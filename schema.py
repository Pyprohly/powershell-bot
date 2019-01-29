
import sqlite3

db_file = './database.db'

def get_connection():
	con = sqlite3.connect(db_file)
	con.row_factory = sqlite3.Row
	return con

def create_database():
	db = get_connection()
	db.executescript('''CREATE TABLE IF NOT EXISTS t3_reply (
	id INTEGER PRIMARY KEY,
	target_id TEXT UNIQUE,
	reply_id TEXT,
	target_created INTEGER,
	topic_flags INTEGER,
	previous_topic_flags INTEGER,
	is_set BOOLEAN,
	is_ignored BOOLEAN,
	is_deletable BOOLEAN,
	CHECK (is_set IN (0, 1)),
	CHECK (is_ignored IN (0, 1)),
	CHECK (is_deletable IN (0, 1)))
);
''')
	db.commit()

if __name__ != '__main__':
	create_database()
