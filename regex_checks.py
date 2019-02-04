
import re
from enum import IntFlag

class MatchControl:
	def __init__(self):
		self.match_rules = []
		self.match_store = {}

	def add(self, rule):
		t = type(rule.tag)
		if t not in self.match_store:
			self.match_store[t] = 0

		self.match_rules.append(rule)

	def check(self, tag_type, haystack):
		self.match_store[tag_type] = 0
		for rule in self.match_rules:
			if type(rule.tag) is tag_type:
				if rule.test(haystack):
					self.match_store[tag_type] |= rule.flag

	def check_all(self, haystack):
		self.match_store = dict.fromkeys(self.match_store, 0)
		for rule in self.match_rules:
			if rule.test(haystack):
				self.match_store[type(rule.tag)] |= rule.flag

	def get(self, key, default=None):
		return self.match_store.get(key, default)

	def __getitem__(self, tag):
		return self.get(tag)

class MatchRule:
	def __init__(self, tag, func):
		self.tag = tag
		self.name = tag.name
		self.flag = tag.value
		self.func = func

	def test(self, text):
		return self.func(text)

	def __call__(self, *args, **kwargs):
		return self.func(*args, **kwargs)

	@classmethod
	def create(cls, tag):
		def decorator(func):
			return cls(tag=tag, func=func)
		return decorator

class RegexHolder:
	code_outside_of_code_block = re.compile((
			r'^ {0,3}('
			r'(function|filter|workflow|class|enum) *[a-z_]\w* *\{'
			r'|(switch|if|foreach) *\([^\)]+\) *\{'
			r'|param *\('
			r'|process *\{'
			r'''|(PS [A-Z]:\\[-\w\\]*> )?\w{3,}-\w{2,} (-\w+|@?'|@?"|\$[a-z]|[A-Z]:\\|\| *\w)'''
			r'|\$[a-z_]\w* *[=\|]'
			r')'), re.I | re.M)

	inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*$', re.M)
	consecutive_inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*\n\n?`.*\n\n?`', re.M)

	code_fence = re.compile(r'^```.*?\n(.*?)```', re.M | re.S)

	contains_code_block = re.compile(r'^(\t| {4,}).+', re.M)

class TopicFlags(IntFlag):
	code_outside_of_code_block = 1
	multiline_inline_code = 2
	very_long_inline_code = 4
	code_fence = 8

class ExtraFlags(IntFlag):
	contains_code_block = 1

@MatchRule.create(TopicFlags.code_outside_of_code_block)
def code_outside_of_code_block(text):
	return bool(RegexHolder.code_outside_of_code_block.search(text))

@MatchRule.create(TopicFlags.multiline_inline_code)
def multiline_inline(text):
	if not RegexHolder.consecutive_inline_code_lines.search(text):
		# Avoid cases like t3_abqs9c
		return False

	new_text, n = RegexHolder.inline_code_lines.subn(r'\1', text)
	if n <= 2:
		# Ignore if it's just two lines
		return False

	return bool(RegexHolder.code_outside_of_code_block.search(new_text))

@MatchRule.create(TopicFlags.very_long_inline_code)
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

@MatchRule.create(TopicFlags.code_fence)
def code_fence_found(text):
	return bool(RegexHolder.code_fence.search(text))

@MatchRule.create(ExtraFlags.contains_code_block)
def contains_code_block(text):
	return bool(RegexHolder.contains_code_block.search(text))

match_control = MatchControl()
match_control.add(code_outside_of_code_block)
match_control.add(multiline_inline)
match_control.add(long_inline_code)
match_control.add(code_fence_found)
match_control.add(contains_code_block)
