#!/usr/bin/env python3

"""Tells redditors in /r/Batch to wrap their code in a code block."""

if __name__ == '__main__':
	import os
	import time
	from collections import deque
	import logging, logging.handlers
	from pathlib import Path
	import praw, prawcore

	from types import SimpleNamespace

	from regex_checks import MatchBank, match_control
	from utils import submission_reply, record_submission_reply

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

	# A fail-safe stop mechanism in case the bot produces comments too quickly.
	reply_shear = SimpleNamespace(**{
		'enabled': True,
		'pitch': 0,
		'threshold': 4,
		'distance': 60 * 60, # i.e., hourly
		'focus': time.time()
	})

	reddit = praw.Reddit(**{k: v for k, v in praw_config.items() if v is not None})
	if reddit.read_only:
		raise RuntimeError('a read-write reddit instance is required')
	me = reddit.user.me()
	subreddit = reddit.subreddit('+'.join(register['target_subreddits']))

	start_time = time.time()
	check_time =  start_time
	seen_deque = deque(maxlen=100)
	control_checkpoint_progression = lambda d: max(0, .5*(d - 10))

	while 1:
		try:
			for submission in subreddit.stream.submissions(pause_after=None):
				if submission is None:
					continue

				if submission.id in seen_deque:
					logger.debug('Skip: seen item: {}'.format(submission.id))
					continue
				if submission.created_utc < check_time:
					if submission.created_utc < start_time:
						logger.debug('Skip: item was submitted before bot started: {}'.format(submission.id))
					else:
						logger.debug('Skip: item was seen or timestamp was supplanted: {}'.format(submission.id))
					continue
				check_time += control_checkpoint_progression(submission.created_utc - check_time)
				seen_deque.append(submission.id)

				if not submission.is_self:
					logger.debug('Skip: link submission: {}'.format(submission.permalink))
					continue

				# Rough check to see if bot hasn't replied already
				submission.comments.replace_more(limit=0)
				if any(1 for comment in submission.comments if comment.author == me):
					logger.debug('Skip: already replied to: {}'.format(submission.permalink))
					continue

				b = match_control.check_all(submission.selftext)
				if b == 0:
					logger.debug('Skip: no match: {}'.format(submission.permalink))
					continue

				if reply_shear.enabled:
					if reply_shear.pitch > 0:
						time_time = time.time()
						while time_time - reply_shear.focus > reply_shear.distance:
							reply_shear.pitch -= 1
							reply_shear.focus += reply_shear.distance

						if reply_shear.pitch > reply_shear.threshold:
							logger.error('Quit: bot made too many responses over time')
							raise SystemExit(1)

				logger.info('Match (by /u/{}): {}'.format(submission.author.name, submission.permalink))


				reply = submission_reply(submission, b)
				record_submission_reply(submission, reply, b)


				if reply_shear.enabled:
					if reply_shear.pitch == 0:
						reply_shear.focus = time.time()
					reply_shear.pitch += 1

		except (praw.exceptions.PRAWException, prawcore.exceptions.PrawcoreException) as e:
			if isinstance(e, praw.exceptions.APIException):
				if e.error_type == 'RATELIMIT':
					logger.info('Exception: ratelimit exceeded: {}'.format(e.message), exc_info=True)
					time.sleep(11*60)
				else:
					logger.warning('Exception: unhandled PRAW APIException exception:', exc_info=True)

			elif isinstance(e, prawcore.exceptions.ResponseException):
				logger.info('Exception: ResponseException: {}'.format(e.response), exc_info=True)
				time.sleep(5)

			elif isinstance(e, prawcore.exceptions.RequestException):
				logger.info('Exception: RequestException: {}'.format(e.original_exception), exc_info=True)
				time.sleep(5)

			else:
				logger.warning('Exception: unhandled PRAW exception:', exc_info=True)

		except Exception:
			logger.error('Exception: unhandled exception:', exc_info=True)

register = {
	'name': 'BatchBot',
	'author': 'Pyprohly',
	'owner': 'Pyprohly',
	'version': None,
	'description': __doc__,
	'license': 'MIT License',
	'target_subreddits': ['Pyprohly_test3']
}

praw_config = {
	'site_name': 'BatchBot',
	'client_id': None,
	'client_secret': None,
	'username': 'BatchBot',
	'password': None,
	'user_agent': 'BatchBot by /u/Pyprohly'
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
