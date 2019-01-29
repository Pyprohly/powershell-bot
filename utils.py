
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
