
from typing import Iterable

import sys
import asyncio
from configparser import ConfigParser

import redditwarp.ASYNC
from redditwarp.models.submission_ASYNC import TextPost
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine as create_engine

from ..database_schema import record_table
from ..feature_extraction import extract_features
from ..message_building import get_message_determiner, build_message

async def invoke(submission_id36s: Iterable[str]) -> None:
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    database_url = section['database_url']
    username = section['username']
    target_subreddit_name = section['target_subreddit_name']

    engine = create_engine(database_url)

    client = redditwarp.ASYNC.Client.from_praw_config(username)

    for submission_id36 in submission_id36s:
        subm = await client.p.submission.fetch(int(submission_id36, 36))

        if subm.subreddit.name != target_subreddit_name:
            print(
                    ("Submission subreddit does not equal target subreddit: "
                    f"{subm.subreddit.name!r} != {target_subreddit_name!r}"),
                    file=sys.stderr)
            continue

        if not isinstance(subm, TextPost):
            print('Submission is not a text post: ' + submission_id36, file=sys.stderr)
            continue

        b = extract_features(subm.body)
        det = get_message_determiner(b)

        if det is None:
            print('Submission is OK')
            continue

        print('Preparing to reply to submission: ' + submission_id36, file=sys.stderr)

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
            print('Failed to reply to submission: ' + submission_id36, file=sys.stderr)
            continue

        async with engine.connect() as conn:
            await conn.execute(
                insert(record_table),
                {
                    'feature_flags': b,
                    'recheck': True,
                    'target_submission_id': subm.id,
                    'target_submission_created_ut': subm.created_ut,
                    'target_submission_author_name': subm.author_display_name,
                    'bot_comment_id': comm.id,
                },
            )
            await conn.commit()

def run_invoke(submission_id36s: Iterable[str]) -> None:
    asyncio.run(invoke(submission_id36s))
