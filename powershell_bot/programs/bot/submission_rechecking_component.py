
from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable
if TYPE_CHECKING:
    import redditwarp.ASYNC
    import logging
    from ...dal.service import Service
    from ...models.record import Record

import asyncio
import time
import random

from redditwarp.util.base_conversion import to_base36
from redditwarp.models.submission_ASYNC import TextPost

from ...message_building import get_message_determiner, build_message
from ...feature_extraction import extract_features


async def process_recheck_record(
    *,
    client: redditwarp.ASYNC.Client,
    logger: logging.Logger,
    record: Record,
    username: str,
    service: Service,
) -> bool:
    try:
        subm = await client.p.submission.fetch(record.target_submission_id)
    except Exception:
        logger.error('Error fetching submission: %s', to_base36(record.target_submission_id), exc_info=True)
        return False

    if not isinstance(subm, TextPost):
        logger.error('Recorded submission is not a text post: %s', subm.id36)
        return False

    if subm.removal_category:
        logger.info('Submission was removed/deleted: %s', subm.id36)
        await service.deactivate_rechecking(record.id)
        return True

    old_feature_flags = record.feature_flags
    new_feature_flags = extract_features(subm.body)

    if new_feature_flags == old_feature_flags:
        logger.debug('No new changes in submission: %s', subm.id36)
        return True
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
            permalink_path=subm.permalink_path,
            enlightened=new_det is None,
            username=username,
            submission_body_len=len(subm.body),
        )

        bot_comment_id = record.bot_comment_id
        if bot_comment_id is None:
            logger.info('Preparing to reply to submission: %s', record.target_submission_id)

            try:
                comm = await client.p.submission.reply(subm.id, message)
            except Exception:
                logger.error('Failed to reply to submission', exc_info=True)
                return False
            logger.info('Created bot comment: %s', comm.id36)

            await service.set_bot_comment_id(record.id, comm.id)

        else:
            try:
                await client.p.comment.edit_body(bot_comment_id, message)
            except Exception:
                logger.error('Unable to edit bot comment: %s', to_base36(bot_comment_id), exc_info=True)
                return False
            logger.info('Updated bot comment: %s', to_base36(bot_comment_id))

    await service.set_feature_flags(record.id, new_feature_flags)
    return True


def get_submission_rechecking_component(
    *,
    client: redditwarp.ASYNC.Client,
    logger: logging.Logger,
    username: str,
    service: Service,
) -> Awaitable[None]:
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

            async for record in service.produce_rechecking_records():
                if time.time() - record.target_submission_created_ut > forget_after:
                    await service.deactivate_rechecking(record.id)
                    continue

                cycle_total_count += 1

                v = await process_recheck_record(
                    client=client,
                    logger=logger,
                    record=record,
                    username=username,
                    service=service,
                )
                if not v:
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

    return recheck_submissions_monitor_job()
