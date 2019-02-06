#!/usr/bin/env python3

"""Tells redditors in /r/PowerShell to wrap their code in a code block."""

def main():
	import os
	import time
	import logging, logging.handlers
	from pathlib import Path
	import praw, prawcore

	from reddit import reddit
	from strategy import process_subsmission, process_inbox_item
	from config import target_subreddits

	script_path = Path(__file__).resolve()
	os.chdir(script_path.parent)

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

	submission_stream = subreddit.stream.submissions(pause_after=-1, skip_existing=True)
	inbox_stream = reddit.inbox.stream(pause_after=-1, skip_existing=True)

	while True:
		try:
			for submission in submission_stream:
				if submission is None:
					break

				process_subsmission(submission)

			for item in inbox_stream:
				if item is None:
					break

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
