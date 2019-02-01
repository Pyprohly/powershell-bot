
import re
from enum import IntEnum

class MatchControl:
	def __init__(self):
		self.match_rules = []

	def add(self, rule):
		self.match_rules.append(rule)

	def check_all(self, haystack):
		b = 0
		for m in self.match_rules:
			if m.test(haystack):
				b |= m.flag
		return b

class MatchRule:
	def __init__(self, name, flag, func):
		self.name = name
		self.flag = flag
		self.func = func

	def test(self, text):
		return self.func(text)

	def __call__(self, *args, **kwargs):
		return self.func(*args, **kwargs)

	@classmethod
	def create(cls, name, flag):
		def decorator(func):
			return cls(name=name, flag=flag, func=func)
		return decorator

class RegexHolder:
	missing_code_block = re.compile((
			r'^ {0,3}('
			r'(function|filter|workflow|class|enum) *[a-z_]\w* *\{'
			r'|(switch|if|foreach) *\([^\)]+\) *\{'
			r'|param *\('
			r'|process *\{'
			r'''|(PS C:\\[-\w\\]*> )?\w{3,}-\w{2,} (-\w+|@?'|@?"|\$[a-z]|[A-F]:\\)'''
			r'|\$[a-z_]\w* *[=\|]'
			r')'), re.I | re.M)

	inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*$', re.M)
	consecutive_inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*\n\n?`.*\n\n?`', re.M)

	code_fence = re.compile(r'^```.*?\n(.*?)```', re.M | re.S)

class MatchBank(IntEnum):
	missing_code_block = 1
	multiline_inline_code = 2
	very_long_inline_code = 4
	code_fence = 8

@MatchRule.create(
		MatchBank.missing_code_block.name,
		MatchBank.missing_code_block.value)
def missing_code_block(text):
	return bool(RegexHolder.missing_code_block.search(text))

@MatchRule.create(
		MatchBank.multiline_inline_code.name,
		MatchBank.multiline_inline_code.value)
def multiline_inline(text):
	if not RegexHolder.consecutive_inline_code_lines.search(text):
		# Avoid cases like t3_abqs9c
		return False

	new_text, n = RegexHolder.inline_code_lines.subn(r'\1', text)
	if n <= 2:
		# Ignore if it's just two lines
		return False

	return bool(RegexHolder.missing_code_block.search(new_text))

@MatchRule.create(
		MatchBank.very_long_inline_code.name,
		MatchBank.very_long_inline_code.value)
def long_inline_code(text):
	span_length = None
	for i, match in enumerate(RegexHolder.inline_code_lines.finditer(text)):
		if i > 0:
			return False
		span_length = match.span(1)[1] - match.span(1)[0]
	if span_length is None:
		return False

	if span_length > 120:
		return True
	return False

@MatchRule.create(
		MatchBank.code_fence.name,
		MatchBank.code_fence.value)
def code_fence_found(text):
	return bool(RegexHolder.code_fence.search(text))

match_control = MatchControl()
match_control.add(missing_code_block)
match_control.add(multiline_inline)
match_control.add(long_inline_code)
match_control.add(code_fence_found)
