import re
from typing import List

try:
    from .split import SENT_HIDDEN
except ImportError:
    from split import SENT_HIDDEN


def word_to_ruby(word: str) -> str:
    """Convert bracket furigana notation to HTML <ruby> tags.

    '大物[おおもの]' → '<ruby>大物<rt>おおもの</rt></ruby>'
    '稼[かせ]いで'  → '<ruby>稼<rt>かせ</rt></ruby>いで'
    'じんせい'       → 'じんせい'
    """
    result = ''
    last_index = 0
    for match in re.finditer(r'([^\[\]]+)\[([^\]]+)\]', word):
        if match.start() > last_index:
            result += word[last_index:match.start()]
        result += f'<ruby>{match.group(1)}<rt>{match.group(2)}</rt></ruby>'
        last_index = match.end()
    if last_index < len(word):
        result += word[last_index:]
    return result


def make_colored_sentence(sequence) -> str:
    """Generate a single colored HTML string for one sequence."""
    spans = []
    for section in sequence:
        if section.word in SENT_HIDDEN or section.is_tape:
            continue
        spans.append(f'<span class="{section.classname}">{word_to_ruby(section.word)}</span>')
    return ''.join(spans)


def apply_kanji_colors(seq_sequences) -> List[str]:
    """Call make_colored_sentence on each sequence."""
    return [make_colored_sentence(s) for s in seq_sequences]
