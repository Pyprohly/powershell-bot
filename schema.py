
from sqlalchemy.schema import Table, MetaData, Column
from sqlalchemy.types import Integer, String, Boolean
from sqlalchemy.engine import create_engine

db_url = 'sqlite:///database.db'
engine = create_engine(db_url, echo=False)

metadata = MetaData()
t3_reply = Table('t3_reply', metadata,
		Column('id', Integer, primary_key=True),
		Column('target_id', String(8), unique=True),
		Column('reply_id', String(8)),
		Column('target_created', Integer),
		Column('topic_flags', Integer),
		Column('previous_topic_flags', Integer),
		Column('is_set', Boolean),
		Column('is_ignored', Boolean),
		Column('is_deletable', Boolean))

def create_database():
	metadata.create_all(engine)

if __name__ != '__main__':
	create_database()
