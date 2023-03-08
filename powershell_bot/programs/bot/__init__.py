
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Awaitable
if TYPE_CHECKING:
    from redditwarp.models.message_ASYNC import CommentMessage
    from ...lib.online_presence_indicator import OnlinePresenceIndicator

import sys
import os
import asyncio
import asyncio.queues
import logging
import logging.handlers
from pathlib import Path
import atexit
import signal
from configparser import ConfigParser
from contextlib import suppress
from functools import partial

import redditwarp.ASYNC
from sqlalchemy.ext.asyncio import create_async_engine as create_engine

from ...__about__ import version_string
from ...dal.service import Service
from ...lib.online_presence_indicator import create_online_presence_indicator_factory
from .submission_replying_component import get_submission_replying_component
from .submission_rechecking_component import get_submission_rechecking_component
from .comment_replying_component import get_comment_replying_component
from .inbox_monitoring_component import get_inbox_monitoring_component


async def invoke(*, debug: bool = False) -> None:
    loop = asyncio.get_running_loop()

    @partial(loop.add_signal_handler, signal.SIGTERM)
    def _() -> None:
        sys.exit(0)

    lock_file_path = Path('powershell_bot.lock')
    if lock_file_path.is_file():
        print('Program appears to be running already. Lock file: ' + str(lock_file_path.resolve()), file=sys.stderr)
        sys.exit(1)
    lock_file_path.touch()

    @atexit.register
    def _() -> None:
        lock_file_path.unlink()

    pid_file_path = Path('powershell_bot.pid')
    pid = os.getpid()
    print(pid)
    pid_file_path.write_text(str(pid) + '\n')
    with pid_file_path.open('w') as fh:
        print(pid, file=fh)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    log_file_path = Path('powershell_bot.log')
    handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file_path),
        encoding='utf-8',
        maxBytes=2*1024*1024,
        backupCount=2,
    )
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        "%d/%b/%Y %H:%M:%S",
    ))
    logger.addHandler(handler)

    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    database_url = section['database_url']
    username = section['username']
    target_subreddit_name = section['target_subreddit_name']
    advanced_comment_replying_enabled = section.getboolean('advanced_comment_replying_enabled', False)
    username = section['username']
    password = section['password']

    logger.info('=== PROGRAM START ===')
    logger.info('Version: %s', version_string)
    logger.info('Log file path: %s', str(log_file_path.resolve()))
    logger.info('Reddit account name: u/%s', username)
    logger.info('Targeting subreddit: r/%s', target_subreddit_name)

    client = redditwarp.ASYNC.Client.from_praw_config(username)
    me = await client.p.account.fetch()
    if me.name != username:
        raise RuntimeError("the account name must exactly match the name given in the configuration file")

    engine = create_engine(database_url)
    haven: set[asyncio.Task[None]] = set()
    service = Service(engine=engine, haven=haven)
    comment_replying_queue: asyncio.queues.Queue[CommentMessage] = asyncio.queues.Queue(5)
    presence_factory = await create_online_presence_indicator_factory(username, password)

    async def do_online_presence_indicator_forever(factory: Callable[[], Awaitable[OnlinePresenceIndicator]]) -> None:
        while True:
            try:
                presence = await factory()
                async with (presence, presence.being_online()):
                    async for _event in presence.ws:
                        pass
            except Exception:
                logger.error('Online presence websocket error', exc_info=True)
                await asyncio.sleep(60)

    aws = [
        do_online_presence_indicator_forever(presence_factory),
        get_submission_replying_component(
            client=client,
            logger=logger,
            target_subreddit_name=target_subreddit_name,
            username=username,
            service=service,
        ),
        get_submission_rechecking_component(
            client=client,
            logger=logger,
            username=username,
            service=service,
        ),
        get_comment_replying_component(
            client=client,
            logger=logger,
            service=service,
            advanced_comment_replying_enabled=advanced_comment_replying_enabled,
            username=username,
            comment_replying_queue=comment_replying_queue,
        ),
        get_inbox_monitoring_component(
            client=client,
            service=service,
            logger=logger,
            username=username,
            advanced_comment_replying_enabled=advanced_comment_replying_enabled,
            comment_replying_queue=comment_replying_queue,
        ),
    ]
    futs = [asyncio.ensure_future(aw) for aw in aws]

    termination = loop.create_future()

    @partial(loop.add_signal_handler, signal.SIGTERM)
    def _() -> None:
        if not termination.done():
            termination.set_result(None)

    logger.info('Bot is now live')

    for aw in asyncio.as_completed({termination, *futs}):
        try:
            await aw
        except Exception:
            logger.critical('Unhandled exception encountered', exc_info=True)
            raise
        if termination.done():
            break

    logger.info('Termination sequence starting')

    async def termination_coro_fn() -> None:
        for fut in futs:
            fut.cancel()
        for fut in futs:
            with suppress(asyncio.CancelledError):
                await fut

        while haven:
            await haven.pop()

        await engine.dispose()

    ACCEPTABLE_TERMINATION_DELAY = 5
    termination_task = asyncio.create_task(termination_coro_fn())
    _done, pending = await asyncio.wait({termination_task}, timeout=ACCEPTABLE_TERMINATION_DELAY)
    if pending:
        logger.warning('Termination is taking longer than expected')
    await termination_task

    logger.info('=== PROGRAM END ===')

def run_invoke(*, debug: bool = False) -> None:
    asyncio.run(invoke(debug=debug))
