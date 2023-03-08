
from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable
if TYPE_CHECKING:
    import logging
    import redditwarp.ASYNC
    from redditwarp.models.submission_ASYNC import Submission
    from ...dal.service import Service


from redditwarp.streaming.makers.subreddit_ASYNC import create_submission_stream
from redditwarp.models.submission_ASYNC import TextPost

from ...message_building import get_message_determiner, build_message
from ...feature_extraction import extract_features


def get_submission_replying_component(
    *,
    client: redditwarp.ASYNC.Client,
    target_subreddit_name: str,
    logger: logging.Logger,
    username: str,
    service: Service,
) -> Awaitable[None]:
    submission_stream = create_submission_stream(client, target_subreddit_name)

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
                enlightened=False,
                submission_id=subm.id,
                permalink_path=subm.permalink_path,
                username=username,
                submission_body_len=len(subm.body),
            )
            try:
                comm = await client.p.submission.reply(subm.id, message)
            except Exception:
                logger.error('Failed to reply to submission', exc_info=True)
                return
            logger.info('Created bot comment: %s', comm.id36)
            bot_comment_id = comm.id

        await service.add_record(
            feature_flags=b,
            target_submission_id=subm.id,
            target_submission_created_ut=subm.created_ut,
            target_submission_author_name=subm.author_display_name,
            bot_comment_id=bot_comment_id,
        )

        logger.info("Added submission to database: %s", subm.id36)

    @submission_stream.error.attach
    async def _(error: Exception) -> None:
        logger.info('Error from submission stream error hook', exc_info=error)

    return submission_stream
