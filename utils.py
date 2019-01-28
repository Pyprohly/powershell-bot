
import sqlite3
from messages import MessageBank, messages
from regex_checks import MatchBank
from schema import get_connection

def get_message(topic_flags, **kwargs):
	if topic_flags & MatchBank.inline_code_misuse:
		return messages[MessageBank.inline_code_misuse](**kwargs)
	elif topic_flags & MatchBank.missing_code_block:
		return messages[MessageBank.code_block_needed](**kwargs)
	return None

def record_submission_reply(submission, comment_reply, topic_flags=0):
	target_id = submission.id
	reply_id = comment_reply.id
	target_created = submission.created_utc

	db = get_connection()

	sql = 'SELECT 1 FROM t3_reply WHERE target_id=?'
	c = db.execute(sql, (target_id,))
	if c.fetchone():
		# This shouldn't happen, but update the fields just in case

		sql = '''UPDATE t3_reply SET reply_id=?,
		target_created=?,
		topic_flags=?,
		is_set=?,
		is_obstructed=?,
		is_satisfied=?
WHERE target_id=?
'''
		with db:
			db.execute(sql, (reply_id, target_created, topic_flags, 1, 0, 0, target_id))

	else:
		sql = '''INSERT INTO t3_reply (
	target_id,
	reply_id,
	target_created,
	topic_flags,
	is_set,
	is_obstructed,
	is_satisfied)
VALUES (?,?,?,?,?,?,?)
'''

		with db:
			db.execute(sql, (target_id, reply_id, target_created, topic_flags, 1, 0, 0))
