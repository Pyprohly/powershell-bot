
from typing import Optional, Iterable

###
import argparse
class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass
parser = argparse.ArgumentParser(formatter_class=Formatter)
subparsers = parser.add_subparsers(description=None, dest='subparser_name')
subparser_run = subparsers.add_parser('run', help="run the bot", formatter_class=Formatter)
subparser_run.add_argument('--debug', action='store_true', help="enable debug level logging")
subparser_create_database = subparsers.add_parser('create_database', help="create the database", formatter_class=Formatter)
subparser_show_config = subparsers.add_parser('show_config', help="display configuration values to help verify that the configuration file can be found", formatter_class=Formatter)
subparser_test_one = subparsers.add_parser('test_one', help="display the generated message for a single submission", formatter_class=Formatter)
subparser_test_one.add_argument('target', help="the ID36 of a submission")
subparser_test_many = subparsers.add_parser('test_many', help="display which submissions from the current new listing would be commented on", formatter_class=Formatter)
subparser_test_many.add_argument('-n', type=int, default=100, help="the number of submissions to check")
subparser_test_string = subparsers.add_parser('test_string', help="display the generated message given a test string", formatter_class=Formatter)
subparser_test_string.add_argument('text')
subparser_test_string = subparsers.add_parser('process_target', help="Process submissions individually. Only add the submission to the database if it is not OK.", formatter_class=Formatter)
subparser_test_string.add_argument('submission_id36', nargs='+')
args = parser.parse_args()
###;

import sys
from configparser import ConfigParser
import asyncio

import redditwarp.http.transport.carriers.httpx  # noqa: F401
from sqlalchemy.ext.asyncio import create_async_engine as create_engine

from .database_schema import create_database_async
from .mains.run_bot import run_bot
from .mains.run_test_one import run_test_one
from .mains.run_test_many import run_test_many
from .mains.run_test_string import run_test_string
from .mains.process_target import process_targets


subparser_name: Optional[str] = args.subparser_name
if subparser_name == 'run':
    debug: bool = args.debug
    run_bot(debug=debug)

elif subparser_name == 'create_database':
    config = ConfigParser()
    config.read('powershell_bot.ini')
    database_url = config[config.default_section]['database_url']
    engine = create_engine(database_url, future=True)
    asyncio.run(create_database_async(engine))

elif subparser_name == 'show_config':
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    database_url = section['database_url']
    reddit_user_name = section['reddit_user_name']
    target_subreddit_name = section['target_subreddit_name']
    advanced_comment_replying_enabled = section.getboolean('advanced_comment_replying_enabled', False)

    print(f'database_url = {database_url!r}')
    print(f'reddit_user_name = {reddit_user_name!r}')
    print(f'target_subreddit_name = {target_subreddit_name!r}')
    print(f'advanced_comment_replying_enabled = {advanced_comment_replying_enabled!r}')

elif subparser_name == 'test_one':
    target_id36: str = args.target
    run_test_one(int(target_id36, 36))

elif subparser_name == 'test_many':
    n: int = args.n
    run_test_many(n=n)

elif subparser_name == 'test_string':
    text: str = args.text
    run_test_string(text)

elif subparser_name == 'process_target':
    submission_id36s: Iterable[str] = args.submission_id36
    process_targets(submission_id36s)

else:
    parser.print_usage(file=sys.stderr)
