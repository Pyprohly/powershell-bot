
import sqlite3
from types import SimpleNamespace
from schema import get_connection

db = get_connection()

forget_after = 60 * 60 * 24 * 7 # 7 days

sql_lines = SimpleNamespace()
sql_lines.is_set_0 = 'UPDATE t3_reply SET is_set=0 WHERE target_id=?'
sql_lines.is_ignored_1 = 'UPDATE t3_reply SET is_ignored=1 WHERE target_id=?'
sql_lines.is_deletable_1 = 'UPDATE t3_reply SET is_deletable=1 WHERE target_id=?'
sql_lines.is_acknowledged_1 = 'UPDATE t3_reply SET is_acknowledged=1 WHERE target_id=?'
sql_lines.topic_flags = 'UPDATE t3_reply SET topic_flags=? WHERE target_id=?'
sql_lines.revisit = '''SELECT *
FROM t3_reply
WHERE is_set = 1 AND is_ignored = 0 AND is_acknowledged = 0
		AND (strftime('%s', 'now') - target_created) <= {}
'''.format(forget_after)

def recheck():
	c = db.execute(sql_lines.revisit)
	for row in c:
		yield row

def get_t3_target_id(t1_reply_id):
	with db:
		sql = 'SELECT target_id FROM t3_reply WHERE reply_id=?'
		c = db.execute(sql, (t1_reply_id,))
		result = c.fetchone()
		if result is None:
			return None
		return result['target_id']

def assign_is_set_0(target_id):
	with db:
		db.execute(sql_lines.is_set_0, (target_id,))

def assign_is_ignored_1(target_id):
	with db:
		db.execute(sql_lines.is_ignored_1, (target_id,))

def assign_is_deletable_1(target_id):
	with db:
		db.execute(sql_lines.is_deletable_1, (target_id,))

def assign_is_acknowledged_1(target_id):
	with db:
		db.execute(sql_lines.is_acknowledged_1, (target_id,))

def assign_topic_flags(topic_flags, target_id):
	with db:
		db.execute(sql_lines.topic_flags, (topic_flags, target_id))
