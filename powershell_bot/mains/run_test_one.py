
import sys
import asyncio
from configparser import ConfigParser

import redditwarp
from redditwarp.models.submission_SYNC import TextPost

from ..feature_extraction import extract_features
from ..message_building import get_message_determiner, build_message

async def main(idn: int) -> None:
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    reddit_user_name = section['reddit_user_name']

    client = redditwarp.SYNC.Client.from_praw_config(reddit_user_name)

    subm = client.p.submission.get(idn)
    if subm is None:
        print('Submission not found', file=sys.stderr)
        sys.exit(1)

    if not isinstance(subm, TextPost):
        print('Submission is not a text post', file=sys.stderr)
        sys.exit(1)

    b = extract_features(subm.body)
    det = get_message_determiner(b)

    print(b)
    print(det)

    if det is not None:
        msg = build_message(
            determiner=det,
            submission_id=idn,
            rel_permalink=subm.rel_permalink,
            enlightened=False,
            reddit_user_name=reddit_user_name,
        )
        print()
        print(msg)

def run_test_one(idn: int) -> None:
    asyncio.run(main(idn))
