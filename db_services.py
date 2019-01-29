
import sqlite3
from types import SimpleNamespace
from schema import get_connection

db = get_connection()

forget_after = 60 * 60 * 24 * 7 # 7 days
forget_acknowledged_after = 60 * 60 * 24 * 100# 1 day

sql_lines = SimpleNamespace()
sql_lines.is_set_0 = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
sql_lines.is_ignored_1 = 'UPDATE t3_reply SET is_ignored=1 WHERE target_id=?'
sql_lines.is_deletable_0 = 'UPDATE t3_reply SET is_deletable=0 WHERE target_id=?'
sql_lines.topic_flags = 'UPDATE t3_reply SET topic_flags=? WHERE target_id=?'
sql_lines.previous_topic_flags = 'UPDATE t3_reply SET previous_topic_flags=? WHERE target_id=?'
sql_lines.revisit = '''SELECT *
FROM t3_reply
WHERE is_set = 1 AND is_ignored = 0
		AND ((
				topic_flags = 0 AND ((strftime('%s', 'now') - target_created) <= {0})
			) OR (
				topic_flags != 0 AND ((strftime('%s', 'now') - target_created) <= {1})
			))
'''.format(forget_acknowledged_after, forget_after)
sql_lines.record_submission_reply_update = '''UPDATE t3_reply SET reply_id=?,
		target_created=?,
		topic_flags=?,
		previous_topic_flags=?,
		is_set=?,
		is_ignored=?,
		is_deletable=?
WHERE target_id=?
'''
sql_lines.record_submission_reply_insert = '''INSERT INTO t3_reply (
	target_id,
	reply_id,
	target_created,
	topic_flags,
	previous_topic_flags,
	is_set,
	is_ignored,
	is_deletable)
VALUES (?,?,?,?,?,?,?,?)
'''

def record_submission_reply(submission, comment_reply, topic_flags=0):
	target_id = submission.id
	reply_id = comment_reply.id
	target_created = submission.created_utc

	db = get_connection()

	sql = 'SELECT 1 FROM t3_reply WHERE target_id=?'
	c = db.execute(sql, (target_id,))
	if c.fetchone():
		# The target id is already in the database.
		# This shouldn't happen, but update the fields just in case.

		with db:
			db.execute(sql_lines.record_submission_reply_update, (reply_id, target_created, topic_flags, None, 1, 0, 1, target_id))

	else:
		with db:
			db.execute(sql_lines.record_submission_reply_insert, (target_id, reply_id, target_created, topic_flags, None, 1, 0, 1))

def revisit():
	c = db.execute(sql_lines.revisit)
	for row in c:
		yield row

def get_t3_target_id(t1_reply_id):
	sql = 'SELECT target_id FROM t3_reply WHERE reply_id=?'
	c = db.execute(sql, (t1_reply_id,))
	result = c.fetchone()
	if result is None:
		return None
	return result['target_id']

def is_deletable(t1_reply_id):
	sql = 'SELECT is_deletable FROM t3_reply WHERE reply_id=?'
	c = db.execute(sql, (t1_reply_id,))
	result = c.fetchone()
	if result is None:
		return True
	return bool(result['is_deletable'])

def assign_is_set_0(target_id):
	with db:
		db.execute(sql_lines.is_set_0, (target_id,))

def assign_is_ignored_1(target_id):
	with db:
		db.execute(sql_lines.is_ignored_1, (target_id,))

def assign_is_deletable_0(target_id):
	with db:
		db.execute(sql_lines.is_deletable_0, (target_id,))

def assign_topic_flags(topic_flags, target_id):
	with db:
		db.execute(sql_lines.topic_flags, (topic_flags, target_id))

def assign_previous_topic_flags(topic_flags, target_id):
	with db:
		db.execute(sql_lines.previous_topic_flags, (topic_flags, target_id))
