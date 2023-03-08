
from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable
if TYPE_CHECKING:
    from redditwarp.models.message_ASYNC import MailboxMessage
    import redditwarp.ASYNC
    import logging
    from ...dal.service import Service

import asyncio
import random

import redditwarp
from redditwarp.models.message import CommentMessageCause
from redditwarp.streaming.makers.message_ASYNC import create_inbox_message_stream
from redditwarp.util.base_conversion import to_base36
from redditwarp.models.message_ASYNC import ComposedMessage, CommentMessage

from .comment_replying_component import (
    ping_command_regex,
    good_being_regex,
    delete_command_regex,
)


def get_inbox_monitoring_component(
    *,
    client: redditwarp.ASYNC.Client,
    logger: logging.Logger,
    service: Service,
    username: str,
    advanced_comment_replying_enabled: bool,
    comment_replying_queue: asyncio.queues.Queue[CommentMessage],
) -> Awaitable[None]:
    inbox_message_stream = create_inbox_message_stream(client)

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

            record = await service.get_record_by_submission_id(target_submission_id)
            if record is None:
                logger.info('The submission ID was not found in the database')
                return

            bot_comment_id = record.bot_comment_id
            if bot_comment_id is None:
                logger.info('The bot has not commented on the submission')
                return

            logger.info('Relevant comment: %s', to_base36(bot_comment_id))

            if (
                mesg.author_name != record.target_submission_author_name
                and mesg.author_name not in {username, 'Pyprohly', 'nascentt'}
            ):
                logger.info('User is not permitted to delete the comment')
                return

            try:
                tree_node = await client.p.comment_tree.fetch(record.target_submission_id, bot_comment_id)
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

            await service.deactivate_rechecking(record.id)

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

    return inbox_message_stream
