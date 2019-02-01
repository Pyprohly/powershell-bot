#!/usr/bin/env python3

"""Update a reply message appropriately when the redditor changes their post."""

import os
import time
import logging, logging.handlers
from pathlib import Path
import praw, prawcore

from regex_checks import match_control
from config import praw_config
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

	reddit = praw.Reddit(**praw_config)
	me = reddit.user.me()

	sleep_seconds = 30

	while True:
		try:
			for row in db_services.revisit():
				target_id = row['target_id']
				reply_id = row['reply_id']
				topic_flags = row['topic_flags']

				submission = reddit.submission(target_id)
				try:
					submission._fetch()
				except prawcore.exceptions.NotFound:
					# This should never happen, even if the submission was deleted.
					# Avoid processing it in future.
					logger.warning('Skip: recorded submission not found: t3_{}'.format(target_id))

					db_services.assign_is_set_0(target_id)
					continue

				if not submission.is_self:
					# This shouldn't happen.
					logger.warning('Note: non-is_self submission: t3_{}'.format(target_id))

					db_services.assign_is_ignored_1(target_id)
					continue

				is_deleted = submission.author is None and submission.selftext == '[deleted]'
				is_removed = submission.selftext == '[removed]'
				if is_deleted or is_removed:
					if is_deleted:
						logger.info('Skip: submission was deleted: t3_{}'.format(target_id))
					elif is_removed:
						logger.info('Skip: submission was removed: t3_{}'.format(target_id))

					db_services.assign_is_ignored_1(target_id)
					continue

				b = match_control.check_all(submission.selftext)

				topic_flags_changed = b != topic_flags
				if not topic_flags_changed:
					logger.debug('Skip: no change: t3_{}'.format(target_id))
					continue

				my_comment = reddit.comment(reply_id)
				try:
					my_comment.refresh()
				except praw.exceptions.PRAWException:
					# The comment has disappeared. It may have been deleted.
					db_services.assign_is_set_0(target_id)
					continue

				if len(my_comment.replies):
					logger.info(f'Info: found replies on comment t1_`{reply_id}`')

					db_services.assign_is_deletable_0(target_id)

				topic_flags_0 = b == 0
				if topic_flags_0:
					# The author has fixed their post. Success!

					if time.time() - submission.created_utc < 60 * 3:
						# If they've ninja edited then just delete the post.

						if len(my_comment.replies):
							logger.info(f'Skip: ninja edited, but there are replies: t1_`{reply_id}`')
							continue
						if not db_services.is_deletable(reply_id):
							logger.info(f'Skip: ninja edited, but not deletable: t1_`{reply_id}`')
							continue

						my_comment.delete()
						db_services.assign_is_set_0(target_id)
						logger.info(f'Success: delete, ninja edited: t1_`{reply_id}`')
						continue

					message = get_message(topic_flags,
							signature=2,
							passed=True,
							thing_kind=type(submission).__name__,
							redditor=submission.author.name,
							bot_name=me.name,
							reply_id=my_comment.id)
					my_comment.edit(message)
					logger.info(f'Success: update comment (passing) t1_`{reply_id}`')
				else:
					# topic_flags have changed but markdown still not fixed yet.
					message = get_message(b,
							signature=2,
							passed=False,
							thing_kind=type(submission).__name__,
							redditor=submission.author.name,
							bot_name=me.name,
							reply_id=my_comment.id)
					my_comment.edit(message)
					logger.info(f'Success: update comment (failing) t1_`{reply_id}`')

				db_services.assign_topic_flags(b, target_id)
				db_services.assign_previous_topic_flags(topic_flags, target_id)

			time.sleep(sleep_seconds)

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

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
