#!/usr/bin/env python3

"""Delete a reply message when the redditor fixes their post."""

import os
import time
import logging, logging.handlers
from pathlib import Path
import praw, prawcore
from schema import get_connection
from regex_checks import MatchBank, match_control
from config import praw_config

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

	reddit = praw.Reddit(**praw_config)

	sleep_seconds = 30

	forget_after = 60 * 60 * 24 * 10 # 10 days

	revisit_sql = '''SELECT *
	FROM t3_reply
	WHERE is_set = 1 AND is_obstructed = 0
			AND (strftime('%s', 'now') - target_created_utc) <= {}
	'''.format(forget_after)
	db = get_connection()

	while 1:
		try:
			c = db.execute(revisit_sql)
			for row in c:
				target_id = row['target_id']
				reply_id = row['reply_id']
				content_flags = row['content_flags']

				submission = reddit.submission(target_id)
				try:
					submission._fetch()
				except prawcore.exceptions.NotFound:
					# This should never happen, even if the submission was deleted.
					logger.warning('Skip: recorded submission not found: {}'.format(target_id))

					with db:
						sql = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
						db.execute(sql, (target_id,))
					continue

				b = match_control.check_all(submission.selftext)
				if b == 0:
					# The author has fixed their post. Success!

					comment = reddit.comment(reply_id)

					try:
						comment.refresh()
					except praw.exceptions.PRAWException:
						# The comment has disappeared. It may have been deleted
						with db:
							sql = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
							db.execute(sql, (target_id,))
						continue

					if len(comment.replies):
						# Don't delete the comment if there are replies
						logger.info(f'Skip: found replies on comment `{reply_id}`')

						with db:
							sql = 'UPDATE t3_reply SET is_obstructed=1 WHERE target_id=?'
							db.execute(sql, (target_id,))
					else:
						comment.delete()

						with db:
							sql = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
							db.execute(sql, (target_id,))

						logger.info(f'Success: deleted comment `{reply_id}`')

				else:
					if b != content_flags:
						with db:
							sql = 'UPDATE t3_reply SET content_flags=? WHERE target_id=?'
							db.execute(sql, (b, target_id))

			time.sleep(sleep_seconds)

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

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
