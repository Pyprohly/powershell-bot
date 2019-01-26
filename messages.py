
from enum import Enum, auto
from string import Template

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
	inline_code_misuse = auto()

class MessageStorage:
	code_block = '''Looks like your PowerShell code isn’t wrapped in a code block.

To format code correctly on **new.reddit.com**, highlight the code and select *‘Code Block’* in the editing toolbar.

If you’re on **old.reddit.com**, separate the code from your text with a blank line and precede each line of code with **4 spaces** or a **tab**.

---

^(*Beep-boop. I am a bot.*)
'''

	inline_code = '''Looks like you used *inline code* formatting where a **code block** should have been used.

The inline code text styling is for use in paragraphs of text. For larger sequences of code, consider using a code bock. This can be done by selecting your code then clicking the *‘Code Block’* button.

---

^(*Beep-boop. I am a bot.*)
'''

class MessageData:
	@messages.register(MessageBank.code_block_needed)
	def code_block_needed(example=False, **kws):
		return MessageStorage.code_block_with_example if example else MessageStorage.code_block

	@messages.register(MessageBank.inline_code_misuse)
	def inline_code_misuse(**kws):
		return MessageStorage.inline_code
