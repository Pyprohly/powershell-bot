
import asyncio
from configparser import ConfigParser

import redditwarp
from redditwarp.models.submission_SYNC import TextPost

from ..feature_extraction import extract_features
from ..message_building import get_message_determiner

async def main(*, n: int) -> None:
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    reddit_user_name = section['reddit_user_name']

    client = redditwarp.SYNC.Client.from_praw_config(reddit_user_name)

    it = client.p.subreddit.pull.new('PowerShell', amount=n)
    for subm in it:
        if not isinstance(subm, TextPost):
            continue

        b = extract_features(subm.body)
        det = get_message_determiner(b)
        print(f"https://old.reddit.com/comments/{subm.id36} :: {det}")

def run_test_many(n: int) -> None:
    asyncio.run(main(n=n))
