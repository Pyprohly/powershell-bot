
import asyncio
from configparser import ConfigParser

from ..feature_extraction import extract_features
from ..message_building import get_message_determiner, build_message

async def invoke(text: str) -> None:
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    username = section['username']

    b = extract_features(text)
    det = get_message_determiner(b)

    print(b)
    print(det)

    if det is not None:
        msg = build_message(
            determiner=det,
            submission_id=0,
            permalink_path='',
            enlightened=False,
            username=username,
            submission_body_len=300,
        )
        print()
        print(msg)

def run_invoke(text: str) -> None:
    asyncio.run(invoke(text))
