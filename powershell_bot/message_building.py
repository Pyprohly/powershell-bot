
from typing import Optional

from io import StringIO
from string import Template
from urllib.parse import urlencode
from enum import Enum, auto

from redditwarp.util.base_conversion import to_base36

from .feature_extraction import FeatureFlags


class MessagePartsStaticNamepace:
    code_outside_of_code_block_message = '''\
Looks like your PowerShell code isn’t wrapped in a code block.

To properly style code on **[new Reddit][new.reddit.com]**, highlight the code and
choose ‘Code Block’ from the editing toolbar.

If you’re on **[old Reddit][old.reddit.com]**, separate the code from your text with
a blank line gap and precede each line of code with **4 spaces** or a **tab**.

[old.reddit.com]: https://old.reddit.com${rel_permalink}
[new.reddit.com]: https://new.reddit.com${rel_permalink}
'''
    code_outside_of_code_block_template = Template(code_outside_of_code_block_message)

    some_code_outside_of_code_block_message = '''\
Some of your PowerShell code isn’t enclosed in a code block.

To properly style code on **[new Reddit][new.reddit.com]**, highlight the code and
choose ‘Code Block’ from the editing toolbar.

If you’re on **[old Reddit][old.reddit.com]**, separate the code from your text with
a blank line gap and precede each line of code with **4 spaces** or a **tab**.

[old.reddit.com]: https://old.reddit.com${rel_permalink}
[new.reddit.com]: https://new.reddit.com${rel_permalink}
'''
    some_code_outside_of_code_block_template = Template(some_code_outside_of_code_block_message)

    multiline_inline_code_message = '''\
It appears that you have used *inline code* formatting when a **code block**
should have been used.

Consider using a code block for longer sequences of code.
To correct the formatting, highlight your code then click the ‘Code Block’
button in the editing toolbar.
'''
    multiline_inline_code_template = Template(multiline_inline_code_message)

    very_long_inline_code_message = '''\
That’s a really long line of inline code.

On **[old Reddit][old.reddit.com]** inline code blocks do not word wrap, making it
difficult for many of us to see all your code.

To ensure your code is readable by everyone, on **[new Reddit][new.reddit.com]**,
highlight your code and select ‘Code Block’ in the editing toolbar.

If you’re on **[old Reddit][old.reddit.com]**, separate the code from your text with
a blank line gap and precede each line of code with **4 spaces** or a **tab**.

[old.reddit.com]: https://old.reddit.com${rel_permalink}
[new.reddit.com]: https://new.reddit.com${rel_permalink}
'''
    very_long_inline_code_template = Template(very_long_inline_code_message)

    code_fences_message = '''\
Code fences are a **[new Reddit][new.reddit.com]** feature and won’t render for
those viewing your post on **[old Reddit][old.reddit.com]**.

If you want those viewing from old Reddit to see your PowerShell code formatted
correctly then consider using a regular space-indented **code block**. This can
be easily be done on **[new Reddit][new.reddit.com]** by highlighting your code
and selecting ‘Code Block’ in the editing toolbar.

[old.reddit.com]: https://old.reddit.com${rel_permalink}
[new.reddit.com]: https://new.reddit.com${rel_permalink}
'''
    code_fences_template = Template(code_fences_message)

    thematic_break = '\n-----\n\n'


def build_body_message_part(template: Template, rel_permalink: str) -> str:
    substitutions = {
        'rel_permalink': rel_permalink,
    }
    return template.substitute(substitutions)

def build_enlightenment_message_part(fraction: tuple[int, int]) -> str:
    length = 20
    fill_length = int(length * (fraction[0]/fraction[1]))
    bar = fill_length*'\N{FULL BLOCK}' + (length - fill_length)*'-'

    symbol = '\N{CROSS MARK}'
    if fraction[0] == fraction[1]:
        symbol = '\N{WHITE HEAVY CHECK MARK}'
    elif fraction[0] != 0:
        symbol = '\N{WARNING SIGN}\N{VARIATION SELECTOR-16}'

    return '''\
    You examine the path beneath your feet...
    [AboutRedditFormatting]: [{}] {} {}
'''.format(bar, '%d/%d' % fraction, symbol)

def build_footer_message_part(submission_id: int, reddit_user_name: str) -> str:
    submission_id36 = to_base36(submission_id)
    message = '''\
Click ‘send’ to immediately delete the bot’s comment.

The bot’s comment will not be deleted if:

* You are not the submitter of the submission.
* There are any replies on the bot’s comment.
'''
    query_params = {
        'to': reddit_user_name,
        'subject': f'!delete {submission_id36}',
        'message': message,
    }
    deletion_form_url = 'https://www.reddit.com/message/compose?' + urlencode(query_params)

    return f'''\
&thinsp;^(*Beep-boop, I am a bot.* | [Remove-Item])

[Remove-Item]: {deletion_form_url}
'''

class MessageDeterminer(Enum):
    CODE_FENCES = auto()
    SOME_CODE_OUTSIDE_OF_CODE_BLOCK = auto()
    CODE_OUTSIDE_OF_CODE_BLOCK = auto()
    MULTILINE_INLINE_CODE = auto()
    VERY_LONG_INLINE_CODE = auto()

def get_message_determiner(feature_flags: int) -> Optional[MessageDeterminer]:
    if (feature_flags & (mask := FeatureFlags.CODE_OUTSIDE_OF_CODE_BLOCK | FeatureFlags.CODE_FENCE)) == mask:
        return MessageDeterminer.CODE_FENCES
    elif (feature_flags & (mask := FeatureFlags.CODE_OUTSIDE_OF_CODE_BLOCK | FeatureFlags.CODE_BLOCK)) == mask:
        return MessageDeterminer.SOME_CODE_OUTSIDE_OF_CODE_BLOCK
    elif feature_flags & FeatureFlags.CODE_OUTSIDE_OF_CODE_BLOCK:
        return MessageDeterminer.CODE_OUTSIDE_OF_CODE_BLOCK
    elif feature_flags & FeatureFlags.MULTILINE_INLINE_CODE:
        return MessageDeterminer.MULTILINE_INLINE_CODE
    elif feature_flags & FeatureFlags.VERY_LONG_INLINE_CODE:
        return MessageDeterminer.VERY_LONG_INLINE_CODE
    return None


def build_message(
    *,
    determiner: MessageDeterminer,
    submission_id: int,
    rel_permalink: str,
    enlightened: bool,
    reddit_user_name: str,
) -> str:
    template, fraction = {
        MessageDeterminer.CODE_FENCES: (
            MessagePartsStaticNamepace.code_fences_template,
            (2, 2) if enlightened else (1, 2),
        ),
        MessageDeterminer.SOME_CODE_OUTSIDE_OF_CODE_BLOCK: (
            MessagePartsStaticNamepace.some_code_outside_of_code_block_template,
            (3, 3) if enlightened else (2, 3),
        ),
        MessageDeterminer.CODE_OUTSIDE_OF_CODE_BLOCK: (
            MessagePartsStaticNamepace.code_outside_of_code_block_template,
            (1, 1) if enlightened else (0, 1),
        ),
        MessageDeterminer.MULTILINE_INLINE_CODE: (
            MessagePartsStaticNamepace.multiline_inline_code_template,
            (1, 1) if enlightened else (0, 1),
        ),
        MessageDeterminer.VERY_LONG_INLINE_CODE: (
            MessagePartsStaticNamepace.very_long_inline_code_template,
            (1, 1) if enlightened else (0, 1),
        ),
    }[determiner]

    sio = StringIO()
    sio.write(build_body_message_part(template, rel_permalink))
    sio.write(MessagePartsStaticNamepace.thematic_break)
    sio.write(build_enlightenment_message_part(fraction))
    sio.write(MessagePartsStaticNamepace.thematic_break)
    sio.write(build_footer_message_part(submission_id, reddit_user_name))
    return sio.getvalue()
