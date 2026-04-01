"""Dev-only: look up pitch accent from daijisen.db and append to Notes field.

This file is excluded from packaging (see package_addon.sh).
It adds a button to the editor toolbar that:
1. Reads the Word field and strips pitch markup to get the bare word
2. Searches daijisen.db for the word
3. Fetches pitch_drop values from the accents table
4. Appends the result to the Notes field
"""

import os
import re
import sqlite3

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

_DB_PATH = os.path.join(os.path.dirname(__file__), "dictionary", "daijisen.db")

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


def _find_entries(word: str, conn: sqlite3.Connection) -> list[str]:
    """Find all matching entry IDs across lookup and headword fields."""
    cur = conn.cursor()
    ids: set[str] = set()

    for query in (
        "SELECT id FROM lookup WHERE normalized = ?",
        "SELECT id FROM lookup WHERE reading = ?",
        "SELECT id FROM headwords WHERE 表記 = ?",
        "SELECT id FROM headwords WHERE 見出 = ?",
    ):
        cur.execute(query, (word,))
        ids.update(row[0] for row in cur.fetchall())

    if not ids:
        return []

    # Exclude entries with no pitch accent data
    cur2 = conn.cursor()
    placeholders = ','.join('?' * len(ids))
    cur2.execute(
        f"SELECT DISTINCT entry_id FROM accents WHERE entry_id IN ({placeholders}) AND pitch_drop IS NOT NULL",
        sorted(ids),
    )
    return sorted(row[0] for row in cur2.fetchall())


def _get_pitch(entry_id: str, conn: sqlite3.Connection) -> list[tuple[str, int | None]] | None:
    """Get distinct (pitch_drop, split) tuples for a single entry."""
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT pitch_drop, split FROM accents "
        "WHERE entry_id = ? AND pitch_drop IS NOT NULL ORDER BY priority",
        (entry_id,),
    )
    rows = [(r[0], r[1]) for r in cur.fetchall() if r[0]]
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


def _get_reading(entry_id: str, conn: sqlite3.Connection) -> tuple[str, str, str] | None:
    """Get reading info for an entry with a kanji form (表記).

    Returns (clean_reading, raw_reading_with_separators, surface) or None.
    """
    cur = conn.cursor()
    cur.execute("SELECT 見出, 表記 FROM headwords WHERE id = ? LIMIT 1", (entry_id,))
    row = cur.fetchone()
    if not row or not row[1]:
        return None
    raw = row[0]
    surface = row[1]
    clean = _READING_STRIP_RE.sub('', raw)
    raw_with_sep = _READING_KEEP_SEP_RE.sub('', raw)
    if not clean:
        return None
    return (clean, raw_with_sep, surface)


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


def _split_compound(surface: str, raw_reading: str, split_mora: int, pitch_drop: str) -> str:
    """Format a compound word as two pitch units split at the given mora boundary."""
    pitches = pitch_drop.split(',')
    if len(pitches) < 2:
        clean = _READING_STRIP_RE.sub('', raw_reading)
        aligned = _align_reading(surface, clean)
        return f"{aligned}:{pitch_drop}-"

    p1, p2 = pitches[0].strip(), pitches[1].strip()

    # Split reading into morphemes at ‐ separators
    if '‐' in raw_reading:
        morphemes = [m.replace('・', '') for m in raw_reading.split('‐') if m]
    else:
        # No morpheme separators — split by mora count directly
        clean = _READING_STRIP_RE.sub('', raw_reading)
        part1_reading = _take_morae(clean, split_mora)
        part2_reading = clean[len(part1_reading):]
        if not part1_reading or not part2_reading:
            aligned = _align_reading(surface, clean)
            return f"{aligned}:{pitch_drop}-"
        s1, s2 = _split_surface(surface, part1_reading, part2_reading)
        a1 = _align_reading(s1, part1_reading)
        a2 = _align_reading(s2, part2_reading)
        return f"{a1}:{p1} / {a2}:{p2}-"

    # Group morphemes by cumulative morae reaching split_mora
    part1_morphemes: list[str] = []
    part2_morphemes: list[str] = []
    cumulative = 0
    for m in morphemes:
        cumulative += _count_morae(m)
        if cumulative <= split_mora:
            part1_morphemes.append(m)
        else:
            part2_morphemes.append(m)

    if not part1_morphemes or not part2_morphemes:
        clean = _READING_STRIP_RE.sub('', raw_reading)
        aligned = _align_reading(surface, clean)
        return f"{aligned}:{pitch_drop}-"

    part1_reading = ''.join(part1_morphemes)
    part2_reading = ''.join(part2_morphemes)

    s1, s2 = _split_surface(surface, part1_reading, part2_reading)
    a1 = _align_reading(s1, part1_reading)
    a2 = _align_reading(s2, part2_reading)
    return f"{a1}:{p1} / {a2}:{p2}-"


def _entry_display(entry_id: str, conn: sqlite3.Connection) -> str:
    """Build a display string for a single entry (for the picker list)."""
    cur = conn.cursor()

    # Reading from lookup
    cur.execute("SELECT reading FROM lookup WHERE id = ? LIMIT 1", (entry_id,))
    row = cur.fetchone()
    reading = row[0] if row and row[0] else "?"

    # Headword from headwords
    cur.execute("SELECT 見出 FROM headwords WHERE id = ? LIMIT 1", (entry_id,))
    row = cur.fetchone()
    headword = row[0] if row and row[0] else ""

    # Pitch
    rows = _get_pitch(entry_id, conn)
    pitch = ', '.join(r[0] for r in rows) if rows else "—"

    # First definition preview
    cur.execute(
        "SELECT definition FROM senses WHERE entry_id = ? ORDER BY sense_number LIMIT 1",
        (entry_id,),
    )
    row = cur.fetchone()
    defn = ""
    if row and row[0]:
        defn = re.sub(r'\[\[[^|]*\|([^\]]+)\]\]', r'\1', row[0])
        defn = re.sub(r'\[\[([^\]]+)\]\]', r'\1', defn)
        defn = re.sub(r'<[^>]+>', '', defn)[:80]

    parts = [reading]
    if headword and headword != reading:
        parts.append(f"【{headword}】")
    parts.append(f"[{pitch}]")
    if defn:
        parts.append(f"— {defn}")
    return " ".join(parts)


def _show_entry_picker(entry_ids: list[str], word: str, conn: sqlite3.Connection) -> str | None:
    """Show a dialog to pick one entry. Returns entry ID or None."""
    dlg = QDialog(mw)
    dlg.setWindowTitle("Select entry")
    dlg.setMinimumWidth(500)
    layout = QVBoxLayout(dlg)

    layout.addWidget(QLabel(f"Multiple entries match <b>{word}</b>:"))

    lst = QListWidget()
    for eid in entry_ids:
        item = QListWidgetItem(_entry_display(eid, conn))
        item.setData(Qt.ItemDataRole.UserRole, eid)
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

    if not os.path.exists(_DB_PATH):
        tooltip("Dictionary database not found.")
        return

    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    try:
        entry_ids = _find_entries(word, conn)

        if not entry_ids:
            tooltip(f"No match found for: {word}")
            return

        if len(entry_ids) == 1:
            selected = entry_ids[0]
        else:
            selected = _show_entry_picker(entry_ids, word, conn)
            if selected is None:
                return

        pitch_rows = _get_pitch(selected, conn)
        reading_info = _get_reading(selected, conn)
    finally:
        conn.close()

    if pitch_rows is None:
        tooltip(f"No pitch accent found for: {word}")
        return

    if reading_info:
        clean_reading, raw_reading, surface = reading_info
    else:
        clean_reading, raw_reading, surface = None, None, None

    lines: list[str] = []
    for pitch_drop, split in pitch_rows:
        if split is not None and reading_info:
            line = _split_compound(surface, raw_reading, split, pitch_drop)
        else:
            word_value = _align_reading(surface, clean_reading) if reading_info else word
            line = f"{word_value}:{pitch_drop}-"
        lines.append(line)

    note.fields[word_idx] = '<br>'.join(lines)

    if note.id:
        mw.col.update_note(note)
    editor.loadNoteKeepingFocus()
    display = ', '.join(r[0] for r in pitch_rows)
    tooltip(f"{word} → {display}")


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
