#!/usr/bin/env python3

"""Tells redditors in /r/PowerShell to wrap their code in a code block."""

def main():
	import os
	import time
	from collections import deque
	import logging, logging.handlers
	from pathlib import Path
	import praw, prawcore

	from reddit import reddit
	from strategy import process_subsmission, process_inbox_item
	from config import target_subreddits

	script_path = Path(__file__).resolve()
	os.chdir(script_path.parent)


	prawcore_logger = logging.getLogger('prawcore')
	prawcore_logger.setLevel(logging.DEBUG)

	log_file = script_path.parent / 'log' / 'prawcore.log'
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
		prawcore_logger.addHandler(rfh)

		prawcore_logger.info('Log ({}): {}'.format(prawcore_logger.name, log_file.absolute()))


	logger = logging.getLogger(__name__)
	logger.setLevel(logging.INFO)
	#logger.addHandler(logging.StreamHandler())
	#logger.disabled = True

	log_file = script_path.parent / 'log' / script_path.with_suffix('.log').name
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

	if reddit.read_only:
		raise RuntimeError('a read-write reddit instance is required')

	subreddit = reddit.subreddit('+'.join(target_subreddits))

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

				process_subsmission(submission)

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

				process_inbox_item(item)

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
				logger.info('Exception: RequestException: {}'.format(e.original_exception))
				time.sleep(5)

			else:
				logger.warning('Exception: unhandled PRAW exception:', exc_info=True)

		except Exception:
			logger.error('Exception: unhandled exception:', exc_info=True)

register = {
	'name': 'PowerShell-Bot',
	'component': 'main',
	'author': 'Pyprohly',
	'owner': 'Pyprohly',
	'version': None,
	'description': __doc__,
	'license': 'MIT License'
}

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
