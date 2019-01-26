
import sqlite3

db_file = './reply.db'

def get_connection():
	con = sqlite3.connect(db_file)
	con.row_factory = sqlite3.Row
	return con

db = get_connection()

def create_database():
	db.executescript('''CREATE TABLE IF NOT EXISTS t3_reply (
	id INTEGER PRIMARY KEY,
	target_id TEXT UNIQUE,
	reply_id TEXT,
	target_created_utc INTEGER,
	content_flags INTEGER,
	is_set BOOLEAN,
	is_obstructed BOOLEAN,
	CHECK (is_set IN (0, 1)),
	CHECK (is_obstructed IN (0, 1))
);
''')
	db.commit()

if __name__ != '__main__':
	create_database()
