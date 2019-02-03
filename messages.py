
from enum import Enum, auto
from string import Template
from urllib.parse import urlencode

from regex_checks import TopicFlags

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
	long_inline_code = auto()
	code_fence = auto()

class MessageInventory:
	code_outside_of_code_block_message = '''Looks like your PowerShell code isn’t wrapped in a code block.

To format code correctly on **new reddit** (*[new.reddit.com]*), highlight the code and select *‘Code Block’* in the editing toolbar.

If you’re on **[old.reddit.com]**, separate the code from your text with a blank line and precede each line of code with **4 spaces** or a **tab**.

[old.reddit.com]: ${old_reddit_permalink}
[new.reddit.com]: ${new_reddit_permalink}
'''

	some_code_outside_of_code_block_message = '''Some of your PowerShell code isn’t wrapped in a code block.

To format code correctly on **new reddit** (*[new.reddit.com]*), highlight *all lines* of code and select *‘Code Block’* in the editing toolbar.

If you’re on **[old.reddit.com]**, separate the code from your text with a blank line and precede *each line* of code with **4 spaces** or a **tab**.

[old.reddit.com]: ${old_reddit_permalink}
[new.reddit.com]: ${new_reddit_permalink}
'''

	inline_code_message = '''Looks like you used *inline code* formatting where a **code block** should have been used.

The inline code text styling is for use in paragraphs of text. For larger sequences of code, consider using a code block. This can be done by selecting your code then clicking the *‘Code Block’* button.
'''

	long_inline_code_message = '''That’s a very long stretch of inline code.

Note that on **[old.reddit.com]** inline code blocks do not word wrap, making it difficult for many of us to see all your code.

To ensure your code is readable by everyone, on **new reddit** (*[new.reddit.com]*), highlight the code and select *‘Code Block’* in the editing toolbar.

If you’re on **[old.reddit.com]**, separate the code from your text with a blank line and precede each line of code with **4 spaces** or a **tab**.

[old.reddit.com]: ${old_reddit_permalink}
[new.reddit.com]: ${new_reddit_permalink}
'''

	code_fence_message = '''Code fences are a new feature on reddit and won’t render for those viewing your post on **[old.reddit.com]**. Because of this its use is discouraged.

If you want those viewing from old reddit to see formatted PowerShell code then consider using a regular **code block**. This can be easily be done on **new reddit** (*[new.reddit.com]*) by highlighting your code and selecting *‘Code Block’* in the editing toolbar.

[old.reddit.com]: ${old_reddit_permalink}
[new.reddit.com]: ${new_reddit_permalink}
'''

	thematic_break = '\n---\n\n'

	beep_boop = '*Beep-boop. I am a bot.*'
	delete_button = '[Remove-Item]'
	delete_message = 'Deletion requests can only be made by the OP. A comment with replies on it cannot be removed.\n'

	describing_message = '''\tDescribing ${fixture}
\t[${passing}] Demonstrates good markdown
\tPassed: ${passed_count} Failed: ${failed_count}
'''

	def code_block(some=False, **kwargs):
		st = None
		if some:
			st = Template(MessageInventory.some_code_outside_of_code_block_message)
		else:
			st = Template(MessageInventory.code_outside_of_code_block_message)
		return st.substitute(kwargs)

	def inline_code(**kwargs):
		st = Template(MessageInventory.inline_code_message)
		return st.substitute(kwargs)

	def long_inline_code(**kwargs):
		st = Template(MessageInventory.long_inline_code_message)
		return st.substitute(kwargs)

	def code_fence(**kwargs):
		st = Template(MessageInventory.code_fence_message)
		return st.substitute(kwargs)

	def signature(*, delete_message_url=None, **kwargs):
		sig_items = [MessageInventory.beep_boop]
		if delete_message_url:
			sig_items.append(MessageInventory.delete_button)

		sb = '^(' + ' | '.join(sig_items) + ')'

		if delete_message_url:
			sb += '\n\n{}: {}'.format(MessageInventory.delete_button, delete_message_url)
		return sb

	def describing(*, fixture='Thing', passed=0, **kwargs):
		st = Template(MessageInventory.describing_message)

		subs = dict.fromkeys(['fixture', 'passing', 'passed_count', 'failed_count'])
		subs['fixture'] = fixture
		subs['passing'] = '\N{CROSS MARK}'
		subs['passed_count'] = '0'
		subs['failed_count'] = '1'
		if passed == 1:
			subs['passing'] = '\N{WHITE HEAVY CHECK MARK}'
			subs['passed_count'] = '1'
			subs['failed_count'] = '0'
		elif passed == 2:
			subs['passing'] = '\N{WARNING SIGN}\N{VARIATION SELECTOR-16}'
			subs['passed_count'] = '0.5'
			subs['failed_count'] = '0.5'

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
			reddit_url = kwargs.pop('reddit_url', 'https://www.reddit.com')
			message_compose_url = f'{reddit_url}/message/compose'
			query_args = {
				'to': kwargs.pop('bot_name'),
				'subject': '!delete t1_%s' % kwargs.pop('reply_id'),
				'message': MessageInventory.delete_message
			}
			delete_message_url = message_compose_url + '?' + urlencode(query_args)

			sig = MessageInventory.signature(delete_message_url=delete_message_url)
		return sig + '\n'

	def _get_fake_pester(**kwargs):
		describing_kwargs = {
			'fixture': kwargs.pop('thing_kind', 'Thing'),
			'passed': kwargs.pop('passed', 0)
		}
		return MessageInventory.describing(**describing_kwargs)

	@messages.register(MessageBank.code_block_needed)
	def code_block_needed(**kwargs):
		sb = MessageInventory.code_block(**kwargs)

		if kwargs.pop('pester', False):
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		signature = kwargs.pop('signature', 0)
		if signature:
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		return sb

	@messages.register(MessageBank.multiline_inline_code)
	def multiline_inline_code(**kwargs):
		sb = MessageInventory.inline_code(**kwargs)

		if kwargs.pop('pester', False):
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		signature = kwargs.pop('signature', 0)
		if signature:
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		return sb

	@messages.register(MessageBank.long_inline_code)
	def long_inline_code(**kwargs):
		sb = MessageInventory.long_inline_code(**kwargs)

		if kwargs.pop('pester', False):
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		signature = kwargs.pop('signature', 0)
		if signature:
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		return sb

	@messages.register(MessageBank.code_fence)
	def code_fence(**kwargs):
		sb = MessageInventory.code_fence(**kwargs)

		if kwargs.pop('pester', False):
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_fake_pester(**kwargs)
		signature = kwargs.pop('signature', 0)
		if signature:
			sb += MessageInventory.thematic_break
			sb += MessageMaker._get_signature(signature, **kwargs)

		return sb

def get_message(topic_flags, **kwargs):
	fence_flags = topic_flags & (TopicFlags.code_outside_of_code_block | TopicFlags.code_fence) \
			== (TopicFlags.code_outside_of_code_block | TopicFlags.code_fence)
	if fence_flags:
		passed = 1 if kwargs.pop('passed', False) else 2
		return messages[MessageBank.code_fence](passed=passed, **kwargs)
	else:
		passed = int(kwargs.pop('passed', False))
		if topic_flags & TopicFlags.multiline_inline_code:
			return messages[MessageBank.multiline_inline_code](passed=passed, **kwargs)
		elif topic_flags & TopicFlags.very_long_inline_code:
			return messages[MessageBank.long_inline_code](passed=passed, **kwargs)
		elif topic_flags & TopicFlags.code_outside_of_code_block:
			return messages[MessageBank.code_block_needed](passed=passed, **kwargs)

	return None
