
from enum import Enum, auto
from string import Template
from urllib.parse import urlencode

from regex_checks import MatchBank

class MessageRegister:
	def __init__(self, dispatch_table=None):
		self.dispatch = dict() if dispatch_table is None else dispatch_table

	def register(self, ref):
		def decorator(func):
			self.dispatch[ref] = func
			return func
		return decorator

	def get(self, ref):
		return self.dispatch.get(ref)

	def __getitem__(self, ref):
		return self.dispatch[ref]

messages = MessageRegister()

class MessageBank(Enum):
	code_block_needed = auto()
	multiline_inline_code = auto()

class MessageInventory:
	code_block_missing_message = '''Looks like your PowerShell code isn’t wrapped in a code block.

To format code correctly on **new.reddit.com**, highlight the code and select *‘Code Block’* in the editing toolbar.

If you’re on **old.reddit.com**, separate the code from your text with a blank line and precede each line of code with **4 spaces** or a **tab**.
'''

	inline_code_message = '''Hi ${redditor},

Looks like you used *inline code* formatting where a **code block** should have been used.

The inline code text styling is for use in paragraphs of text. For larger sequences of code, consider using a code block. This can be done by selecting your code then clicking the *‘Code Block’* button.
'''

	message_break = '\n---\n\n'

	signature_beep_boop = '*Beep-boop, I am a bot.*'
	signature_delete = '[Remove-Item]'
	delete_message = (
			'Deletion requests can only be made by the OP. A comment with replies on it cannot be removed.\n')

	describing_message = '''\tDescribing ${fixture_name}
\t[${passing}] Demonstrates good markdown
\tPassed: ${passed_count} Failed: ${failed_count}
'''

	def code_block(**kwargs):
		st = Template(MessageInventory.code_block_missing_message)
		return st.substitute(kwargs)

	def inline_code(**kwargs):
		st = Template(MessageInventory.inline_code_message)
		return st.substitute(kwargs)

	def signature(*, delete_message_url=None, **kwargs):
		sig_items = [MessageInventory.signature_beep_boop]
		if delete_message_url:
			sig_items.append(MessageInventory.signature_delete)

		sb = '^(' + ' | '.join(sig_items) + ')'

		if delete_message_url:
			sb += '\n\n{}: {}'.format(MessageInventory.signature_delete, delete_message_url)
		return sb

	def describing(*, fixture_name='Thing', passed=False, **kwargs):
		st = Template(MessageInventory.describing_message)
		subs = {
			'fixture_name': fixture_name,
			'passing': '\N{WHITE HEAVY CHECK MARK}' if passed else '\N{CROSS MARK}',
			'passed_count': 1 if passed else 0,
			'failed_count': 0 if passed else 1
		}
		s = st.substitute(subs)
		return s

class MessageMaker:
	def _get_signature(num=1, **kwargs):
		sig = ''
		if num == 1:
			# Basic signature
			sig = MessageInventory.signature()
		elif num == 2:
			# With delete button
			redditor = kwargs.pop('redditor')
			reddit_url = kwargs.pop('reddit_url', 'https://www.reddit.com')
			message_compose_url = '{}/message/compose'.format(reddit_url)
			query_args = dict(
				to = kwargs.pop('bot_name'),
				subject = '!delete %s' % kwargs.pop('reply_id'),
				message = Template(MessageInventory.delete_message).substitute(redditor=redditor)
			)
			delete_message_url = message_compose_url + '?' + urlencode(query_args)

			sig = MessageInventory.signature(delete_message_url=delete_message_url)

		return sig

	def _get_fake_pester(**kwargs):
		describing_kwargs = {
			'fixture_name': kwargs.pop('thing_kind', 'Thing'),
			'passed': kwargs.pop('passed', False)
		}
		return MessageInventory.describing(**describing_kwargs)

	@messages.register(MessageBank.code_block_needed)
	def code_block_needed(*, signature=1, pester=True, **kwargs):
		sb = MessageInventory.code_block(**kwargs)

		if pester:
			sb += MessageInventory.message_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		if signature:
			sb += MessageInventory.message_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		sb += '\n'
		return sb

	@messages.register(MessageBank.multiline_inline_code)
	def multiline_inline_code(*, signature=1, pester=True, **kwargs):
		sb = MessageInventory.inline_code(**kwargs)

		if pester:
			sb += MessageInventory.message_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		if signature:
			sb += MessageInventory.message_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		sb += '\n'
		return sb

def get_message(topic_flags, **kwargs):
	if topic_flags & MatchBank.multiline_inline_code:
		return messages[MessageBank.multiline_inline_code](**kwargs)
	elif topic_flags & MatchBank.very_long_inline_code:
		return messages[MessageBank.multiline_inline_code](**kwargs)
	elif topic_flags & MatchBank.missing_code_block:
		return messages[MessageBank.code_block_needed](**kwargs)
	return None
