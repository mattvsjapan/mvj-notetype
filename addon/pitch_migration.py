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
# d = devoiced: 'd' immediately preceding a kana marks that kana as devoiced;
# rewrite as '*' in the same position. Applies wherever the pattern appears
# — inside brackets ([dきし] → [*きし], [がdくしゃ] → [が*くしゃ]) or in bare
# kana tokens (いdきき → い*きき).
_INLINE_DEVOICED_RE = re.compile(r'd(?=[぀-ヿ])')


def _reformat_token(text):
    """Reformat a single token from comment syntax to converter input."""
    # d modifier → * (everywhere, before the bare-kana check below sees it)
    text = _INLINE_DEVOICED_RE.sub('*', text)
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
                '぀' <= ch <= 'ゟ' or '゠' <= ch <= 'ヿ' or ch == '*'
                for ch in word
            )
            # Pure-kana word: use kana[pitch] form so the converter treats
            # the kana as the word, not as a "reading" needing brackets.
            text = f'{word}[{pitch}]' if is_all_kana else f'[{word};{pitch}]'
    return text


# --- Word-field kanji splice -----------------------------------------------
# When the Image-comment syntax is kana-only but the Word field already has
# the kanji+furigana form, splice the Word-field surface into the converter
# output so the kanji isn't lost.

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_KANJI_RANGES_RE = re.compile(r'[一-鿿㐀-䶿々-〇]')
_KANJI_FURIGANA_RE = re.compile(
    r'[一-鿿㐀-䶿々-〇]+\[([^\]]+)\]'
)
# Pitch suffix at end of a single-group converter output: ':' then digits/
# letters/commas/+/~, optionally followed by trailing '-' (ghost particle).
_PITCH_SUFFIX_RE = re.compile(r':[0-9a-zA-Z,+~]+-?$')


def _has_kanji(text):
    return bool(_KANJI_RANGES_RE.search(text))


def _word_field_surface(word_field):
    """Strip HTML wrappers; return the bare Anki-furigana surface text."""
    return _HTML_TAG_RE.sub('', word_field).strip()


def _bare_kana(surface):
    """Reduce an Anki-furigana surface to its kana reading.

    '当[あ]たり 外[はず]れ' → 'あたりはずれ'
    """
    surface = _KANJI_FURIGANA_RE.sub(r'\1', surface)
    surface = re.sub(r'\[[^\]]*\]', '', surface)
    return surface.replace(' ', '').strip()


_FRONT_VISIBLE_RE = re.compile(r'class\s*=\s*"[^"]*\bfront_visible\b[^"]*"')
# Bracket contents not starting with `!` or a digit — i.e. a furigana
# reading, not an already-marked bracket or a pitch-only bracket like [0].
_FURIGANA_BRACKET_RE = re.compile(r'\[([^\]!0-9][^\]]*)\]')


def mark_front_visible(converted, word_field):
    """If the legacy Word field carries `class="front_visible"`, prefix each
    furigana bracket in `converted` with `!` so the new note type renders
    the reading on the front (see note-types/mvj/front.html `textToRuby`:
    `reading.charAt(0) === '!'` → `<rt data-front>...</rt>`).

    Idempotent. Brackets whose contents start with `!` or a digit are left
    alone, so `[0]`-style empty-pitch brackets aren't touched.
    """
    if not _FRONT_VISIBLE_RE.search(word_field):
        return converted
    return _FURIGANA_BRACKET_RE.sub(r'[!\1]', converted)


def splice_word_kanji(converted, word_field):
    """If converter output is kana-only but Word field has the kanji form,
    substitute the Word-field surface in (keeping the pitch suffix).

    Returns (spliced_or_unchanged, warnings).
    """
    warnings = []
    if not converted or '/' in converted:
        return converted, warnings  # skip multi-group / split compounds
    word_surface = _word_field_surface(word_field)
    if not word_surface or not _has_kanji(word_surface):
        return converted, warnings
    if _has_kanji(converted):
        return converted, warnings  # converter already produced kanji
    m = _PITCH_SUFFIX_RE.search(converted)
    if not m:
        return converted, warnings
    surface_part = converted[:m.start()]
    pitch_part = converted[m.start():]
    if _bare_kana(word_surface) != surface_part:
        warnings.append('word_kana_mismatch')
        return converted, warnings
    return word_surface + pitch_part, warnings


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
