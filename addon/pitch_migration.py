"""Convert legacy Image-field comment syntax to the new Word-field notation.

Pure-function module — no Anki dependencies, fully testable standalone.
"""

import re

try:
    from .pitch_converter import convert_word_field
except ImportError:  # standalone (test) import
    from pitch_converter import convert_word_field


# Matches [reading]okurigana;pitch — okurigana may be empty
_PITCH_OUTSIDE_RE = re.compile(r'\[([^\]]+)\]([^;\s]*);(\S+)')
_EMPTY_PITCH_RE = re.compile(r'\[([^\]]+)\]([^;\s]*);')
# d = devoiced: 'd' immediately preceding a kana inside a bracket marks that
# kana as devoiced; rewrite as '*' in the same position. Handles d at the
# start of the bracket ([dきし] → [*きし]) and inline ([がdくしゃ] → [が*くしゃ]).
_BRACKET_RE = re.compile(r'\[([^\]]+)\]')
_INLINE_DEVOICED_RE = re.compile(r'd(?=[぀-ヿ])')


def _reformat_token(text):
    """Reformat a single token from comment syntax to converter input."""
    # d modifier → * inserted at the same position inside the bracket
    text = _BRACKET_RE.sub(
        lambda m: '[' + _INLINE_DEVOICED_RE.sub('*', m.group(1)) + ']',
        text,
    )
    # Move ;pitch inside brackets
    text = _PITCH_OUTSIDE_RE.sub(r'[\1;\3]\2', text)
    # Empty pitch (trailing ";") defaults to 0
    text = _EMPTY_PITCH_RE.sub(r'[\1;0]\2', text)
    # Bare token with ;pitch but no brackets → wrap in brackets
    # (empty pitch defaults to 0, matching the bracketed _EMPTY_PITCH_RE rule)
    if '[' not in text and ';' in text:
        m = re.match(r'^([^;]+);(\S*)$', text)
        if m:
            word, pitch = m.group(1), m.group(2) or '0'
            is_all_kana = word and all(
                '぀' <= ch <= 'ゟ' or '゠' <= ch <= 'ヿ'
                for ch in word
            )
            # Pure-kana word: use kana[pitch] form so the converter treats
            # the kana as the word, not as a "reading" needing brackets.
            text = f'{word}[{pitch}]' if is_all_kana else f'[{word};{pitch}]'
    return text


def convert_comment_syntax(raw):
    """Convert full comment syntax string to new notation.

    Returns (converted, warnings).
    """
    # Strip trailing " -" ghost particle — convert_word_field adds its own
    raw = re.sub(r'\s+-\s*$', '', raw)
    # Split on standalone ; between word groups
    groups = re.split(r'\s+;\s+', raw)
    all_warnings = []
    converted_groups = []

    multi = len(groups) > 1

    for group in groups:
        group = re.sub(r'\s+-\s*$', '', group)
        tokens = group.split()
        pitched = []
        for token in tokens:
            reformatted = _reformat_token(token)
            result, warnings = convert_word_field(reformatted)
            # In multi-group expressions, strip the auto-added ghost particle
            if multi:
                result = re.sub(r'-$', '', result)
            all_warnings.extend(warnings)
            pitched.append(result)

        converted_groups.append(' '.join(pitched))

    # Join word groups with /
    result = ' / '.join(converted_groups)

    # Add : to bare particles between accented tokens
    parts = result.split(' ')
    for i in range(len(parts)):
        if ':' in parts[i] or parts[i] == '/':
            continue
        has_before = any(':' in parts[j] for j in range(i))
        has_after = any(':' in parts[j] for j in range(i + 1, len(parts)))
        if has_before and has_after:
            parts[i] = parts[i] + ':'
    result = ' '.join(parts)

    return result, all_warnings
