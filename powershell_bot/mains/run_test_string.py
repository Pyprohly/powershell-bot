
import asyncio
from configparser import ConfigParser

from ..feature_extraction import extract_features
from ..message_building import get_message_determiner, build_message

async def main(text: str) -> None:
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    reddit_user_name = section['reddit_user_name']

    b = extract_features(text)
    det = get_message_determiner(b)

    print(b)
    print(det)

    if det is not None:
        msg = build_message(
            determiner=det,
            submission_id=0,
            rel_permalink='',
            enlightened=False,
            reddit_user_name=reddit_user_name,
        )
        print()
        print(msg)

def run_test_string(text: str) -> None:
    asyncio.run(main(text))
