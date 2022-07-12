
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from redditwarp.models.submission_ASYNC import Submission
    from redditwarp.models.message_ASYNC import MailboxMessage

import sys
import os
import asyncio
import asyncio.queues
import logging
import logging.handlers
from pathlib import Path
import time
import re
import random
import atexit
import signal
from configparser import ConfigParser
from contextlib import suppress
from collections import deque
from functools import partial

import redditwarp
from redditwarp.streaming.makers.subreddit_ASYNC import make_submission_stream
from redditwarp.streaming.makers.message_ASYNC import make_inbox_message_stream
from redditwarp.models.submission_ASYNC import TextPost
from redditwarp.models.message_ASYNC import ComposedMessage, CommentMessage
from redditwarp.models.message import CommentMessageCause
from redditwarp.util.base_conversion import to_base36
from redditwarp.util.token_bucket import TokenBucket
import sqlalchemy
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import create_async_engine as create_engine
import sqlalchemy.ext.asyncio

from ..__about__ import version_string
from ..feature_extraction import extract_features
from ..message_building import get_message_determiner, build_message
from ..database_schema import record_table


async def main(*, debug: bool = False) -> None:
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
    reddit_user_name = section['reddit_user_name']
    target_subreddit_name = section['target_subreddit_name']
    advanced_comment_replying_enabled = section.getboolean('advanced_comment_replying_enabled', False)

    async def get_advanced_comment_reply(
        *,
        logger: logging.Logger,
        engine: sqlalchemy.ext.asyncio.engine.AsyncEngine,
        mesg: CommentMessage,
    ) -> Optional[str]:
        raise Exception

    if advanced_comment_replying_enabled:
        from powershell_bot_snapins.advanced_comment_replying import get_advanced_comment_reply as _get_advanced_comment_reply  # type: ignore

        async def get_advanced_comment_reply(  # noqa: F811
            *,
            logger: logging.Logger,
            engine: sqlalchemy.ext.asyncio.engine.AsyncEngine,
            mesg: CommentMessage,
        ) -> Optional[str]:
            return await _get_advanced_comment_reply(logger=logger, engine=engine, mesg=mesg)

    logger.info('==PROGRAM START==')
    logger.info('Version: %s', version_string)
    logger.info('Log file path: %s', str(log_file_path.resolve()))
    logger.info('Reddit account name: u/%s', reddit_user_name)
    logger.info('Targeting subreddit: r/%s', target_subreddit_name)

    engine = create_engine(database_url, future=True)

    client = redditwarp.ASYNC.Client.from_praw_config(reddit_user_name)

    me = await client.p.account.fetch()
    if me.name != reddit_user_name:
        raise RuntimeError("the account name must exactly match the name given in the configuration file")

    subsidiaries: deque[asyncio.Task[None]] = deque([])

    #region

    submission_stream = make_submission_stream(client, target_subreddit_name)

    @submission_stream.output.attach
    async def _(subm: Submission) -> None:
        logger.info('Found new submission: %s', subm.id36)

        if not isinstance(subm, TextPost):
            logger.info('Submission is not a text post')
            return

        b = extract_features(subm.body)
        det = get_message_determiner(b)

        bot_comment_id = None
        if det is None:
            logger.info('Submission is OK')
        else:
            logger.info('Submission not OK. Preparing to reply to submission')
            message = build_message(
                determiner=det,
                submission_id=subm.id,
                rel_permalink=subm.rel_permalink,
                enlightened=False,
                reddit_user_name=reddit_user_name,
            )
            try:
                comm = await client.p.submission.reply(subm.id, message)
            except Exception:
                logger.error('Failed to reply to submission', exc_info=True)
                return
            logger.info('Created bot comment: %s', comm.id36)
            bot_comment_id = comm.id

        record_data = {
            'feature_flags': b,
            'recheck': True,
            'target_submission_id': subm.id,
            'target_submission_created_ut': subm.created_ut,
            'target_submission_author_name': subm.author_name,
            'bot_comment_id': bot_comment_id,
        }

        async def coro_func() -> None:
            async with engine.connect() as conn:
                await conn.execute(
                    insert(record_table),
                    record_data,
                )
                await conn.commit()

        task = asyncio.create_task(coro_func())
        subsidiaries.append(task)
        task.add_done_callback(subsidiaries.remove)
        await asyncio.shield(task)
        logger.info("Added submission to database: %s", subm.id36)

    @submission_stream.error.attach
    async def _(error: Exception) -> None:
        logger.info('Error from submission stream error hook', exc_info=error)

    #endregion

    #region

    async def process_recheck_submission_row(
        conn: sqlalchemy.ext.asyncio.engine.AsyncConnection,
        row: sqlalchemy.engine.row.Row,
    ) -> None:
        try:
            subm = await client.p.submission.fetch(row.target_submission_id)
        except Exception:
            logger.error('Error fetching submission: %s', to_base36(row.target_submission_id), exc_info=True)
            return

        if not isinstance(subm, TextPost):
            logger.error('Recorded submission is not a text post: %s', subm.id36)
            return

        if subm.removal_category:
            logger.info('Submission was removed/deleted: %s', subm.id36)
            await conn.execute(update(record_table).where(record_table.c.id == row.id), {'recheck': False})
            await conn.commit()
            return

        old_feature_flags = row.feature_flags
        new_feature_flags = extract_features(subm.body)

        if new_feature_flags == old_feature_flags:
            logger.debug('No new changes in submission: %s', subm.id36)
            return
        logger.info('New change detected in submission: %s', subm.id36)

        new_det = get_message_determiner(new_feature_flags)
        old_det = get_message_determiner(old_feature_flags)

        det = new_det
        if det is None:
            det = old_det

        if det is None:
            logger.info('No update to bot comment required')
        else:
            message = build_message(
                determiner=det,
                submission_id=subm.id,
                rel_permalink=subm.rel_permalink,
                enlightened=new_det is None,
                reddit_user_name=reddit_user_name,
            )

            bot_comment_id = row.bot_comment_id
            if bot_comment_id is None:
                logger.info('Preparing to reply to submission: %s', row.target_submission_id)

                try:
                    comm = await client.p.submission.reply(subm.id, message)
                except Exception:
                    logger.error('Failed to reply to submission', exc_info=True)
                    return
                logger.info('Created bot comment: %s', comm.id36)

                await conn.execute(update(record_table).where(record_table.c.id == row.id), {'bot_comment_id': comm.id})
                await conn.commit()

            else:
                try:
                    await client.p.comment.edit_body(bot_comment_id, message)
                except Exception:
                    logger.error('Unable to edit bot comment: %s', to_base36(bot_comment_id), exc_info=True)
                    return
                logger.info('Updated bot comment: %s', to_base36(bot_comment_id))

        async def coro_func() -> None:
            await conn.execute(
                update(record_table).where(record_table.c.id == row.id),
                {'feature_flags': new_feature_flags},
            )
            await conn.commit()

        task = asyncio.create_task(coro_func())
        subsidiaries.append(task)
        task.add_done_callback(subsidiaries.remove)
        await asyncio.shield(task)

    async def recheck_submission(submission_id: int) -> None:
        async with engine.connect() as conn:
            result = await conn.execute(select(record_table).where(record_table.c.target_submission_id == submission_id))
            row = result.first()
            if row is None:
                return
            await process_recheck_submission_row(conn, row)

    async def recheck_submissions_monitor_job() -> None:
        base_poll_interval = 30
        max_poll_interval = 3 * 60
        jitter_factor = .4
        backoff_factor = 2
        delay = base_poll_interval

        forget_after = 60 * 60 * 24 * 1  # 1 day

        failure_threshold = .5

        while True:
            cycle_total_count = 0
            cycle_error_count = 0

            async with engine.connect() as conn:
                for row in await conn.execute(select(record_table).where(record_table.c.recheck)):
                    if time.time() - row.target_submission_created_ut > forget_after:
                        await conn.execute(update(record_table).where(record_table.c.id == row.id), {'recheck': False})
                        await conn.commit()
                        continue

                    cycle_total_count += 1

                    await process_recheck_submission_row(conn, row)

                    last_response = client.http.last.response
                    if last_response is None or not last_response.status_successful():
                        cycle_error_count += 1

            successful = True
            if cycle_total_count:
                successful = cycle_error_count / cycle_total_count <= failure_threshold
            if successful:
                delay = base_poll_interval
            else:
                if delay < max_poll_interval:
                    delay = min(backoff_factor * delay, max_poll_interval)

            t = random.uniform(delay * (1 - jitter_factor), delay * (1 + jitter_factor))
            await asyncio.sleep(t)

    #endregion

    #region

    delete_command_regex = re.compile(r"^!delete +([a-z0-9]{1,12}) *$", re.I)
    ping_command_regex = re.compile(r"^!ping *$", re.I)

    good_being_regex = re.compile(r"^Good (\w+)\.?$", re.I)


    comment_replying_queue: asyncio.queues.Queue[CommentMessage] = asyncio.queues.Queue(5)

    async def comment_replying_queue_worker() -> None:
        tb = TokenBucket(5, 1)

        while True:
            mesg = await comment_replying_queue.get()
            try:
                await asyncio.sleep(tb.get_cooldown(1))
                tb.consume(1)

                logger.info('Generating comment reply for comment: %s', to_base36(mesg.comment.id))

                await recheck_submission(mesg.submission.id)

                try:
                    reply_text = await get_advanced_comment_reply(logger=logger, engine=engine, mesg=mesg)
                except Exception:
                    logger.error('Error during advanced comment reply generation', exc_info=True)
                    continue

                if reply_text is None:
                    logger.info('No advanced comment reply text generated')
                    continue

                try:
                    await client.p.comment.reply(mesg.comment.id, reply_text + "\n\n&thinsp;^^^(*Beep-boop.*)")
                except Exception:
                    logger.error('Failed to reply to comment after NLP text generation', exc_info=True)
                    continue

                logger.info('Made NLP reply to comment: %s', to_base36(mesg.comment.id))

            finally:
                comment_replying_queue.task_done()


    inbox_message_stream = make_inbox_message_stream(client)

    @inbox_message_stream.output.attach
    async def _(mesg: MailboxMessage) -> None:
        logger.info('Mailbox message received')

        if isinstance(mesg, ComposedMessage):
            logger.info('Composed message received from u/%s', mesg.author_name)

            m = ping_command_regex.match(mesg.subject)
            if m:
                logger.info('Ping')
                try:
                    await client.p.message.send(
                        mesg.author_name,
                        're: ' + mesg.subject,
                        'pong',
                    )
                except Exception:
                    logger.error('Failed to return ping: %s', to_base36(mesg.id), exc_info=True)
                return


            m = delete_command_regex.match(mesg.subject)
            if m is None:
                logger.info('Message is not a deletion request')
                return

            target_submission_id36 = m[1]
            target_submission_id = int(target_submission_id36, 36)

            logger.info('Deletion request on submission: %s', target_submission_id36)

            async with engine.connect() as conn:
                result = await conn.execute(
                        select(record_table)
                        .where(record_table.c.target_submission_id == target_submission_id))
                row = result.first()

            if row is None:
                logger.info('The submission ID was not found in the database')
                return

            bot_comment_id = row.bot_comment_id
            if bot_comment_id is None:
                logger.info('The bot has not commented on the submission')
                return

            logger.info('Relevant comment: %s', to_base36(bot_comment_id))

            if (
                mesg.author_name != row.target_submission_author_name
                and mesg.author_name not in {reddit_user_name, 'Pyprohly', 'nascentt'}
            ):
                logger.info('User is not permitted to delete the comment')
                return

            try:
                tree_node = await client.p.comment_tree.fetch(row.target_submission_id, bot_comment_id)
            except redditwarp.exceptions.RejectedResultException:
                logger.info("The comment doesn't appear to exist anymore")
                return
            except Exception:
                logger.error('Failed to fetch bot comment', exc_info=True)
                return

            replies = tree_node.children[0].children
            if replies:
                logger.info('The bot comment has replies')
                return

            try:
                await client.p.comment.delete(bot_comment_id)
            except Exception:
                logger.error('Failed to delete bot comment: %s', to_base36(bot_comment_id), exc_info=True)
                return

            logger.info('Deleted bot comment: %s', to_base36(bot_comment_id))

            async with engine.connect() as conn:
                await conn.execute(update(record_table).where(record_table.c.id == row.id), {'recheck': False})
                await conn.commit()

        elif isinstance(mesg, CommentMessage):
            logger.info('Comment message received from u/%s', mesg.author_name)

            if mesg.cause != CommentMessageCause.COMMENT_REPLY:
                return

            m = good_being_regex.match(mesg.comment.body)
            if m:
                if m[1].lower() != 'bot':
                    return
                if random.random() < .3:
                    return

                logger.info('Replying to comment: %s', mesg.comment.id)

                try:
                    await client.p.comment.reply(mesg.comment.id, "Good human.\n\n&thinsp;^^^(*Beep-boop.*)")
                except Exception:
                    logger.error('Failed to reply to comment', exc_info=True)
                    return

            else:
                if not advanced_comment_replying_enabled:
                    return
                if len(mesg.comment.body) > 110:
                    logger.info('Comment body is too long to reply to')
                    return
                if not comment_replying_queue.full():
                    comment_replying_queue.put_nowait(mesg)

    @inbox_message_stream.error.attach
    async def _(error: Exception) -> None:
        logger.info('Error from inbox stream error hook', exc_info=error)

    #endregion

    aws = [
        submission_stream,
        recheck_submissions_monitor_job(),
        inbox_message_stream,
    ]
    if advanced_comment_replying_enabled:
        aws.append(comment_replying_queue_worker())
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

    async def termination_coro_func() -> None:
        for fut in futs:
            fut.cancel()
        for fut in futs:
            with suppress(asyncio.CancelledError):
                await fut
        while subsidiaries:
            task = subsidiaries.popleft()
            await task

        await engine.dispose()

    TERMINATION_ACCEPTABLE_DELAY_SECONDS = 5

    termination_task = asyncio.create_task(termination_coro_func())
    _done, pending = await asyncio.wait({termination_task}, timeout=TERMINATION_ACCEPTABLE_DELAY_SECONDS)
    if pending:
        logger.warning('Termination is taking longer than expected')
    await termination_task

    logger.info('==PROGRAM END==')

def run_bot(*, debug: bool = False) -> None:
    asyncio.run(main(debug=debug))
