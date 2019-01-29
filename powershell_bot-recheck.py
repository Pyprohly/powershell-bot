#!/usr/bin/env python3

"""Update a reply message appropriately when the redditor changes their post."""

import os
import time
import logging, logging.handlers
from pathlib import Path
from types import SimpleNamespace
import praw, prawcore

from schema import get_connection
from regex_checks import MatchBank, match_control
from config import praw_config
from utils import get_message

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
	me = reddit.user.me()

	sleep_seconds = 30

	forget_after = 60 * 60 * 24 * 10 # 10 days

	sqll = SimpleNamespace()
	sqll.is_set_0 = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
	sqll.is_ignored_1 = 'UPDATE t3_reply SET is_ignored=1 WHERE target_id=?'
	sqll.is_obstructed_1 = 'UPDATE t3_reply SET is_obstructed=1 WHERE target_id=?'
	sqll.is_satisfied_1 = 'UPDATE t3_reply SET is_satisfied=1 WHERE target_id=?'
	sqll.topic_flags = 'UPDATE t3_reply SET topic_flags=? WHERE target_id=?'
	sqll.revisit = '''SELECT *
FROM t3_reply
WHERE is_set = 1 AND is_ignored = 0 AND is_satisfied = 0
		AND (strftime('%s', 'now') - target_created) <= {}
'''.format(forget_after)
	db = get_connection()

	while True:
		try:
			c = db.execute(sqll.revisit)
			for row in c:
				target_id = row['target_id']
				reply_id = row['reply_id']
				topic_flags = row['topic_flags']

				submission = reddit.submission(target_id)
				try:
					submission._fetch()
				except prawcore.exceptions.NotFound:
					# This should never happen, even if the submission was deleted.
					# Avoid processing it in future.
					logger.warning('Skip: recorded submission not found: {}'.format(target_id))

					with db:
						db.execute(sqll.is_set_0, (target_id,))
					continue

				if not submission.is_self:
					# This shouldn't happen.
					logger.warning('Note: non-is_self submission: {}'.format(target_id))

					with db:
						db.execute(sqll.is_ignored_1, (target_id,))
					continue

				is_deleted = submission.author is None and submission.selftext == '[deleted]'
				is_removed = submission.selftext == '[removed]'
				if is_deleted or is_removed:
					if is_deleted:
						logger.info('Skip: submission was deleted: {}'.format(target_id))
					elif is_removed:
						logger.info('Skip: submission was removed: {}'.format(target_id))

					with db:
						db.execute(sqll.is_ignored_1, (target_id,))
					continue

				b = match_control.check_all(submission.selftext)
				topic_flags_0 = b == 0
				topic_flags_changed = b != topic_flags

				if topic_flags_0 or topic_flags_changed:
					my_comment = reddit.comment(reply_id)
					try:
						my_comment.refresh()
					except praw.exceptions.PRAWException:
						# The comment has disappeared. It may have been deleted.
						with db:
							db.execute(sqll.is_set_0, (target_id,))
						continue

					if len(my_comment.replies):
						logger.info(f'Info: found replies on comment `{reply_id}`')

						with db:
							db.execute(sqll.is_obstructed_1, (target_id,))

					if topic_flags_0:
						# The author has fixed their post. Success!

						message = get_message(topic_flags,
								signature=2,
								passed=True,
								thing_kind=type(submission).__name__,
								redditor=submission.author.name,
								bot_name=me.name,
								reply_id=my_comment.id)
						my_comment.edit(message)

						with db:
							db.execute(sqll.is_satisfied_1, (target_id,))

						logger.info(f'Success: update comment (passing) `{reply_id}`')

					elif topic_flags_changed:
						message = get_message(b,
								signature=2,
								passed=False,
								thing_kind=type(submission).__name__,
								redditor=submission.author.name,
								bot_name=me.name,
								reply_id=my_comment.id)
						my_comment.edit(message)

						with db:
							db.execute(sqll.topic_flags, (b, target_id))

						logger.info(f'Success: update comment (failing) `{reply_id}`')

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

		except Exception:
			logger.error('Exception: unhandled exception:', exc_info=True)

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
