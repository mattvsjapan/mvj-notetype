"""Dev-only: look up pitch accent from daijisen.db and append to Notes field.

This file is excluded from packaging (see package_addon.sh).
It adds a button to the editor toolbar that:
1. Reads the Word field and strips pitch markup to get the bare word
2. Searches daijisen.db (keystore) for the word
3. Fetches drops/splits/audio from the pronunciations table
4. Writes pitch notation to Word and audio to Word Audio
"""

import os
import re
import shutil
import sqlite3
import subprocess

from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    Qt,
    QVBoxLayout,
)
from aqt.utils import showWarning, tooltip

from .notetype import NOTE_TYPE_NAME

_DB_PATH = os.path.join(os.path.dirname(__file__), "dictionary", "daijisen", "daijisen.db")
_NHK_DB_PATH = os.path.join(os.path.dirname(__file__), "dictionary", "nhk", "nhk.db")
_NHK_KINDS = ('accent', 'pattern')

# Strip bracket+semicolon notation: [たべる;2] → たべる
_BRACKET_PITCH_RE = re.compile(r'\[([^;\]]+);[\d]+\]')
# Strip furigana brackets: 食[た]べ → 食べ
_FURIGANA_RE = re.compile(r'\[[^\]]*\]')
# Strip colon+number: コーヒー:3 → コーヒー
_COLON_PITCH_RE = re.compile(r':[\d,]+-?')
# Strip devoiced marker
_DEVOICED_RE = re.compile(r'\*')


def _strip_pitch(word_field: str) -> str:
    """Strip pitch markup from the Word field to get the bare word."""
    # For multi-line (split compound), take last line (the full word form)
    lines = re.split(r'<br\s*/?>|\n', word_field)
    text = next((l for l in reversed(lines) if l.strip()), word_field)
    # Extract readings from bracket+semicolon notation: [たべる;2] → たべる
    text = _BRACKET_PITCH_RE.sub(r'\1', text)
    # Remove furigana brackets: 食[た]べ → 食べ
    text = _FURIGANA_RE.sub('', text)
    # Remove colon+pitch numbers
    text = _COLON_PITCH_RE.sub('', text)
    # Remove devoiced markers
    text = _DEVOICED_RE.sub('', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove furigana spaces and strip
    text = text.replace(' ', '').strip()
    if not text:
        return ''
    # Take first meaningful token (split on /)
    tokens = re.split(r'/+', text)
    return tokens[0].strip() if tokens else ''


def _hira_to_kata(text: str) -> str:
    """Convert hiragana to katakana."""
    return ''.join(
        chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c
        for c in text
    )


def _find_entries(word: str, conn: sqlite3.Connection) -> list[str]:
    """Find all matching entry IDs via the keystore."""
    cur = conn.cursor()
    # keystore keys store kana parts as katakana; try both directions plus raw.
    candidates = sorted({word, _hira_to_kata(word), _katakana_to_hiragana(word)})
    placeholders = ','.join('?' * len(candidates))
    cur.execute(
        f"SELECT entry_id FROM keystore WHERE key IN ({placeholders})",
        candidates,
    )
    ids = {row[0] for row in cur.fetchall()}
    if not ids:
        return []

    # Exclude entries with no pitch data.
    cur2 = conn.cursor()
    placeholders = ','.join('?' * len(ids))
    cur2.execute(
        f"SELECT DISTINCT entry_id FROM pronunciations "
        f"WHERE entry_id IN ({placeholders}) AND drops IS NOT NULL",
        sorted(ids),
    )
    return sorted(row[0] for row in cur2.fetchall())


def _get_pitch(entry_id: str, conn: sqlite3.Connection) -> list[tuple[str, str | None, str | None]] | None:
    """Get distinct (drops, splits, audio_file) tuples for a single entry."""
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT drops, splits, audio_file FROM pronunciations "
        "WHERE entry_id = ? AND drops IS NOT NULL "
        "ORDER BY position",
        (entry_id,),
    )
    rows = [(r[0], r[1], r[2]) for r in cur.fetchall() if r[0]]
    return rows or None


_READING_STRIP_RE = re.compile(r'[・‐=＝┊×▽△]')
_READING_KEEP_SEP_RE = re.compile(r'[・=＝┊×▽△]')

_SMALL_KANA = set('ょゃゅァィゥェォャュョぁぃぅぇぉ')


def _count_morae(kana: str) -> int:
    """Count morae in a kana string. Small kana don't count as separate morae."""
    return sum(1 for c in kana if c not in _SMALL_KANA)


def _take_morae(kana: str, n: int) -> str:
    """Return the prefix of kana containing exactly n morae."""
    count = 0
    for i, c in enumerate(kana):
        if c not in _SMALL_KANA:
            count += 1
            if count > n:
                return kana[:i]
    return kana


def _get_reading(entry_id: str, conn: sqlite3.Connection) -> tuple[str, str] | None:
    """Get the kana reading for an entry.

    Returns (clean_reading, raw_reading_with_‐_separators) or None.
    """
    cur = conn.cursor()
    cur.execute("SELECT form FROM entries WHERE id = ? LIMIT 1", (entry_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    raw = row[0]
    clean = _READING_STRIP_RE.sub('', raw)
    raw_with_sep = _READING_KEEP_SEP_RE.sub('', raw)
    if not clean:
        return None
    return (clean, raw_with_sep)


# writings is wrapped as 【…】 (or 《…》 in NHK for uncommon kanji), with `・`
# separating variants; ×/▽/＝ are markers.
_WRITING_MARKER_RE = re.compile(r'[【】《》×▽＝=]')


def _extract_hyouki(writings: str | None) -> str | None:
    """Extract the primary kanji form from entries.writings ('【食べる】' → '食べる')."""
    if not writings:
        return None
    first = writings.strip('【】').split('・')[0]
    return _WRITING_MARKER_RE.sub('', first).strip() or None


def _extract_nhk_hyouki(headline: str | None) -> str | None:
    """Extract the kanji form from NHK headline.

    Common form uses 【】 ('たべる【食べる】' → '食べる'); uncommon kanji use
    《》 ('くぎ《×釘》' → '釘').
    """
    if not headline:
        return None
    m = re.search(r'[【《](.+?)[】》]', headline)
    if not m:
        return None
    return _extract_hyouki(f'【{m.group(1)}】')


def _find_entries_nhk(word: str, conn: sqlite3.Connection) -> list[str]:
    """Find NHK entry IDs for a word, restricted to those with usable pron rows."""
    cur = conn.cursor()
    candidates = sorted({word, _hira_to_kata(word), _katakana_to_hiragana(word)})
    placeholders = ','.join('?' * len(candidates))
    cur.execute(
        f"SELECT entry_id FROM keystore WHERE key IN ({placeholders})",
        candidates,
    )
    ids = {row[0] for row in cur.fetchall()}
    if not ids:
        return []
    id_ph = ','.join('?' * len(ids))
    kind_ph = ','.join('?' * len(_NHK_KINDS))
    cur.execute(
        f"SELECT DISTINCT entry_id FROM pronunciations "
        f"WHERE entry_id IN ({id_ph}) AND kind IN ({kind_ph}) "
        f"AND drops IS NOT NULL",
        sorted(ids) + list(_NHK_KINDS),
    )
    return sorted(row[0] for row in cur.fetchall())


def _find_nhk_particle_siblings(bare_id: str, conn: sqlite3.Connection) -> list[str]:
    """Return sibling entry IDs of `bare_id` representing the bare word + a
    generic case particle (を/に) and having usable accent/pattern pron rows.

    NHK encodes 'X + を' as a separate entry with the same numeric prefix and a
    suffix other than -0000 (typically -0001), with form like '合方を' and an
    empty headline. These never reach the keystore, so we walk siblings here.
    """
    prefix = bare_id.split('-')[0] + '-'
    kind_ph = ','.join('?' * len(_NHK_KINDS))
    cur = conn.cursor()
    cur.execute(
        f"SELECT DISTINCT e.id FROM entries e "
        f"WHERE e.id LIKE ? AND e.id != ? "
        f"AND (e.headline IS NULL OR e.headline = '') "
        f"AND (e.form LIKE '%を' OR e.form LIKE '%に') "
        f"AND EXISTS (SELECT 1 FROM pronunciations p WHERE p.entry_id = e.id "
        f"AND p.kind IN ({kind_ph}) AND p.drops IS NOT NULL) "
        f"ORDER BY e.id",
        [prefix + '%', bare_id, *_NHK_KINDS],
    )
    return [row[0] for row in cur.fetchall()]


def _get_nhk_pitch(entry_id: str, conn: sqlite3.Connection):
    """Distinct (drops, splits, audio_file, devoiced) for an NHK entry's accent/pattern rows."""
    cur = conn.cursor()
    kind_ph = ','.join('?' * len(_NHK_KINDS))
    cur.execute(
        f"SELECT DISTINCT drops, splits, audio_file, devoiced FROM pronunciations "
        f"WHERE entry_id = ? AND kind IN ({kind_ph}) AND drops IS NOT NULL "
        f"ORDER BY position",
        (entry_id, *_NHK_KINDS),
    )
    rows = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall() if r[0]]
    return rows or None


def _nhk_devoiced_for_word(word: str, conn: sqlite3.Connection) -> tuple[dict[str, str], str | None]:
    """Map drops -> devoiced for NHK accent/pattern rows matching `word`.

    Returns (by_drops, fallback) where fallback is any non-empty devoiced
    string from a matching row (used when an exact drops match is missing).
    """
    cur = conn.cursor()
    candidates = sorted({word, _hira_to_kata(word), _katakana_to_hiragana(word)})
    placeholders = ','.join('?' * len(candidates))
    kind_ph = ','.join('?' * len(_NHK_KINDS))
    cur.execute(
        f"SELECT p.drops, p.devoiced FROM pronunciations p "
        f"JOIN keystore k ON k.entry_id = p.entry_id "
        f"WHERE k.key IN ({placeholders}) "
        f"AND p.kind IN ({kind_ph}) "
        f"AND p.drops IS NOT NULL "
        f"AND p.devoiced IS NOT NULL AND p.devoiced != ''",
        candidates + list(_NHK_KINDS),
    )
    by_drops: dict[str, str] = {}
    fallback: str | None = None
    for drops, devoiced in cur.fetchall():
        if drops not in by_drops:
            by_drops[drops] = devoiced
        if fallback is None:
            fallback = devoiced
    return by_drops, fallback


def _inject_devoiced_aligned(aligned: str, devoiced: str | None) -> str:
    """Insert `*` before each devoiced mora (NHK uses 1-indexed positions).

    Walks `aligned` (which may contain `kanji[reading]` brackets and trailing
    kana). Counts morae across both bracket-internal kana and kana outside,
    skipping kanji. Inserts `*` before each char that begins a devoiced mora.
    """
    if not devoiced or not aligned:
        return aligned
    positions = {int(p) for p in devoiced.split(',') if p.strip().isdigit()}
    if not positions:
        return aligned
    out: list[str] = []
    mora = 0
    in_bracket = False
    for c in aligned:
        if c == '[':
            in_bracket = True
            out.append(c)
            continue
        if c == ']':
            in_bracket = False
            out.append(c)
            continue
        if in_bracket or not _is_kanji(c):
            if c not in _SMALL_KANA and c not in (' ', '・', '‐', '＝', '='):
                mora += 1
                if mora in positions:
                    out.append('*')
        out.append(c)
    return ''.join(out)


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana."""
    return ''.join(
        chr(ord(c) - 0x60) if '\u30A1' <= c <= '\u30F6' else c
        for c in text
    )


def _is_kanji(char: str) -> bool:
    """Check if a single character is kanji or needs ruby annotation (like digits)."""
    if '\u4E00' <= char <= '\u9FFF':
        return True
    if '0' <= char <= '9':
        return True
    if '\u3005' <= char <= '\u3007':
        return True
    return False


def _segment_surface(surface: str) -> list[tuple[str, bool]]:
    """Segment surface into alternating (text, is_kanji) runs."""
    if not surface:
        return []
    segments: list[tuple[str, bool]] = []
    current = ""
    current_kind = _is_kanji(surface[0])
    for char in surface:
        kind = _is_kanji(char)
        if kind == current_kind:
            current += char
        else:
            if current:
                segments.append((current, current_kind))
            current = char
            current_kind = kind
    if current:
        segments.append((current, current_kind))
    return segments


def _find_anchor_candidates(
    segments: list[tuple[str, bool]], reading: str
) -> list[list]:
    """Find kana anchors and their candidate positions in reading.

    Returns list of [kana_text, segment_index, [candidate_positions]].
    """
    anchors = []
    for i, (text, is_k) in enumerate(segments):
        if not is_k:
            kana = _katakana_to_hiragana(text)
            candidates = []
            pos = 0
            while True:
                idx = reading.find(kana, pos)
                if idx == -1:
                    break
                candidates.append(idx)
                pos = idx + 1
            anchors.append([kana, i, candidates])
    return anchors


def _strip_edge_kana(
    segments: list[tuple[str, bool]], reading: str
) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]], str, list[tuple[str, bool]]]:
    """Strip definite leading/trailing kana from segments and reading.

    Returns (prefix_segments, remaining_segments, remaining_reading, suffix_segments).
    """
    prefix: list[tuple[str, bool]] = []
    suffix: list[tuple[str, bool]] = []
    remaining = list(segments)
    rem_reading = reading

    while remaining and not remaining[0][1]:
        text = remaining[0][0]
        kana = _katakana_to_hiragana(text)
        if rem_reading.startswith(kana):
            prefix.append(remaining[0])
            rem_reading = rem_reading[len(kana):]
            remaining = remaining[1:]
        else:
            break

    while remaining and not remaining[-1][1]:
        text = remaining[-1][0]
        kana = _katakana_to_hiragana(text)
        if rem_reading.endswith(kana):
            suffix.insert(0, remaining[-1])
            rem_reading = rem_reading[:-len(kana)]
            remaining = remaining[:-1]
        else:
            break

    return prefix, remaining, rem_reading, suffix


def _eliminate_invalid_positions(
    anchors: list[list], segments: list[tuple[str, bool]], reading: str
) -> list[list]:
    """Prune anchor positions that would give any kanji segment an empty reading."""
    if not anchors:
        return anchors

    kanji_before = []
    kanji_count = 0
    anchor_idx = 0
    for i, (_, is_k) in enumerate(segments):
        if is_k:
            kanji_count += 1
        else:
            if anchor_idx < len(anchors) and anchors[anchor_idx][1] == i:
                kanji_before.append(kanji_count)
                anchor_idx += 1

    kanji_after = []
    kanji_count = 0
    anchor_idx = len(anchors) - 1
    for i in range(len(segments) - 1, -1, -1):
        _, is_k = segments[i]
        if is_k:
            kanji_count += 1
        else:
            if anchor_idx >= 0 and anchors[anchor_idx][1] == i:
                kanji_after.insert(0, kanji_count)
                anchor_idx -= 1

    for i, anchor in enumerate(anchors):
        kana_len = len(anchor[0])
        valid = []
        for pos in anchor[2]:
            if kanji_before[i] > 0 and pos == 0:
                continue
            end_pos = pos + kana_len
            if kanji_after[i] > 0 and end_pos >= len(reading):
                continue
            valid.append(pos)
        anchor[2] = valid

    return anchors


def _enumerate_valid_combinations(
    anchors: list[list], reading_len: int
) -> list[list[int]]:
    """Enumerate all valid anchor position combinations (sequential, non-overlapping)."""
    if not anchors:
        return [[]]

    def backtrack(idx: int, min_pos: int, current: list[int]) -> list[list[int]]:
        if idx == len(anchors):
            return [current[:]]
        results = []
        for pos in anchors[idx][2]:
            if pos < min_pos:
                continue
            current.append(pos)
            results.extend(backtrack(idx + 1, pos + len(anchors[idx][0]), current))
            current.pop()
        return results

    return backtrack(0, 0, [])


def _build_bracket_notation(
    segments: list[tuple[str, bool]],
    reading: str,
    anchors: list[list],
    positions: list[int],
) -> str:
    """Build Anki bracket notation from resolved anchor positions.

    E.g. 食[た]べ 物[もの]
    Space before each non-initial kanji segment.
    """
    parts = []
    reading_pos = 0
    anchor_idx = 0
    first_segment = True

    for text, is_k in segments:
        if is_k:
            if anchor_idx < len(anchors):
                kanji_end = positions[anchor_idx]
            else:
                kanji_end = len(reading)
            kanji_reading = reading[reading_pos:kanji_end]
            reading_pos = kanji_end

            if not first_segment:
                parts.append(' ')
            if kanji_reading:
                parts.append(f'{text}[{kanji_reading}]')
            else:
                parts.append(text)
            first_segment = False
        else:
            kana_len = len(_katakana_to_hiragana(text))
            reading_pos += kana_len
            parts.append(text)
            anchor_idx += 1
            first_segment = False

    return ''.join(parts)


def _align_reading(surface: str, reading: str) -> str:
    """Align a surface form with its reading using Anki bracket notation.

    Returns e.g. '食[た]べ 物[もの]' or falls back to 'surface[reading]'.
    """
    reading = _katakana_to_hiragana(reading)

    if surface == reading:
        return surface

    segments = _segment_surface(surface)
    if not segments:
        return surface

    # Strip edge kana
    prefix, remaining, rem_reading, suffix = _strip_edge_kana(segments, reading)

    if not remaining:
        return surface

    has_kanji = any(is_k for _, is_k in remaining)
    if not has_kanji:
        return surface

    # Find anchors in remaining segments
    anchors = _find_anchor_candidates(remaining, rem_reading)

    def _try_resolve(anchors, remaining, rem_reading):
        """Try to resolve with current anchors. Returns bracket string or None."""
        if all(len(a[2]) == 1 for a in anchors):
            positions = [a[2][0] for a in anchors]
            return _build_bracket_notation(remaining, rem_reading, anchors, positions)
        return None

    # Easy case
    result = _try_resolve(anchors, remaining, rem_reading)
    if result is not None:
        parts = [t for t, _ in prefix] + [result] + [t for t, _ in suffix]
        return ''.join(parts)

    # Eliminate invalid positions
    anchors = _eliminate_invalid_positions(anchors, remaining, rem_reading)

    if any(len(a[2]) == 0 for a in anchors):
        return f'{surface}[{reading}]'

    result = _try_resolve(anchors, remaining, rem_reading)
    if result is not None:
        parts = [t for t, _ in prefix] + [result] + [t for t, _ in suffix]
        return ''.join(parts)

    # Enumerate combinations
    combos = _enumerate_valid_combinations(anchors, len(rem_reading))

    if not combos:
        return f'{surface}[{reading}]'

    if len(combos) == 1:
        result = _build_bracket_notation(remaining, rem_reading, anchors, combos[0])
        parts = [t for t, _ in prefix] + [result] + [t for t, _ in suffix]
        return ''.join(parts)

    # Check if all combos agree on each anchor position
    unique_positions: list[int | None] = []
    for i in range(len(anchors)):
        pos_set = set(c[i] for c in combos)
        unique_positions.append(pos_set.pop() if len(pos_set) == 1 else None)

    if all(p is not None for p in unique_positions):
        positions = [p for p in unique_positions if p is not None]
        result = _build_bracket_notation(remaining, rem_reading, anchors, positions)
        parts = [t for t, _ in prefix] + [result] + [t for t, _ in suffix]
        return ''.join(parts)

    # Ambiguous — whole-word fallback
    return f'{surface}[{reading}]'


def _split_surface(surface: str, reading1: str, reading2: str) -> tuple[str, str]:
    """Split a surface form into two parts matching the given readings."""
    reading1_h = _katakana_to_hiragana(reading1)
    reading2_h = _katakana_to_hiragana(reading2)

    # Match kana from end of surface with end of reading2
    suffix_len = 0
    while (suffix_len < len(surface) and suffix_len < len(reading2_h)
           and _katakana_to_hiragana(surface[-(suffix_len + 1)]) == reading2_h[-(suffix_len + 1)]):
        suffix_len += 1

    # Match kana from start of surface with start of reading1
    prefix_len = 0
    limit = len(surface) - suffix_len
    while (prefix_len < limit and prefix_len < len(reading1_h)
           and _katakana_to_hiragana(surface[prefix_len]) == reading1_h[prefix_len]):
        prefix_len += 1

    middle = surface[prefix_len:len(surface) - suffix_len] if suffix_len else surface[prefix_len:]
    if not middle:
        return surface[:prefix_len], surface[prefix_len:]

    # Distribute remaining kanji proportionally by morae
    morae1 = _count_morae(reading1_h[prefix_len:])
    morae2 = _count_morae(reading2_h[:len(reading2_h) - suffix_len]) if suffix_len else _count_morae(reading2_h)
    total = morae1 + morae2
    if total == 0:
        split_at = len(middle) // 2
    else:
        split_at = round(len(middle) * morae1 / total)
        split_at = max(1 if morae1 > 0 else 0,
                       min(split_at, len(middle) - (1 if morae2 > 0 else 0)))

    cut = prefix_len + split_at
    return surface[:cut], surface[cut:]


def _split_surface_n(surface: str, readings: list[str]) -> list[str]:
    """Split surface into N parts matching the given readings."""
    if len(readings) <= 1:
        return [surface]
    if len(readings) == 2:
        return list(_split_surface(surface, readings[0], readings[1]))
    # Split off first part, recurse on remainder
    rest_reading = ''.join(readings[1:])
    s1, s_rest = _split_surface(surface, readings[0], rest_reading)
    return [s1] + _split_surface_n(s_rest, readings[1:])


def _split_compound(surface: str, raw_reading: str, split_str: str, pitch_drop: str) -> str:
    """Format a compound word as N pitch units split at the given mora boundaries."""
    split_points = [int(x) for x in split_str.split(',')]
    pitches = [p.strip() for p in pitch_drop.split(',')]
    n_parts = len(split_points) + 1

    if len(pitches) < n_parts:
        clean = _READING_STRIP_RE.sub('', raw_reading)
        aligned = _align_reading(surface, clean)
        return f"{aligned}:{pitch_drop}-"

    # Build part readings from morphemes or mora counts
    if '‐' in raw_reading:
        morphemes = [m.replace('・', '') for m in raw_reading.split('‐') if m]
        parts_morphemes: list[list[str]] = [[] for _ in range(n_parts)]
        cumulative = 0
        part_idx = 0
        for m in morphemes:
            cumulative += _count_morae(m)
            while part_idx < len(split_points) and cumulative > split_points[part_idx]:
                part_idx += 1
            parts_morphemes[min(part_idx, n_parts - 1)].append(m)
        parts_readings = [''.join(pm) for pm in parts_morphemes]
    else:
        clean = _READING_STRIP_RE.sub('', raw_reading)
        parts_readings = []
        remaining = clean
        prev = 0
        for sp in split_points:
            part = _take_morae(remaining, sp - prev)
            parts_readings.append(part)
            remaining = remaining[len(part):]
            prev = sp
        parts_readings.append(remaining)

    if any(not r for r in parts_readings):
        clean = _READING_STRIP_RE.sub('', raw_reading)
        aligned = _align_reading(surface, clean)
        return f"{aligned}:{pitch_drop}-"

    parts_surfaces = _split_surface_n(surface, parts_readings)
    formatted = [f"{_align_reading(s, r)}:{p}"
                 for s, r, p in zip(parts_surfaces, parts_readings, pitches)]
    return ' / '.join(formatted) + '-'


def _entry_display(entry_id: str, conn: sqlite3.Connection, source: str = 'daijisen') -> str:
    """Build a display string for a single entry (for the picker list)."""
    cur = conn.cursor()

    if source == 'nhk':
        cur.execute("SELECT form, headline FROM entries WHERE id = ? LIMIT 1", (entry_id,))
        row = cur.fetchone()
        reading = row[0] if row and row[0] else "?"
        label = None
        if row and row[1]:
            # Headline is `<kana>【<kanji>】<optional annotations>` — keep everything
            # from the first 【 onward so place-name / category tags disambiguate.
            idx = row[1].find('【')
            label = row[1][idx:] if idx >= 0 else None
        rows = _get_nhk_pitch(entry_id, conn)
        pitch_list = [r[0] for r in rows] if rows else []
    else:
        cur.execute("SELECT form, writings FROM entries WHERE id = ? LIMIT 1", (entry_id,))
        row = cur.fetchone()
        reading = row[0] if row and row[0] else "?"
        label = row[1] if row else None
        rows = _get_pitch(entry_id, conn)
        pitch_list = [r[0] for r in rows] if rows else []

    pitch = ', '.join(pitch_list) if pitch_list else "—"

    defn = ""
    if source == 'daijisen':
        cur.execute(
            "SELECT definition FROM senses WHERE entry_id = ? ORDER BY sense_number LIMIT 1",
            (entry_id,),
        )
        row = cur.fetchone()
        if row and row[0]:
            defn = re.sub(r'\[\[[^|]*\|([^\]]+)\]\]', r'\1', row[0])
            defn = re.sub(r'\[\[([^\]]+)\]\]', r'\1', defn)
            defn = re.sub(r'<[^>]+>', '', defn)[:80]

    parts = [reading]
    if label:
        parts.append(label)
    parts.append(f"[{pitch}]")
    if defn:
        parts.append(f"— {defn}")
    return " ".join(parts)


def _show_entry_picker(
    candidates: list[tuple[str, str]],
    word: str,
    conns: dict[str, sqlite3.Connection],
) -> tuple[str, str] | None:
    """Show a dialog with entries from one or more sources.

    candidates: list of (source, entry_id) pairs.
    Returns the selected (source, entry_id) or None if cancelled.
    """
    dlg = QDialog(mw)
    dlg.setWindowTitle("Select entry")
    dlg.setMinimumWidth(540)
    layout = QVBoxLayout(dlg)

    layout.addWidget(QLabel(f"Multiple entries match <b>{word}</b>:"))

    lst = QListWidget()
    for src, eid in candidates:
        tag = '[daijisen]' if src == 'daijisen' else '[NHK]'
        item = QListWidgetItem(f"{tag} {_entry_display(eid, conns[src], src)}")
        item.setData(Qt.ItemDataRole.UserRole, (src, eid))
        lst.addItem(item)
    lst.setCurrentRow(0)
    layout.addWidget(lst)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    lst.itemDoubleClicked.connect(dlg.accept)
    layout.addWidget(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    sel = lst.currentItem()
    return sel.data(Qt.ItemDataRole.UserRole) if sel else None


def _lookup_note(editor: Editor):
    note = editor.note
    if note is None:
        showWarning("No note loaded.")
        return

    model = note.note_type()
    if model is None or model["name"] != NOTE_TYPE_NAME:
        showWarning(f"This note is not a {NOTE_TYPE_NAME} note.")
        return

    field_names = [f["name"] for f in model["flds"]]
    for needed in ("Word", "Notes"):
        if needed not in field_names:
            showWarning(f"Note is missing {needed} field.")
            return

    word_idx = field_names.index("Word")

    raw_word = note.fields[word_idx]
    word = _strip_pitch(raw_word)
    if not word:
        tooltip("Word field is empty.")
        return

    if not os.path.exists(_DB_PATH) and not os.path.exists(_NHK_DB_PATH):
        tooltip("No dictionary databases found.")
        return

    daijisen_conn = (
        sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
        if os.path.exists(_DB_PATH) else None
    )
    nhk_conn = (
        sqlite3.connect(f"file:{_NHK_DB_PATH}?mode=ro", uri=True)
        if os.path.exists(_NHK_DB_PATH) else None
    )

    source: str | None = None
    selected: str | None = None
    pitch_rows: list[tuple[str, str | None, str | None, str | None]] | None = None
    reading_info: tuple[str, str] | None = None
    hyouki: str | None = None

    try:
        candidates: list[tuple[str, str]] = []
        if daijisen_conn:
            candidates += [('daijisen', eid) for eid in _find_entries(word, daijisen_conn)]
        if nhk_conn:
            for bare_id in _find_entries_nhk(word, nhk_conn):
                candidates.append(('nhk', bare_id))
                for sib in _find_nhk_particle_siblings(bare_id, nhk_conn):
                    candidates.append(('nhk', sib))

        if not candidates:
            tooltip(f"No match found for: {word}")
            return

        if len(candidates) == 1:
            source, selected = candidates[0]
        else:
            conns = {}
            if daijisen_conn:
                conns['daijisen'] = daijisen_conn
            if nhk_conn:
                conns['nhk'] = nhk_conn
            picked = _show_entry_picker(candidates, word, conns)
            if picked is None:
                return
            source, selected = picked

        if source == 'daijisen':
            assert daijisen_conn is not None
            rows3 = _get_pitch(selected, daijisen_conn)
            if rows3:
                pitch_rows = [(d, s, a, None) for (d, s, a) in rows3]
                reading_info = _get_reading(selected, daijisen_conn)
                cur = daijisen_conn.cursor()
                cur.execute("SELECT writings FROM entries WHERE id = ? LIMIT 1", (selected,))
                row = cur.fetchone()
                hyouki = _extract_hyouki(row[0] if row else None)
        else:
            assert nhk_conn is not None
            rows4 = _get_nhk_pitch(selected, nhk_conn)
            if rows4:
                cur = nhk_conn.cursor()
                cur.execute("SELECT headline FROM entries WHERE id = ? LIMIT 1", (selected,))
                e_row = cur.fetchone()
                e_headline = e_row[0] if e_row else None
                if e_headline:
                    pitch_rows = rows4
                    reading_info = _get_reading(selected, nhk_conn)
                    hyouki = _extract_nhk_hyouki(e_headline)
                else:
                    # Particle sub-entry: write the bare word's text but use the
                    # +particle audio (which actually voices the trailing particle).
                    bare_id = selected.split('-')[0] + '-0000'
                    bare_rows = _get_nhk_pitch(bare_id, nhk_conn)
                    if bare_rows:
                        particle_audio_by_drops = {
                            d: a for (d, _s, a, _dv) in rows4 if a
                        }
                        fallback_audio = next(iter(particle_audio_by_drops.values()), None)
                        pitch_rows = [
                            (d, s, particle_audio_by_drops.get(d, fallback_audio), dv)
                            for (d, s, _a, dv) in bare_rows
                        ]
                        reading_info = _get_reading(bare_id, nhk_conn)
                        cur.execute(
                            "SELECT headline FROM entries WHERE id = ? LIMIT 1",
                            (bare_id,),
                        )
                        b_row = cur.fetchone()
                        hyouki = _extract_nhk_hyouki(b_row[0] if b_row else None)
                    else:
                        pitch_rows = rows4
                        reading_info = _get_reading(selected, nhk_conn)
                        hyouki = None

        if pitch_rows is None:
            tooltip(f"No pitch data for: {word}")
            return

        # When daijisen is primary, enrich each variant with NHK devoicing.
        if source == 'daijisen' and nhk_conn:
            by_drops, fallback = _nhk_devoiced_for_word(word, nhk_conn)
            pitch_rows = [
                (d, s, a, by_drops.get(d) or fallback)
                for (d, s, a, _) in pitch_rows
            ]
    finally:
        if daijisen_conn:
            daijisen_conn.close()
        if nhk_conn:
            nhk_conn.close()

    if reading_info:
        clean_reading, raw_reading = reading_info
    else:
        clean_reading, raw_reading = None, None

    lines: list[str] = []
    audio_files: list[str] = []
    for pitch_drop, split, audio, devoiced in pitch_rows:
        if split is not None and raw_reading:
            line = _split_compound(word, raw_reading, split, pitch_drop)
        else:
            word_value = _align_reading(word, clean_reading) if clean_reading else word
            word_value = _inject_devoiced_aligned(word_value, devoiced)
            line = f"{word_value}:{pitch_drop}-"
        lines.append(line)
        if audio:
            audio_files.append(audio)

    note.fields[word_idx] = '<br>'.join(lines)

    # Copy audio files and populate Word Audio field
    if audio_files and "Word Audio" in field_names:
        seen: set[tuple[str, str]] = set()
        unique_pairs: list[tuple[str, str]] = []
        for (pitch_drop, _split, audio, _dv) in pitch_rows:
            if audio and (audio, str(pitch_drop)) not in seen:
                seen.add((audio, str(pitch_drop)))
                unique_pairs.append((audio, str(pitch_drop)))

        if source == 'daijisen':
            audio_dir = os.path.join(os.path.dirname(__file__), "dictionary", "daijisen", "audio")
            audio_suffix = 'DAIJISEN2'
        else:
            audio_dir = os.path.join(os.path.dirname(__file__), "dictionary", "nhk", "audio")
            audio_suffix = 'NHK'
        media_dir = mw.col.media.dir()
        # macOS GUI apps don't inherit the shell PATH, so resolve ffmpeg explicitly.
        ffmpeg = shutil.which('ffmpeg') or next(
            (p for p in ('/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg') if os.path.exists(p)),
            None,
        )
        ext = '.mp3' if ffmpeg else '.aac'
        _strip_parens = lambda s: re.sub(r'[（）()]', '', s) if s else s
        h_clean = _strip_parens(hyouki)
        r_clean = _strip_parens(clean_reading)
        new_names: list[str] = []
        for orig_audio, pitch in unique_pairs:
            pitch_part = pitch.replace(',', '-')
            if h_clean and r_clean and h_clean != r_clean:
                new_name = f"{h_clean}_{r_clean}_{pitch_part}_{audio_suffix}{ext}"
            elif h_clean:
                new_name = f"{h_clean}_{pitch_part}_{audio_suffix}{ext}"
            else:
                new_name = os.path.splitext(orig_audio)[0] + ext
            src = os.path.join(audio_dir, orig_audio)
            dst = os.path.join(media_dir, new_name)
            if os.path.exists(src) and not os.path.exists(dst):
                if ffmpeg:
                    subprocess.run(
                        [ffmpeg, '-i', src, '-q:a', '2', dst],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    shutil.copyfile(src, dst)
            new_names.append(new_name)

        audio_idx = field_names.index("Word Audio")
        existing = note.fields[audio_idx]
        new_tags = [
            f'[audio:{name}]' for name in new_names
            if f'[audio:{name}]' not in existing
        ]
        if new_tags:
            sep = '<br>' if existing.strip() else ''
            note.fields[audio_idx] = (existing.rstrip() + sep + '<br>'.join(new_tags)).strip()

    if note.id:
        mw.col.update_note(note)
    editor.loadNoteKeepingFocus()
    display = ', '.join(r[0] for r in pitch_rows)
    tooltip(f"{word} → {display} ({source})")


def _add_lookup_button(buttons, editor: Editor):
    btn = editor.addButton(
        icon=None,
        cmd="lookup_pitch",
        func=lambda e=editor: _lookup_note(e),
        tip="Look up pitch accent from daijisen.db",
        label="\u2197",
        disables=False,
    )
    buttons.append(btn)


gui_hooks.editor_did_init_buttons.append(_add_lookup_button)
