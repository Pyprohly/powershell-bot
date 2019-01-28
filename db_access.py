
import sqlite3
from schema import get_connection

db = get_connection()

def get_t3_target_id(t1_reply_id):
	with db:
		sql = 'SELECT target_id FROM t3_reply WHERE reply_id=?'
		c = db.execute(sql, (t1_reply_id,))
		result = c.fetchone()
		if result is None:
			return None
		return result['target_id']
