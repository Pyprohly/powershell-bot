
from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable, Optional
if TYPE_CHECKING:
    import redditwarp.ASYNC
    import logging
    from ...dal.service import Service

import asyncio
import re

from redditwarp.util.base_conversion import to_base36
from redditwarp.util.token_bucket import TokenBucket
from redditwarp.models.message_ASYNC import CommentMessage

from .submission_rechecking_component import process_recheck_record


delete_command_regex = re.compile(r"^!delete +([a-z0-9]{1,12}) *$", re.I)
ping_command_regex = re.compile(r"^!ping *$", re.I)

good_being_regex = re.compile(r"^Good (\w+)\.?$", re.I)


def get_comment_replying_component(
    client: redditwarp.ASYNC.Client,
    logger: logging.Logger,
    service: Service,
    advanced_comment_replying_enabled: bool,
    username: str,
    comment_replying_queue: asyncio.queues.Queue[CommentMessage],
) -> Awaitable[None]:
    async def get_advanced_comment_reply(
        *,
        logger: logging.Logger,
        service: Service,
        mesg: CommentMessage,
    ) -> Optional[str]:
        raise Exception

    if advanced_comment_replying_enabled:
        from powershell_bot_snapins.advanced_comment_replying import get_advanced_comment_reply as _get_advanced_comment_reply  # type: ignore

        async def get_advanced_comment_reply(  # noqa: F811
            *,
            logger: logging.Logger,
            service: Service,
            mesg: CommentMessage,
        ) -> Optional[str]:
            return await _get_advanced_comment_reply(logger=logger, service=service, mesg=mesg)

    async def comment_replying_queue_comsumer() -> None:
        tb = TokenBucket(5, 1)

        while True:
            mesg = await comment_replying_queue.get()
            try:
                await asyncio.sleep(tb.get_cooldown(1))
                tb.consume(1)

                logger.info('Generating comment reply for comment: %s', to_base36(mesg.comment.id))

                record = await service.get_record_by_submission_id(mesg.submission.id)
                if record is not None:
                    await process_recheck_record(
                        client=client,
                        logger=logger,
                        record=record,
                        username=username,
                        service=service,
                    )

                try:
                    reply_text = await get_advanced_comment_reply(logger=logger, service=service, mesg=mesg)
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

    return comment_replying_queue_comsumer()
