
import sqlite3

db_file = './reply.db'

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
	is_set BOOLEAN, -- Is 1 when the bot's reply is exposed.
	is_obstructed BOOLEAN, -- Is 1 when a redditor replies to the bot's comment.
	is_satisfied BOOLEAN, -- Is 1 when the author fixes their Markdown.
	CHECK (is_set IN (0, 1)),
	CHECK (is_obstructed IN (0, 1)),
	CHECK (is_satisfied IN (0, 1))
);
''')
	db.commit()

if __name__ != '__main__':
	create_database()
