"""Convert old MvJ semicolon-inside-brackets pitch syntax to new colon-outside syntax.

Pure-function module — no Anki dependencies, fully testable standalone.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Character helpers
# ---------------------------------------------------------------------------

def _is_kanji(ch):
    """True if ch is a CJK ideograph or the repeat mark 々."""
    return ch == '々' or (
        unicodedata.category(ch) == 'Lo' and (
            '\u4e00' <= ch <= '\u9fff' or   # CJK Unified
            '\u3400' <= ch <= '\u4dbf'      # CJK Extension A
        )
    )


def _is_kana(ch):
    """True if ch is hiragana or katakana."""
    return ('\u3040' <= ch <= '\u309f' or   # hiragana
            '\u30a0' <= ch <= '\u30ff')      # katakana


def _to_hiragana(text):
    """Normalize katakana to hiragana for comparison."""
    result = []
    for ch in text:
        cp = ord(ch)
        if 0x30A1 <= cp <= 0x30F6:  # katakana ァ–ヶ
            result.append(chr(cp - 0x60))
        else:
            result.append(ch)
    return ''.join(result)


def _is_all_kana(text):
    """True if every character in text is kana."""
    return bool(text) and all(_is_kana(ch) for ch in text)


# ---------------------------------------------------------------------------
# Bracket classification
# ---------------------------------------------------------------------------

_PITCH_ONLY_RE = re.compile(r'^[0-9,hkaonb~+p\-]+$')


def _classify_bracket(content):
    """Classify bracket content.

    Returns 'reading_and_pitch', 'pitch_only', 'reading_only', or 'already_new'.
    """
    if ':' in content:
        return 'already_new'
    if ';' in content:
        return 'reading_and_pitch'
    if _PITCH_ONLY_RE.match(content):
        return 'pitch_only'
    return 'reading_only'


# ---------------------------------------------------------------------------
# Multiple-reading parsing (§2.5)
# ---------------------------------------------------------------------------

def _parse_readings(content):
    """Parse bracket content into list of (reading, pitch_str) tuples.

    For single-reading content like 'にほん;2', returns [('にほん', '2')].
    For multiple like 'しんじゅう;0,しんちゅう;1,0', returns
    [('しんじゅう', '0'), ('しんちゅう', '1,0')].
    """
    parts = content.split(';')
    readings = []
    current_reading = parts[0]
    current_pitches = []

    for part in parts[1:]:
        # Split on comma to find where a new reading starts
        sub_parts = part.split(',')
        for j, sp in enumerate(sub_parts):
            sp_stripped = sp.strip()
            if sp_stripped and (_is_kana(sp_stripped[0]) or sp_stripped[0] == '*'):
                # This starts a new reading — flush current
                if current_reading is not None:
                    readings.append((current_reading, ','.join(current_pitches)))
                current_reading = sp_stripped
                current_pitches = []
            else:
                # It's a pitch value for the current reading
                current_pitches.append(sp_stripped)

    if current_reading is not None:
        readings.append((current_reading, ','.join(current_pitches)))

    return readings


# ---------------------------------------------------------------------------
# Pitch normalization (§2.9)
# ---------------------------------------------------------------------------

def _normalize_pitch(raw_pitch):
    """Normalize an old-syntax pitch value for new colon syntax.

    Returns (new_pitch, suffix) where suffix is appended after :pitch
    (e.g., ' -' for ghost particle from '+' modifier).
    """
    pitch = raw_pitch
    suffix = ''

    # Handle + modifier: strip it, add ghost particle
    if '+' in pitch:
        pitch = pitch.replace('+', '')
        suffix = ' -'

    # Handle b modifier: reorder to role-before-digit
    # Old allows b as prefix or suffix: 0b, 2b, b2, pb
    # New requires: b as role letter before digit: b0, b2, pb
    if 'b' in pitch and pitch != 'b':
        has_p = pitch.startswith('p')
        rest = pitch.lstrip('p').replace('b', '')
        pitch = ('p' if has_p else '') + 'b' + rest

    # Handle ~ modifier: ensure it's present (both positions work in new syntax)
    # ~0, 0~ both acceptable — leave as-is after + and b handling

    return pitch, suffix


# ---------------------------------------------------------------------------
# Furigana distribution (§5)
# ---------------------------------------------------------------------------

def _distribute_furigana(word, reading):
    """Split combined reading across kanji segments using kana anchors.

    Returns list of ('kanji', kanji_text, kanji_reading) and ('kana', kana_text)
    tuples, or None if distribution fails.
    """
    # Split word into alternating kanji/kana segments
    segments = []
    i = 0
    while i < len(word):
        if _is_kanji(word[i]):
            run = ''
            while i < len(word) and _is_kanji(word[i]):
                run += word[i]
                i += 1
            segments.append(('kanji', run))
        else:
            run = ''
            while i < len(word) and not _is_kanji(word[i]):
                run += word[i]
                i += 1
            segments.append(('kana', run))

    # If there's only one kanji segment and no kana anchors, can't split further
    kanji_count = sum(1 for t, _ in segments if t == 'kanji')
    if kanji_count <= 1:
        # Single kanji segment — just return as-is (no splitting needed)
        result = []
        r_pos = 0
        for seg_type, seg_text in segments:
            if seg_type == 'kana':
                kana_len = len(seg_text)
                if r_pos + kana_len > len(reading):
                    return None
                expected = _to_hiragana(seg_text)
                actual = _to_hiragana(reading[r_pos:r_pos + kana_len])
                if expected != actual:
                    return None
                r_pos += kana_len
                result.append(('kana', seg_text))
            else:
                kanji_reading = reading[r_pos:]
                r_pos = len(reading)
                if not kanji_reading:
                    return None
                result.append(('kanji', seg_text, kanji_reading))
        return result

    # Match segments against reading using kana anchors
    result = []
    r_pos = 0
    for idx, (seg_type, seg_text) in enumerate(segments):
        if seg_type == 'kana':
            kana_len = len(seg_text)
            if r_pos + kana_len > len(reading):
                return None
            expected = _to_hiragana(seg_text)
            actual = _to_hiragana(reading[r_pos:r_pos + kana_len])
            if expected != actual:
                return None
            r_pos += kana_len
            result.append(('kana', seg_text))
        else:
            # Find the next kana anchor in the word
            next_kana = None
            for future_type, future_text in segments[idx + 1:]:
                if future_type == 'kana':
                    next_kana = future_text
                    break

            if next_kana is not None:
                anchor_hira = _to_hiragana(next_kana)
                reading_hira = _to_hiragana(reading)
                anchor_pos = reading_hira.find(anchor_hira, r_pos)
                if anchor_pos == -1:
                    return None
                kanji_reading = reading[r_pos:anchor_pos]
                r_pos = anchor_pos
            else:
                # Last segment — consume all remaining reading
                kanji_reading = reading[r_pos:]
                r_pos = len(reading)

            if not kanji_reading:
                return None
            result.append(('kanji', seg_text, kanji_reading))

    return result


def _segments_to_text(segments, pitch, okurigana=''):
    """Build new notation from distributed segments.

    Returns string like '考[かんが] え 方[かた]:5,0'.
    """
    parts = []
    for seg in segments:
        if seg[0] == 'kana':
            parts.append(seg[1])
        else:
            parts.append(f'{seg[1]}[{seg[2]}]')
    return ' '.join(parts) + okurigana + f':{pitch}'


# ---------------------------------------------------------------------------
# Nakaten compound conversion (§2.7)
# ---------------------------------------------------------------------------

def _convert_nakaten_compound(word, reading_with_dots, pitch_with_hyphens, okurigana=''):
    """Convert a nakaten compound to new syntax with per-segment accents.

    Returns (new_text, warnings).
    """
    reading_segments = reading_with_dots.split('・')
    pitch_segments = pitch_with_hyphens.split('-')
    full_reading = ''.join(reading_segments)

    # Try distributing the full reading across the word
    distributed = _distribute_furigana(word, full_reading)
    if distributed is None:
        # Fallback: can't split — keep combined bracket, use last pitch
        pitch, suffix = _normalize_pitch(pitch_segments[-1])
        return f'{word}[{full_reading}]{okurigana}:{pitch}{suffix}', ['nakaten_fallback']

    # Partition distributed segments by reading segment boundaries
    groups = []
    current_group = []
    seg_idx = 0
    chars_consumed = 0
    target_len = len(reading_segments[seg_idx])

    for seg in distributed:
        current_group.append(seg)
        if seg[0] == 'kana':
            chars_consumed += len(seg[1])
        else:  # kanji
            chars_consumed += len(seg[2])  # reading length

        if chars_consumed >= target_len:
            pitch_idx = min(seg_idx, len(pitch_segments) - 1)
            groups.append((current_group, pitch_segments[pitch_idx]))
            current_group = []
            seg_idx += 1
            chars_consumed = 0
            if seg_idx < len(reading_segments):
                target_len = len(reading_segments[seg_idx])

    # Any remaining segments go into the last group
    if current_group:
        groups.append((current_group, pitch_segments[-1]))

    # If we couldn't split into as many groups as reading segments,
    # the distribution didn't actually help — fall back
    if len(groups) < len(reading_segments):
        pitch, suffix = _normalize_pitch(pitch_segments[-1])
        return f'{word}[{full_reading}]{okurigana}:{pitch}{suffix}', ['nakaten_fallback']

    # Build output: each group becomes segments + :pitch
    parts = []
    for group_segs, raw_pitch in groups:
        pitch, suffix = _normalize_pitch(raw_pitch)
        text_parts = []
        for seg in group_segs:
            if seg[0] == 'kana':
                text_parts.append(seg[1])
            else:
                text_parts.append(f'{seg[1]}[{seg[2]}]')
        parts.append(' '.join(text_parts) + f':{pitch}{suffix}')

    # Last group gets any trailing okurigana (insert before :pitch)
    if okurigana and parts:
        last = parts[-1]
        colon_pos = last.rfind(':')
        parts[-1] = last[:colon_pos] + okurigana + last[colon_pos:]

    return ' '.join(parts), ['nakaten_split']


# ---------------------------------------------------------------------------
# Token-level detection
# ---------------------------------------------------------------------------

# Detect old-syntax bracket (has semicolon + pitch)
_OLD_PITCHED_BRACKET = re.compile(r'\[[^\]]*;[^\]]*\]')

# Detect pitch-only bracket
_PITCH_ONLY_BRACKET = re.compile(r'\[([0-9hkaonb~+p,\-]+)\]')

# Full word-field token pattern
_WORD_TOKEN_RE = re.compile(
    r'^(?P<head>[^\[\]]*?)'          # text before bracket (kanji, kana, or empty)
    r'\[(?P<content>[^\]]+)\]'       # bracket content
    r'(?P<tail>[^\[\]:]*)$'          # okurigana after bracket
)


def _is_already_converted(token):
    """True if token has ':' outside brackets (already new syntax)."""
    stripped = re.sub(r'\[[^\]]*\]', '', token)
    return ':' in stripped


# ---------------------------------------------------------------------------
# Single-token conversion (Word field) — §2.1–§2.7
# ---------------------------------------------------------------------------

def _convert_single_token(token):
    """Convert a single old-syntax word-field token.

    Returns (converted_text, warnings).
    """
    warnings = []

    if _is_already_converted(token):
        return token, warnings

    m = _WORD_TOKEN_RE.match(token)
    if not m:
        return token, warnings

    head = m.group('head')
    content = m.group('content')
    tail = m.group('tail')
    bracket_type = _classify_bracket(content)

    if bracket_type == 'already_new':
        return token, warnings

    if bracket_type == 'reading_only':
        # No pitch data — leave unchanged
        return token, warnings

    if bracket_type == 'pitch_only':
        # Kana-only word: kana[pitch] → kana:pitch
        pitch, suffix = _normalize_pitch(content)
        return f'{head}{tail}:{pitch}{suffix}', warnings

    # bracket_type == 'reading_and_pitch'
    readings = _parse_readings(content)
    if not readings:
        return token, warnings

    reading, raw_pitch = readings[0]
    if len(readings) > 1:
        warnings.append('multiple_readings')

    # Check for nakaten in reading
    if '・' in reading:
        return _convert_nakaten_compound(head, reading, raw_pitch, tail)

    pitch, suffix = _normalize_pitch(raw_pitch)

    # Check if this is a collapsed compound that needs furigana distribution
    if head and not _is_all_kana(head):
        # Word is kanji (possibly mixed with kana) — try distribution
        distributed = _distribute_furigana(head, reading)
        if distributed is not None:
            # Check if distribution actually split anything
            kanji_segs = [s for s in distributed if s[0] == 'kanji']
            if len(kanji_segs) > 1 or any(s[0] == 'kana' for s in distributed):
                # Successful split into multiple segments
                return _segments_to_text(distributed, pitch, tail) + suffix, warnings

        # Couldn't distribute or single kanji block — keep combined bracket
        return f'{head}[{reading}]{tail}:{pitch}{suffix}', warnings

    if head and _is_all_kana(head):
        # Kana word with reading_and_pitch bracket (unusual but handle it)
        # Use pitch from bracket
        return f'{head}{tail}:{pitch}{suffix}', warnings

    # Fallback: just move pitch outside
    if head:
        return f'{head}[{reading}]{tail}:{pitch}{suffix}', warnings
    return f'[{reading}]{tail}:{pitch}{suffix}', warnings


# ---------------------------------------------------------------------------
# Sentence-field helpers (§3, §6)
# ---------------------------------------------------------------------------

# Matches brackets with ;letter at the end: [かんが;n], [n], [かた;n]
_SENTENCE_PITCH_LETTER_RE = re.compile(
    r'\[(?:([^\];]*);)?([hankHANK])\]'
)


def _get_pitch_letter(token):
    """Extract pitch letter (h/a/n/k) from an old-syntax token, or None."""
    m = re.search(r'\[([^\]]*);([hankHANK])\]', token)
    if m:
        return m.group(2).lower()
    # Check for pitch-only bracket with single letter
    m = re.search(r'\[([hank])\]', token)
    if m:
        return m.group(1)
    return None


def _group_compound_tokens(tokens):
    """Group consecutive tokens sharing the same pitch letter.

    Returns list of (group_type, letter, token_list, flag) tuples.
    group_type is 'compound', 'single', or 'bare'.
    """
    groups = []
    current_group = []
    current_letter = None

    def flush_group():
        if not current_group:
            return
        if len(current_group) > 1:
            flag = 'hk_compound_review' if current_letter in ('h', 'k') else None
            groups.append(('compound', current_letter, current_group[:], flag))
        else:
            groups.append(('single', current_letter, current_group[:], None))

    for token in tokens:
        letter = _get_pitch_letter(token)
        if letter is not None and letter == current_letter:
            current_group.append(token)
        else:
            flush_group()
            if letter is not None:
                current_group = [token]
                current_letter = letter
            else:
                # Check if this bare token has numeric/other old-syntax pitch
                groups.append(('bare', None, [token], None))
                current_group = []
                current_letter = None

    flush_group()
    return groups


def _convert_compound_group(tokens, letter):
    """Convert a compound group into a single merged token.

    Strips pitch from all members, adds :letter to the last one,
    then joins everything into one space-separated string.

    Returns (merged_token, warnings).
    """
    converted = []
    for token in tokens:
        def strip_pitch(m):
            reading = m.group(1)
            if reading:
                return f'[{reading}]'   # [かんが;n] → [かんが]
            else:
                return ''               # [n] → removed entirely
        converted.append(_SENTENCE_PITCH_LETTER_RE.sub(strip_pitch, token))

    # Add :letter to the last token
    converted[-1] = converted[-1] + f':{letter}'

    warnings = []
    if letter in ('h', 'k') and len(tokens) > 1:
        warnings.append('hk_compound_review')

    merged = ' '.join(converted)
    merged = _escape_trailing_i(merged)
    return merged, warnings


# Sentence-ending punctuation and non-particle characters
_SENTENCE_ENDING = {'。', '！', '？', '!', '?'}
_NON_PARTICLE = {'。', '、', '！', '？', '!', '?', '…', '「', '」'}


def _add_particle_colons(tokens):
    """Add :p to bare tokens sitting between two accented tokens.

    Splits on sentence-ending punctuation first, then processes each
    clause independently.
    """
    clauses = []
    current = []
    for token in tokens:
        current.append(token)
        stripped = token.strip()
        if stripped and stripped[-1] in _SENTENCE_ENDING:
            clauses.append(current)
            current = []
    if current:
        clauses.append(current)

    result = []
    for clause in clauses:
        result.extend(_add_particle_colons_clause(clause))
    return result


def _add_particle_colons_clause(tokens):
    """Add :p to bare tokens between accented tokens within a single clause."""
    result = list(tokens)

    for i in range(len(result)):
        if ':' in result[i]:
            continue  # already accented
        stripped = result[i].strip()
        if stripped in _NON_PARTICLE:
            continue
        if stripped and stripped[-1] in _SENTENCE_ENDING:
            continue

        # Look for accented token before and after
        has_before = any(':' in result[j] for j in range(i - 1, -1, -1))
        has_after = any(':' in result[j] for j in range(i + 1, len(result)))

        if has_before and has_after:
            result[i] = result[i] + ':p'

    return result


# ---------------------------------------------------------------------------
# HTML preservation
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r'<[^>]+>')


def _convert_preserving_html(text, converter_fn):
    """Split on HTML tags, convert only text segments, reassemble.

    converter_fn(text_segment) → (converted, warnings)
    Returns (converted_full_text, all_warnings).
    """
    parts = _HTML_TAG_RE.split(text)
    tags = _HTML_TAG_RE.findall(text)
    all_warnings = []

    converted_parts = []
    for part in parts:
        if part:
            converted, warnings = converter_fn(part)
            converted_parts.append(converted)
            all_warnings.extend(warnings)
        else:
            converted_parts.append(part)

    # Reassemble: interleave converted text parts with original tags
    result = []
    for i, cp in enumerate(converted_parts):
        result.append(cp)
        if i < len(tags):
            result.append(tags[i])
    return ''.join(result), all_warnings


# ---------------------------------------------------------------------------
# Word field conversion pipeline
# ---------------------------------------------------------------------------

def _escape_trailing_i(text):
    """Escape trailing い as \\い for verb/adjective pitch tokens."""
    colon_idx = text.rfind(':')
    if colon_idx > 0 and text[colon_idx - 1] == 'い':
        if colon_idx >= 2 and text[colon_idx - 2] == '\\':
            return text  # already escaped
        pitch = text[colon_idx + 1:].split()[0]  # ignore ' -' suffix
        if 'h' in pitch or 'k' in pitch:
            text = text[:colon_idx - 1] + '\\い' + text[colon_idx:]
    return text


# Matches tokens ending with a numeric-only pitch (no verb/adjective letter)
_NUMERIC_PITCH_END_RE = re.compile(r':[0-9,~]+$')


def _convert_word_text(text):
    """Convert a plain-text word field segment (no HTML).

    Returns (converted, warnings).
    """
    warnings = []
    tokens = text.split()
    converted_tokens = []
    for token in tokens:
        conv, w = _convert_single_token(token)
        conv = _escape_trailing_i(conv)
        if _NUMERIC_PITCH_END_RE.search(conv):
            conv = conv + '-'
        converted_tokens.append(conv)
        warnings.extend(w)
    return ' '.join(converted_tokens), warnings


def convert_word_field(text):
    """Word field: old → new pitch syntax. Returns (converted, warnings)."""
    if not text or not has_old_syntax(text):
        return text, []
    return _convert_preserving_html(text, _convert_word_text)


# ---------------------------------------------------------------------------
# Sentence field conversion pipeline
# ---------------------------------------------------------------------------

def _convert_sentence_text(text):
    """Convert a plain-text sentence field segment (no HTML).

    Returns (converted, warnings).
    """
    warnings = []
    tokens = text.split(' ')

    # Step 1: Group compound tokens
    groups = _group_compound_tokens(tokens)

    # Step 2: Convert each group
    converted_tokens = []
    for group_type, letter, group_tokens, flag in groups:
        if flag:
            warnings.append(flag)

        if group_type == 'compound':
            merged, w = _convert_compound_group(group_tokens, letter)
            warnings.extend(w)
            converted_tokens.append(merged)
        elif group_type == 'single':
            # Single token with a pitch letter — convert it
            token = group_tokens[0]
            conv, w = _convert_single_token(token)
            conv = _escape_trailing_i(conv)
            converted_tokens.append(conv)
            warnings.extend(w)
        else:
            # Bare token — might still have old numeric pitch
            token = group_tokens[0]
            if _OLD_PITCHED_BRACKET.search(token) or (
                _PITCH_ONLY_BRACKET.search(token) and not _is_already_converted(token)
            ):
                conv, w = _convert_single_token(token)
                conv = _escape_trailing_i(conv)
                converted_tokens.append(conv)
                warnings.extend(w)
            else:
                converted_tokens.append(token)

    # Step 3: Add :p to bare particles between accented tokens
    converted_tokens = _add_particle_colons(converted_tokens)

    return ' '.join(converted_tokens), warnings


def convert_sentence_field(text):
    """Sentence/Definition field: old → new. Returns (converted, warnings)."""
    if not text or not has_old_syntax(text):
        return text, []
    return _convert_preserving_html(text, _convert_sentence_text)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def has_old_syntax(text):
    """True if text contains old-style notation (semicolon inside brackets)."""
    if not text:
        return False
    # Check for [reading;pitch] pattern
    if _OLD_PITCHED_BRACKET.search(text):
        return True
    # Check for kana[pitch] pattern — pitch-only brackets on kana words
    for m in _PITCH_ONLY_BRACKET.finditer(text):
        start = m.start()
        if start > 0:
            pre = text[:start]
            # Walk backwards to find the word before the bracket
            word = ''
            for ch in reversed(pre):
                if ch == ' ' or ch == '\n':
                    break
                word = ch + word
            if word and _is_all_kana(word):
                return True
    return False
