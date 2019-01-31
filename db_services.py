
import time
from types import SimpleNamespace
from sqlalchemy.sql import select, insert, update, exists, bindparam, and_
from schema import engine, t3_reply

forget_after = 60 * 60 * 24 * 3 # 3 days

sql_lines = SimpleNamespace()
sql_lines.is_set_0 = update(t3_reply).values(is_set=0).where(t3_reply.c.target_id == bindparam('b_target_id'))
sql_lines.is_ignored_1 = update(t3_reply).values(is_ignored=1).where(t3_reply.c.target_id == bindparam('b_target_id'))
sql_lines.is_deletable_0 = update(t3_reply).values(is_deletable=0).where(t3_reply.c.target_id == bindparam('b_target_id'))
sql_lines.topic_flags = update(t3_reply).values(topic_flags=bindparam('b_topic_flags')).where(t3_reply.c.target_id == bindparam('b_target_id'))
sql_lines.previous_topic_flags = update(t3_reply).values(previous_topic_flags=bindparam('b_previous_topic_flags')).where(t3_reply.c.target_id == bindparam('b_target_id'))

sql_lines.revisit = select([t3_reply]) \
		.where(
			and_(
				t3_reply.c.is_set == 1,
				t3_reply.c.is_ignored == 0,
				bindparam('b_current_epoch') - t3_reply.c.target_created <= forget_after))

sql_lines.record_submission_reply_update = update(t3_reply) \
		.values(
			reply_id=bindparam('b_reply_id'),
			target_created=bindparam('b_target_created'),
			topic_flags=bindparam('b_topic_flags'),
			previous_topic_flags=bindparam('b_previous_topic_flags'),
			is_set=bindparam('b_is_set'),
			is_ignored=bindparam('b_is_ignored'),
			is_deletable=bindparam('b_is_deletable')) \
		.where(t3_reply.c.target_id == bindparam('b_target_id'))

sql_lines.record_submission_reply_insert = insert(t3_reply) \
		.values(
			target_id=bindparam('b_target_id'),
			reply_id=bindparam('b_reply_id'),
			target_created=bindparam('b_target_created'),
			topic_flags=bindparam('b_topic_flags'),
			previous_topic_flags=bindparam('b_previous_topic_flags'),
			is_set=bindparam('b_is_set'),
			is_ignored=bindparam('b_is_ignored'),
			is_deletable=bindparam('b_is_deletable'))

sql_lines.target_id_exists = exists().where(t3_reply.c.target_id == bindparam('b_target_id')).select()

def record_submission_reply(submission, comment_reply, topic_flags=0):
	target_id = submission.id
	reply_id = comment_reply.id
	target_created = submission.created_utc

	with engine.connect() as conn:
		result = conn.execute(sql_lines.target_id_exists, b_target_id=target_id)
		row = result.first()
	if row[0]:
		# The target id is already in the database.
		# This shouldn't happen, but update the fields just in case.

		with engine.connect() as conn:
			conn.execute(sql_lines.record_submission_reply_update,
					b_reply_id=reply_id,
					b_target_created=target_created,
					b_topic_flags=topic_flags,
					b_previous_topic_flags=None,
					b_is_set=1,
					b_is_ignored=0,
					b_is_deletable=1,
					b_target_id=target_id)
	else:
		with engine.connect() as conn:
			conn.execute(sql_lines.record_submission_reply_insert,
				b_target_id=target_id,
				b_reply_id=reply_id,
				b_target_created=target_created,
				b_topic_flags=topic_flags,
				b_previous_topic_flags=None,
				b_is_set=1,
				b_is_ignored=0,
				b_is_deletable=1)

def revisit():
	with engine.connect() as conn:
		results = conn.execute(sql_lines.revisit, b_current_epoch=time.time())
		for row in results:
			yield row

def get_target_id(reply_id):
	sql = select([t3_reply.c.target_id]).where(t3_reply.c.reply_id == reply_id)
	with engine.connect() as conn:
		results = conn.execute(sql)
		row = results.first()
	if row is None:
		return None
	return row[t3_reply.c.target_id]

def is_deletable(reply_id):
	sql = select([t3_reply.c.is_deletable]).where(t3_reply.c.reply_id == reply_id)
	with engine.connect() as conn:
		results = conn.execute(sql)
		row = results.first()
	if row is None:
		return True
	return bool(row[t3_reply.c.is_deletable])

def assign_is_set_0(target_id):
	with engine.connect() as conn:
		conn.execute(sql_lines.is_set_0, b_target_id=target_id)

def assign_is_ignored_1(target_id):
	with engine.connect() as conn:
		conn.execute(sql_lines.is_ignored_1, b_target_id=target_id)

def assign_is_deletable_0(target_id):
	with engine.connect() as conn:
		conn.execute(sql_lines.is_deletable_0, b_target_id=target_id)

def assign_topic_flags(topic_flags, target_id):
	with engine.connect() as conn:
		conn.execute(sql_lines.is_ignored_1, b_topic_flags=topic_flags, b_target_id=target_id)

def assign_previous_topic_flags(topic_flags, target_id):
	with engine.connect() as conn:
		conn.execute(sql_lines.is_ignored_1, b_topic_flags=topic_flags, b_target_id=target_id)
