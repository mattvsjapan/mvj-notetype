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


def _inject_inline_markers(word_surface, kana_with_markers):
    """Splice `*` markers from `kana_with_markers` into `word_surface` at the
    matching kana positions. Kana inside [...] brackets and bare kana outside
    them are both consumed in stream order; spaces and kanji in the surface
    are skipped. Markers land immediately before the kana they belong to —
    inside the bracket when the kana lives there, outside otherwise.
    """
    if '*' not in kana_with_markers:
        return word_surface
    result: list[str] = []
    src_idx = 0
    in_bracket = False

    def flush_markers():
        nonlocal src_idx
        while src_idx < len(kana_with_markers) and kana_with_markers[src_idx] == '*':
            result.append(kana_with_markers[src_idx])
            src_idx += 1

    for ch in word_surface:
        if ch == '[':
            in_bracket = True
            result.append(ch)
            continue
        if ch == ']':
            in_bracket = False
            result.append(ch)
            continue
        if ch == ' ':
            result.append(ch)
            continue
        if in_bracket or not _KANJI_RANGES_RE.match(ch):
            flush_markers()
            if src_idx < len(kana_with_markers):
                src_idx += 1
        result.append(ch)

    flush_markers()
    return ''.join(result)


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


_SPAN_RE = re.compile(r'<span\b[^>]*>(.*?)</span>', re.DOTALL)


def _extract_span_surfaces(word_field):
    """Per-<span> bare surfaces for a legacy multi-group Word field.

    Returns one surface per top-level <span>, or None if the field can't be
    cleanly segmented — no spans at all, or non-tag content sitting outside
    the spans (in which case positional splicing would be a guess).
    """
    spans = _SPAN_RE.findall(word_field)
    if not spans:
        return None
    if _word_field_surface(_SPAN_RE.sub('', word_field)):
        return None  # stray content outside spans — don't guess
    return [_word_field_surface(s) for s in spans]


def _splice_one(converted, word_surface):
    """Splice one kana-only group's kanji in from its Word-field surface.

    Returns (result, warnings); returns `converted` unchanged when the splice
    doesn't apply (kana-only Word surface, converter already produced kanji,
    no pitch suffix). Emits 'word_kana_mismatch' when the kana don't line up.
    """
    warnings = []
    if not converted:
        return converted, warnings
    if not word_surface or not _has_kanji(word_surface):
        return converted, warnings
    if _has_kanji(converted):
        return converted, warnings  # converter already produced kanji
    m = _PITCH_SUFFIX_RE.search(converted)
    if not m:
        return converted, warnings
    surface_part = converted[:m.start()]
    pitch_part = converted[m.start():]
    # Strip inline markers (`*` for devoicing) for the plain-kana compare;
    # they're re-injected into the kanji form below.
    plain_surface = surface_part.replace('*', '')
    if _bare_kana(word_surface) != plain_surface:
        warnings.append('word_kana_mismatch')
        return converted, warnings
    return _inject_inline_markers(word_surface, surface_part) + pitch_part, warnings


def splice_word_kanji(converted, word_field):
    """If converter output is kana-only but the Word field has the kanji form,
    substitute the Word-field surface in (keeping the pitch suffix).

    Single-group output is spliced directly. Multi-group output (joined with
    ' / ') is aligned to the legacy Word field's per-<span> segments — one
    span per non-ghost group, in order — and each group is spliced
    independently. Alignment is conservative: if the span count doesn't match
    the real-group count, or any group's kana don't line up, nothing is
    spliced (the kana-only form is kept rather than risk a wrong kanji).

    Returns (spliced_or_unchanged, warnings).
    """
    if not converted:
        return converted, []
    if '/' not in converted:
        return _splice_one(converted, _word_field_surface(word_field))

    groups = converted.split(' / ')
    # Ghost-particle groups (legacy " ; -") have no <span>; only the rest
    # ("real" groups) align positionally with the Word field's spans.
    real_slots = [i for i, g in enumerate(groups) if g.strip() != '-']
    surfaces = _extract_span_surfaces(word_field)
    if surfaces is None or len(surfaces) != len(real_slots):
        # Can't safely segment/align — leave kana-only. Warn only if there
        # was kanji to recover (otherwise nothing was lost).
        warnings = ['multigroup_span_mismatch'] if _has_kanji(word_field) else []
        return converted, warnings

    spliced = list(groups)
    warnings = []
    mismatch = False
    for slot, surface in zip(real_slots, surfaces):
        result, group_warnings = _splice_one(groups[slot], surface)
        for w in group_warnings:
            if w == 'word_kana_mismatch':
                mismatch = True
                warnings.append(f'word_kana_mismatch[group{slot}]')
            else:
                warnings.append(w)
        spliced[slot] = result
    if mismatch:
        # One group didn't line up — don't half-splice; keep all kana so the
        # field stays uniform and the mismatch is easy to spot.
        return converted, warnings
    return ' / '.join(spliced), warnings


def convert_comment_syntax(raw):
    """Convert full comment syntax string to new notation.

    Returns (converted, warnings).
    """
    # Split on standalone ; between word groups. The trailing " -" ghost
    # particle is intentionally NOT stripped here: it's the whitespace the
    # final " ; " group-separator needs, and a "-"-only group is handled
    # below. Per-group ghost-dash stripping still happens inside the loop.
    groups = re.split(r'\s+;\s+', raw)
    all_warnings = []
    converted_groups = []

    multi = len(groups) > 1

    for group in groups:
        # A group that is purely a ghost particle (legacy " ; -") passes
        # through verbatim — skip convert_word_field and the multi-group
        # "-$" strip below, which would otherwise annihilate it.
        if group.strip() == '-':
            converted_groups.append('-')
            continue
        group = re.sub(r'\s+-\s*$', '', group)
        tokens = group.split()
        # Convert the group as a whole so convert_word_field's "ghost dash
        # only on the last numeric-pitched token" rule applies — calling it
        # per token makes every numeric token think it's the last.
        reformatted = ' '.join(_reformat_token(t) for t in tokens)
        result, warnings = convert_word_field(reformatted)
        # In multi-group expressions, strip the auto-added ghost particle
        if multi:
            result = re.sub(r'-$', '', result)
        all_warnings.extend(warnings)
        converted_groups.append(result)

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
