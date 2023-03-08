
from __future__ import annotations
from typing import TYPE_CHECKING, overload
if TYPE_CHECKING:
    from typing import MutableMapping, Callable, Optional, Union

from enum import IntFlag
import re


class FeatureFlags(IntFlag):
    CODE_OUTSIDE_OF_CODE_BLOCK = 1
    MULTILINE_INLINE_CODE = 2
    VERY_LONG_INLINE_CODE = 4
    CODE_BLOCK = 8
    CODE_FENCE = 16

class RegexStaticNamespace:
    code_block = re.compile(r"^(\t| {4,}).+", re.M)
    code_outside_of_code_block = re.compile(r"""
^\ {0,3}(
    (function|filter|workflow|class|enum)\ *[a-z_][a-z0-9_-]*\ *\n?{
    |(if|switch)\ *\((?=.*\$).+\)\ *\n?{\ *
    |foreach\ *\((?=.*\$)(?=.*in).+\)\ *\n?{
    |for\ *\((?=[^;]*\$).*;(?=[^;]*-\w\w\b).*;.*\)\ *\n?{\ *
    |param\ *\(
    |process\ *\n?{
    |(PS\ [A-Z]:\\[-\w\\]*>\ )?\w{3,}-\w{2,}\ (-?\w+|@?'|@?"|\$[a-z]|[A-Z]:\\|\|\ *\w)
    |\$[a-z_]\w*\ *[=\|]
)
""", re.I | re.M | re.X)
    inline_code_lines = re.compile(r"^ {0,3}`(.*)`[\t ]*$", re.M)
    consecutive_inline_code_lines = re.compile(r"^ {0,3}`(.*)`[\t ]*\n\n?`.*\n\n?`", re.M)
    code_fence = re.compile(r"^```.*?\n(.*?)```", re.M | re.S)


feature_flags_registry: MutableMapping[int, Callable[[str], bool]] = {}

@overload
def register(flag: int) -> Callable[[Callable[[str], bool]], None]: ...
@overload
def register(flag: int, func: Callable[[str], bool]) -> None: ...
def register(flag: int, func: Optional[Callable[[str], bool]] = None) -> Union[Callable[[Callable[[str], bool]], None], None]:
    if func is None:
        return lambda func: register(flag, func)
    feature_flags_registry[flag] = func
    return None


@register(FeatureFlags.CODE_BLOCK)
def _(text: str) -> bool:
    return bool(RegexStaticNamespace.code_block.search(text))

@register(FeatureFlags.CODE_OUTSIDE_OF_CODE_BLOCK)
def _(text: str) -> bool:
    return bool(RegexStaticNamespace.code_outside_of_code_block.search(text))

@register(FeatureFlags.MULTILINE_INLINE_CODE)
def _(text: str) -> bool:
    if not RegexStaticNamespace.consecutive_inline_code_lines.search(text):
        # Avoid cases like submission `abqs9c`.
        return False

    new_text, n = RegexStaticNamespace.inline_code_lines.subn(r'\1', text)
    if n < 3:
        # If it's just two consecutive lines of inline code then don't bother.
        return False

    return bool(RegexStaticNamespace.code_outside_of_code_block.search(new_text))

@register(FeatureFlags.VERY_LONG_INLINE_CODE)
def _(text: str) -> bool:
    for match in RegexStaticNamespace.inline_code_lines.finditer(text):
        group1_span = match.span(1)
        span_length = group1_span[1] - group1_span[0]
        if span_length > 120:
            return True
    return False

@register(FeatureFlags.CODE_FENCE)
def _(text: str) -> bool:
    return bool(RegexStaticNamespace.code_fence.search(text))


def extract_features(text: str) -> int:
    b = 0
    for flag, func in feature_flags_registry.items():
        if func(text):
            b |= flag
    return b
