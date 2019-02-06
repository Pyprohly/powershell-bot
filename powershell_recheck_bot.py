#!/usr/bin/env python3

"""Go back on previous posts where the bot has replied and amend the bot's message if needed."""

def main():
	import os
	import time
	import logging, logging.handlers
	from pathlib import Path
	import praw, prawcore

	from reddit import reddit
	import db_services
	from regex_checks import TopicFlags, ExtraFlags, match_control
	from messages import get_message

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

	me = reddit.user.me()

	sleep_seconds = 30

	while True:
		try:
			for row in db_services.revisit():
				target_id = row['target_id']
				reply_id = row['reply_id']
				topic_flags = row['topic_flags']
				extra_flags = row['extra_flags']

				logger.debug(f'Recheck: t1_{reply_id} targeting t3_{target_id}')

				submission = reddit.submission(target_id)
				try:
					submission._fetch()
				except prawcore.exceptions.NotFound:
					# This shouldn't happen, even if the submission was deleted.
					# Avoid processing it in future.
					logger.warning('Skip: recorded submission not found: t3_{}'.format(target_id))
					db_services.assign_is_set_0(target_id)
					continue

				if not submission.is_self:
					# This shouldn't happen.
					logger.warning('Note: non-is_self submission: {}-{}'.format(target_id, reply_id))
					db_services.assign_is_ignored_1(target_id)
					continue

				is_deleted = submission.author is None and submission.selftext == '[deleted]'
				is_removed = submission.selftext == '[removed]'
				if is_deleted or is_removed:
					if is_deleted:
						logger.info('Skip: submission was deleted: {}-{}'.format(target_id, reply_id))
					elif is_removed:
						logger.info('Skip: submission was removed: {}-{}'.format(target_id, reply_id))
					db_services.assign_is_ignored_1(target_id)
					continue

				match_control.check_all(submission.selftext)
				b = match_control[TopicFlags]
				y = match_control[ExtraFlags]

				state_flags_change = (b != topic_flags) or (y != extra_flags)
				if not state_flags_change:
					logger.debug('Skip: no change: {}-{}'.format(target_id, reply_id))
					continue

				my_comment = reddit.comment(reply_id)
				try:
					my_comment.refresh()
				except praw.exceptions.PRAWException:
					# The comment has disappeared. It may have been deleted.
					logger.warning(f'Warning: missing comment: {target_id}-{reply_id}')
					db_services.assign_is_set_0(target_id)
					continue

				if len(my_comment.replies):
					logger.info(f'Info: found replies on comment: {target_id}-{reply_id}')
					db_services.assign_is_deletable_0(target_id)

				message_kwargs = {
					'signature': 2,
					'pester': True,
					'some': bool(y & ExtraFlags.contains_code_block),
					'thing_kind': type(submission).__name__,
					'redditor': submission.author.name,
					'bot_name': me.name,
					'reply_id': my_comment.id,
					'old_reddit_permalink': 'https://old.reddit.com' + submission.permalink,
					'new_reddit_permalink': 'https://new.reddit.com' + submission.permalink
				}

				topic_flags_0 = b == 0
				if topic_flags_0:
					# The author has fixed their post. Success!

					message_kwargs.update({
						'topic_flags': topic_flags,
						'passed': True
					})

					message = get_message(**message_kwargs)
					my_comment.edit(message)
					logger.info(f'Success: update comment (passing): {target_id}-{reply_id}')
				else:
					# topic_flags have changed but markdown still not fixed yet.

					message_kwargs.update({
						'topic_flags': b,
						'passed': False
					})

					message = get_message(**message_kwargs)
					my_comment.edit(message)
					logger.info(f'Success: update comment (failing): {target_id}-{reply_id}')

				db_services.assign_topic_flags(b, target_id)
				db_services.assign_previous_topic_flags(topic_flags, target_id)
				db_services.assign_extra_flags(y, target_id)

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

register = {
	'name': 'PowerShell-Bot',
	'component': 'recheck',
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
