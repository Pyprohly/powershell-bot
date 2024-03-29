
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
subparser_test_string = subparsers.add_parser('process_targets', help="Process submissions individually. Only add the submission to the database if it is not OK.", formatter_class=Formatter)
subparser_test_string.add_argument('submission_id36', nargs='+')
args = parser.parse_args()
###;

import sys
from configparser import ConfigParser
import asyncio

import redditwarp.http.transport.connectors.httpx  # noqa: F401
from sqlalchemy.ext.asyncio import create_async_engine as create_engine

from .database_schema import create_database_async
from . import programs


subparser_name: Optional[str] = args.subparser_name
if subparser_name == 'run':
    debug: bool = args.debug
    programs.bot.run_invoke(debug=debug)

elif subparser_name == 'create_database':
    config = ConfigParser()
    config.read('powershell_bot.ini')
    database_url = config[config.default_section]['database_url']
    engine = create_engine(database_url)
    asyncio.run(create_database_async(engine))

elif subparser_name == 'show_config':
    config = ConfigParser()
    config.read('powershell_bot.ini')
    section = config[config.default_section]
    database_url = section['database_url']
    username = section['username']
    target_subreddit_name = section['target_subreddit_name']
    advanced_comment_replying_enabled = section.getboolean('advanced_comment_replying_enabled', False)
    username = section['username']
    password = section['password']
    print(f'''\
{database_url = })
{username = }
{password = }
{target_subreddit_name = }
{advanced_comment_replying_enabled = }
''', end='')

elif subparser_name == 'test_one':
    target_id36: str = args.target
    programs.test_one.run_invoke(int(target_id36, 36))

elif subparser_name == 'test_many':
    n: int = args.n
    programs.test_many.run_invoke(n=n)

elif subparser_name == 'test_string':
    text: str = args.text
    programs.test_string.run_invoke(text)

elif subparser_name == 'process_targets':
    submission_id36s: Iterable[str] = args.submission_id36
    programs.process_targets.run_invoke(submission_id36s)

else:
    parser.print_usage(file=sys.stderr)
