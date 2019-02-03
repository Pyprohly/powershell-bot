
import os
import time
import logging
from pathlib import Path
import re
import praw, prawcore

import db_services
from regex_checks import TopicFlags, ExtraFlags, match_control
from messages import get_message
from config import praw_config
from powershell_bot import register

script_path = Path(__file__).resolve()
os.chdir(script_path.parent)

logger = logging.getLogger(__name__)
#logger.disabled = True
logger.setLevel(logging.INFO)
#logger.addHandler(logging.StreamHandler())

log_file = script_path.parent / 'log' / 'powershell_bot.log'
if log_file.parent.is_dir():
	log_format = '%(asctime)s %(levelname)s %(funcName)s:%(lineno)d | %(message)s'
	rfh_config = {
		'filename': log_file,
		'encoding': 'utf-8',
		'maxBytes': 5*1024*1024, # 5 megabytes
		'backupCount': 8
	}
	rfh = logging.handlers.RotatingFileHandler(**rfh_config)
	rfh.setFormatter(logging.Formatter(log_format))
	logger.addHandler(rfh)

	logger.info('Log ({}): {}'.format(logger.name, log_file.absolute()))

delete_command_pattern = r'^!delete +(?:(t1)_)?([a-z0-9]{1,12})$'
delete_regexp = re.compile(delete_command_pattern, re.I)

recheck_command_pattern = r'^!recheck +(?:(t[1-6])_)?([a-z0-9]{1,12})$'
recheck_regexp = re.compile(recheck_command_pattern, re.I)

ignore_inbox_items_older_than = 60 * 2 # 2 minutes

trustees = [i.lower() for i in (register['owner'], praw_config['username'])]

reddit = praw.Reddit(**praw_config)
me = reddit.user.me()
if me is None:
	raise RuntimeError('redditor instance is required')

def process_subsmission(submission):
	if not submission.is_self:
		logger.info('Skip: link submission: {}'.format(submission.permalink))
		return

	# Rough check to see if bot hasn't replied already
	submission.comments.replace_more(limit=0)
	if any(1 for comment in submission.comments if comment.author == me):
		logger.warning('Skip: already replied to: {}'.format(submission.permalink))
		return

	match_control.check_all(submission.selftext)
	b = match_control[TopicFlags]
	y = match_control[ExtraFlags]

	if b == 0:
		logger.info('Skip: no match: {}'.format(submission.permalink))
		return

	logger.info('Process submission: {}'.format(submission.permalink))

	message_kwargs = {
		'topic_flags': b,
		'signature': 1,
		'pester': True,
		'passed': False,
		'some': bool(y & ExtraFlags.contains_code_block),
		'thing_kind': type(submission).__name__,
		'redditor': submission.author.name,
		'old_reddit_permalink': 'https://old.reddit.com' + submission.permalink,
		'new_reddit_permalink': 'https://new.reddit.com' + submission.permalink
	}

	message = get_message(**message_kwargs)
	reply = submission.reply(message)

	message_kwargs.update({
		'signature': 2,
		'bot_name': me.name,
		'reply_id': reply.id
	})

	message = get_message(**message_kwargs)
	reply.edit(message)

	db_services.record_submission_reply(submission, reply, b, y)

def process_inbox_item(item):
	if item.was_comment:
		logger.info('[Inbox] Skip: ignore non-message item: t1_{}'.format(item.id))
		return

	if time.time() - item.created_utc > ignore_inbox_items_older_than:
		logger.info('[Inbox] Skip: {0} is older than {1} seconds'.format(type(item).__name__, ignore_inbox_items_older_than))
		return

	delete_match = delete_regexp.match(item.subject)
	recheck_match = recheck_regexp.match(item.subject)

	if not (delete_match or recheck_match):
		logger.info('[Inbox] Skip: no match (subject line): t4_{}'.format(item.id))
		return

	item.mark_read()

	if delete_match:
		logger.info('[Inbox] Process: inbox item, deletion request (from /u/{}): t4_{}'.format(item.author.name, item.id))

		thing_kind = delete_match.group(1)
		comment_id = delete_match.group(2)

		if thing_kind is not None:
			if thing_kind != 't1':
				logger.info(f"[Inbox] Skip: not the kind we're looking for: {thing_kind}{comment_id}")
				return

		comment = reddit.comment(comment_id)
		try:
			comment.refresh()
		except praw.exceptions.PRAWException:
			logger.info('[Inbox] Skip: not found: t1_{}'.format(comment_id))
			return

		target_id = db_services.get_target_id(comment_id)
		if target_id is None:
			logger.warning('[Inbox] Warning: could not resolve target_id from comment: t1_{}'.format(comment_id))

		by_authority = item.author.name.lower() in trustees
		if by_authority:
			comment.delete()

			if target_id is not None:
				db_services.assign_is_set_0(target_id)

			logger.info('[Inbox] Success: force delete: {}'.format(comment.permalink))
			return

		if target_id is None:
			logger.warning('[Inbox] Skip: cannot resolve author_name from null target_id: t1_{}'.format(comment_id))

		author_name = db_services.get_author_name(target_id)
		if author_name is None:
			logger.warning('[Inbox] Skip: could not resolve author_name from target_id: t1_{}'.format(comment_id))
			return

		if comment.author != me:
			logger.info('[Inbox] Skip: not owned: {}'.format(comment.permalink))
			return

		by_op = item.author.name.lower() == author_name.lower()
		if not by_op:
			logger.info('[Inbox] Skip: delete not permitted: {}'.format(comment.permalink))
			return

		if len(comment.replies):
			logger.info('[Inbox] Skip: has replies: {}'.format(comment.permalink))
			return

		if not db_services.is_deletable(comment_id):
			logger.info('[Inbox] Skip: not deletable: {}'.format(comment.permalink))
			return

		comment.delete()
		db_services.assign_is_set_0(target_id)

		logger.info('[Inbox] Success: deleted: {}'.format(comment.permalink))

	elif recheck_match:
		logger.info('[Inbox] Process: inbox item, recheck request (from /u/{}): t4_{}'.format(item.author.name, item.id))

		by_authority = item.author.name.lower() in trustees
		if not by_authority:
			logger.info('[Inbox] Skip: not permitted: {}'.format(comment.permalink))
			return

		thing_kind = recheck_match.group(1)
		thing_id = recheck_match.group(2)

		if thing_kind is None:
			logger.info('[Inbox] Skip: thing_kind was not specified: {thing_kind}{thing_id}')
			return
		if thing_kind != 't3':
			logger.info(f"[Inbox] Skip: not the kind we're looking for: {thing_kind}{thing_id}")
			return

		submission = reddit.submission(thing_id)
		try:
			submission._fetch()
		except prawcore.exceptions.NotFound:
			logger.warning('Skip: submission ID not found: t3_{}'.format(thing_id))
			db_services.assign_is_set_0(thing_id)
			return

		process_subsmission(submission)
