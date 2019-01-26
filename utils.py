
import sqlite3
from messages import MessageBank, messages
from regex_checks import MatchBank
from schema import get_connection

def submission_reply(submission, flags):
	message = None
	if flags & MatchBank.inline_code_misuse:
		message = messages[MessageBank.inline_code_misuse]()
	elif flags & MatchBank.missing_code_block:
		message = messages[MessageBank.code_block_needed]()

	if message is None:
		return
	return submission.reply(message)

def record_submission_reply(submission, comment_reply, flags=0):
	target_id = submission.id
	reply_id = comment_reply.id
	target_created_utc = submission.created_utc

	db = get_connection()

	sql = 'SELECT 1 FROM t3_reply WHERE target_id=?'
	c = db.execute(sql, (target_id,))
	if c.fetchone():
		# This shouldn't happen, but just in case update the fields

		sql = '''UPDATE t3_reply SET reply_id=?,
		target_created_utc=?,
		content_flags=?,
		is_set=?,
		is_obstructed=?
WHERE target_id=?
'''
		with db:
			db.execute(sql, (reply_id, target_created_utc, flags, 1, 0, target_id))

	else:
		sql = '''INSERT INTO t3_reply (
		target_id,
		reply_id,
		target_created_utc,
		content_flags,
		is_set,
		is_obstructed)
VALUES (?,?,?,?,?,?)
'''

		with db:
			db.execute(sql, (target_id, reply_id, target_created_utc, flags, 1, 0))
