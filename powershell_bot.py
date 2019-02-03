#!/usr/bin/env python3

"""Tells redditors in /r/PowerShell to wrap their code in a code block."""

if __name__ == '__main__':
	import os
	import time
	from collections import deque
	import logging, logging.handlers
	from pathlib import Path
	import praw, prawcore

	import re

	from regex_checks import TopicFlags, ExtraFlags, match_control
	from messages import get_message
	import db_services

def main():
	script_path = Path(__file__).resolve()
	os.chdir(script_path.parent)

	logger = logging.getLogger(__name__)
	#logger.disabled = True
	logger.setLevel(logging.INFO)
	#logger.addHandler(logging.StreamHandler())

	log_file = script_path.parent / 'log' / script_path.with_suffix('.log').name
	if log_file.parent.is_dir():
		log_format = '%(asctime)s %(levelname)s %(funcName)s:%(lineno)d | %(message)s'
		rfh_config = {
			'filename': log_file,
			'encoding': 'utf-8',
			'maxBytes': 5*1024*1024, # i.e., 5 megabytes
			'backupCount': 8
		}
		rfh = logging.handlers.RotatingFileHandler(**rfh_config)
		rfh.setFormatter(logging.Formatter(log_format))
		logger.addHandler(rfh)

		logger.info('Log ({}): {}'.format(logger.name, log_file.absolute()))

	delete_command_pattern = r'^!delete +(?:t1_)?(\w{1,12})$'
	delete_regexp = re.compile(delete_command_pattern, re.I)

	ignore_inbox_items_older_than = 60 * 2

	deletion_request_trustees = [i.lower() for i in (register['author'], praw_config['username'])]

	reddit = praw.Reddit(**{k: v for k, v in praw_config.items() if v is not None})
	if reddit.read_only:
		raise RuntimeError('a read-write reddit instance is required')
	me = reddit.user.me()
	subreddit = reddit.subreddit('+'.join(register['target_subreddits']))

	start_time = time.time()
	__ = ['submission', 'inbox']
	check_time = dict.fromkeys(__, start_time)
	seen_deque = dict.fromkeys(__, deque(maxlen=100))
	control_checkpoint_progression = lambda d: max(0, .5*(d - 10))

	while True:
		try:
			for submission in subreddit.stream.submissions(pause_after=-1):
				if submission is None:
					break

				if submission.id in seen_deque['submission']:
					logger.debug('Skip: seen item: t3_{}'.format(submission.id))
					continue
				if submission.created_utc < check_time['submission']:
					if submission.created_utc < start_time:
						logger.debug('Skip: item was submitted before bot started: t3_{}'.format(submission.id))
					else:
						logger.debug('Skip: timestamp was supplanted: t3_{}'.format(submission.id))
					continue
				check_time['submission'] += control_checkpoint_progression(submission.created_utc - check_time['submission'])
				seen_deque['submission'].append(submission.id)

				if not submission.is_self:
					logger.info('Skip: link submission: {}'.format(submission.permalink))
					continue

				# Rough check to see if bot hasn't replied already
				submission.comments.replace_more(limit=0)
				if any(1 for comment in submission.comments if comment.author == me):
					logger.warning('Skip: already replied to: {}'.format(submission.permalink))
					continue

				match_control.check_all(submission.selftext)
				y = match_control[ExtraFlags]
				b = match_control[TopicFlags]
				if b == 0:
					logger.info('Skip: no match: {}'.format(submission.permalink))
					continue

				logger.info('Process submission: {}'.format(submission.permalink))

				message_kwargs = {
					'topic_flags': b,
					'signature': 1,
					'pester': True,
					'passed': False,
					'some': y & ExtraFlags.contains_code_block == ExtraFlags.contains_code_block,
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

			for item in reddit.inbox.stream(pause_after=-1):
				if item is None:
					break

				if item.id in seen_deque['inbox']:
					logger.debug('[Inbox] Skip: seen item: t4_{}'.format(item.id))
					continue
				if item.created_utc < check_time['inbox']:
					if item.created_utc < start_time:
						logger.debug('[Inbox] Skip: item was submitted before bot started: t4_{}'.format(item.id))
					else:
						logger.debug('[Inbox] Skip: timestamp was supplanted: t4_{}'.format(item.id))
					continue
				check_time['inbox'] += control_checkpoint_progression(item.created_utc - check_time['inbox'])
				seen_deque['inbox'].append(item.id)

				if item.was_comment:
					logger.info('[Inbox] Skip: ignore non-message item: t1_{}'.format(item.id))
					continue

				if time.time() - item.created_utc > ignore_inbox_items_older_than:
					logger.info('[Inbox] Skip: {0} is older than {1} seconds'.format(type(item).__name__, ignore_inbox_items_older_than))
					continue

				match = delete_regexp.match(item.subject)
				if not match:
					logger.info('[Inbox] Skip: no match (subject line): t4_{}'.format(item.id))
					continue

				logger.info('[Inbox] Process inbox item (from /u/{}): t4_{}'.format(item.author.name, item.id))

				item.mark_read()

				comment_id = match.group(1)
				comment = reddit.comment(comment_id)
				try:
					comment.refresh()
				except praw.exceptions.PRAWException:
					logger.info('[Inbox] Skip: not found: t1_{}'.format(comment_id))
					continue

				target_id = db_services.get_target_id(comment_id)
				if target_id is None:
					logger.warning('[Inbox] Warning: could not resolve target_id from comment: t1_{}'.format(comment_id))

				by_authority = item.author.name.lower() in deletion_request_trustees
				if by_authority:
					comment.delete()

					if target_id is not None:
						db_services.assign_is_set_0(target_id)

					logger.info('[Inbox] Success: force delete: {}'.format(comment.permalink))
					continue

				if target_id is None:
					logger.warning('[Inbox] Skip: cannot resolve author_name from null target_id: t1_{}'.format(comment_id))

				author_name = db_services.get_author_name(target_id)
				if author_name is None:
					logger.warning('[Inbox] Skip: could not resolve author_name from target_id: t1_{}'.format(comment_id))
					continue

				if comment.author != me:
					logger.info('[Inbox] Skip: not owned: {}'.format(comment.permalink))
					continue

				by_op = item.author.name.lower() == author_name.lower()
				if not by_op:
					logger.info('[Inbox] Skip: delete not permitted: {}'.format(comment.permalink))
					continue

				if len(comment.replies):
					logger.info('[Inbox] Skip: has replies: {}'.format(comment.permalink))
					continue

				if not db_services.is_deletable(comment_id):
					logger.info('[Inbox] Skip: not deletable: {}'.format(comment.permalink))
					continue

				comment.delete()
				db_services.assign_is_set_0(target_id)

				logger.info('[Inbox] Success: deleted: {}'.format(comment.permalink))

		except (praw.exceptions.PRAWException, prawcore.exceptions.PrawcoreException) as e:
			if isinstance(e, praw.exceptions.APIException):
				if e.error_type == 'RATELIMIT':
					logger.info('Exception: ratelimit exceeded: {}'.format(e.message))
					time.sleep(11*60)
				else:
					logger.warning('Exception: unhandled PRAW APIException exception:', exc_info=True)

			elif isinstance(e, prawcore.exceptions.ResponseException):
				logger.info('Exception: ResponseException: {}'.format(e.response))
				time.sleep(5)

			elif isinstance(e, prawcore.exceptions.RequestException):
				logger.info('Exception: RequestException: {}'.format(e))
				time.sleep(5)

			else:
				logger.warning('Exception: unhandled PRAW exception:', exc_info=True)

		except Exception:
			logger.error('Exception: unhandled exception:', exc_info=True)

register = {
	'name': 'PowerShell-Bot',
	'author': 'Pyprohly',
	'owner': 'Pyprohly',
	'version': None,
	'description': __doc__,
	'license': 'MIT License',
	'target_subreddits': ['PowerShell']
}

praw_config = {
	'site_name': None,
	'client_id': None,
	'client_secret': None,
	'username': 'PowerShell-Bot',
	'password': None,
	'user_agent': 'PowerShell-Bot by /u/Pyprohly'
}

try:
	import config
except ModuleNotFoundError:
	pass
else:
	praw_config = config.praw_config
	register['target_subreddits'] = config.subreddit_names

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
