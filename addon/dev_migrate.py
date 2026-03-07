"""Dev-only: migrate old Image-field pitch syntax into the Word field.

This file is excluded from packaging (see package_addon.sh).
It adds a button to the editor toolbar that:
1. Parses the Image field for <!-- generated using syntax: "..." --> comments
2. Converts the extracted syntax to new pitch accent notation
3. Puts the result in the Word field
4. Clears the Image field
5. Logs all changes to a file for safety
"""

import os
import re
from datetime import datetime

from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.utils import showWarning, tooltip

from .notetype import NOTE_TYPE_NAME
from .pitch_converter import convert_word_field

_LOG_DIR = os.path.join(os.path.dirname(__file__), "user_files")
_LOG_FILE = os.path.join(_LOG_DIR, "migration_log.txt")

_SYNTAX_COMMENT_RE = re.compile(
    r'<!--\s*generated using syntax:\s*"([^"]+)"\s*-->'
)
_AUDIO_RE = re.compile(r'\[audio:([^\]]+)\]')

# Matches [reading]okurigana;pitch — okurigana may be empty
_PITCH_OUTSIDE_RE = re.compile(r'\[([^\]]+)\]([^;\s]*);(\S+)')
_EMPTY_PITCH_RE = re.compile(r'\[([^\]]+)\]([^;\s]*);')
# d = devoiced → * prefix on reading (d can be after bracket or before reading)
_DEVOICED_AFTER_RE = re.compile(r'\[([^\]]+)\]d')
_DEVOICED_BEFORE_RE = re.compile(r'\[d([^\]]+)\]')

# Matches <li>DICT_NAME: PITCH_VALUES</li> in the context field
_CONTEXT_DICT_RE = re.compile(r'<li>([^<:]+):\s*(.*?)</li>')


def _reformat_token(text):
    """Reformat a single token from comment syntax to converter input."""
    # d modifier → * prefix inside bracket
    text = _DEVOICED_AFTER_RE.sub(r'[*\1]', text)
    text = _DEVOICED_BEFORE_RE.sub(r'[*\1]', text)
    # Move ;pitch inside brackets
    text = _PITCH_OUTSIDE_RE.sub(r'[\1;\3]\2', text)
    # Empty pitch (trailing ";") defaults to 0
    text = _EMPTY_PITCH_RE.sub(r'[\1;0]\2', text)
    return text


def _convert_comment_syntax(raw):
    """Convert full comment syntax string to new notation."""
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
        # Check if there's an accented token before and after
        has_before = any(':' in parts[j] for j in range(i))
        has_after = any(':' in parts[j] for j in range(i + 1, len(parts)))
        if has_before and has_after:
            parts[i] = parts[i] + ':'
    result = ' '.join(parts)

    return result, all_warnings


def _log(note_id, word_before, image_before, word_after):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"=== {datetime.now().isoformat()} | nid:{note_id} ===\n")
        f.write(f"Word BEFORE:  {word_before}\n")
        f.write(f"Image BEFORE: {image_before}\n")
        f.write(f"Word AFTER:   {word_after}\n")
        f.write("\n")


def _context_to_dict_table(html):
    """Convert Context field dictionary list HTML to a table."""
    entries = _CONTEXT_DICT_RE.findall(html)
    if not entries:
        return None
    rows = ''.join(
        f'<tr><td>{name.strip()}</td><td>{re.sub(r"]\\[", "] [", re.sub(r"</?b>", "", values.strip()))}</td></tr>'
        for name, values in entries
    )
    return f'<table class="dict-table">{rows}</table>'


def _migrate_note(editor: Editor):
    note = editor.note
    if note is None:
        showWarning("No note loaded.")
        return

    model = note.note_type()
    if model is None or model["name"] != NOTE_TYPE_NAME:
        showWarning(f"This note is not a {NOTE_TYPE_NAME} note.")
        return

    field_names = [f["name"] for f in model["flds"]]
    for needed in ("Image", "Word", "Word Audio", "Sentence Audio", "Context", "Notes"):
        if needed not in field_names:
            showWarning(f"Note is missing {needed} field.")
            return

    img_idx = field_names.index("Image")
    word_idx = field_names.index("Word")
    word_audio_idx = field_names.index("Word Audio")
    sent_audio_idx = field_names.index("Sentence Audio")
    context_idx = field_names.index("Context")
    notes_idx = field_names.index("Notes")

    image_content = note.fields[img_idx]
    if not image_content.strip():
        tooltip("Image field is empty, nothing to migrate.")
        return

    m = _SYNTAX_COMMENT_RE.search(image_content)
    if not m:
        tooltip("No pitch syntax comment found in Image field.")
        return

    new_syntax, warnings = _convert_comment_syntax(m.group(1))

    # Move sentence audio from Word Audio to Sentence Audio:
    # - filenames containing "reibun"
    # - filenames with no Japanese characters (kanji/kana)
    word_audio = note.fields[word_audio_idx]
    audio_files = _AUDIO_RE.findall(word_audio)
    moved_audio = []
    for fname in audio_files:
        is_reibun = 'reibun' in fname
        has_japanese = any(
            '\u3040' <= ch <= '\u309f' or  # hiragana
            '\u30a0' <= ch <= '\u30ff' or  # katakana
            '\u4e00' <= ch <= '\u9fff' or  # CJK
            '\u3400' <= ch <= '\u4dbf'     # CJK ext A
            for ch in fname
        )
        if is_reibun or not has_japanese:
            tag = f"[audio:{fname}]"
            word_audio = word_audio.replace(tag, "")
            moved_audio.append(tag)
    if moved_audio:
        note.fields[word_audio_idx] = word_audio.strip()
        note.fields[sent_audio_idx] = (note.fields[sent_audio_idx] + ''.join(moved_audio)).strip()

    word_before = note.fields[word_idx]
    _log(note.id, word_before, image_content, new_syntax)

    note.fields[word_idx] = new_syntax
    note.fields[img_idx] = ""

    # Convert Context field dictionary list to table in Notes field
    context_content = note.fields[context_idx]
    dict_table = _context_to_dict_table(context_content) if context_content.strip() else None
    if dict_table:
        existing_notes = note.fields[notes_idx]
        note.fields[notes_idx] = (dict_table + existing_notes).strip()
        note.fields[context_idx] = ""

    note.flush()
    editor.loadNoteKeepingFocus()

    msg = f"Migrated: {new_syntax}"
    if dict_table:
        msg += " | Dict table → Notes"
    if moved_audio:
        msg += f" | Moved {len(moved_audio)} reibun audio to Sentence Audio"
    if warnings:
        msg += f" (warnings: {', '.join(warnings)})"
    tooltip(msg)


def _add_migrate_button(buttons, editor: Editor):
    btn = editor.addButton(
        icon=None,
        cmd="migrate_pitch",
        func=lambda e=editor: _migrate_note(e),
        tip="Migrate Image pitch syntax to Word field",
        label="💈",
        disables=False,
    )
    buttons.append(btn)


_DICT_TABLE_HTML = (
    '<table class="dict-table">'
    '<tr><td>大辞泉</td><td>[]</td></tr>'
    '<tr><td>ＮＨＫ</td><td>[]</td></tr>'
    '<tr><td>新明解</td><td>[]</td></tr>'
    '<tr><td>大辞林</td><td>[]</td></tr>'
    '<tr><td>三省堂</td><td>[]</td></tr>'
    '</table>'
)


def _insert_dict_table(editor: Editor):
    note = editor.note
    if note is None:
        showWarning("No note loaded.")
        return

    model = note.note_type()
    if model is None or model["name"] != NOTE_TYPE_NAME:
        showWarning(f"This note is not a {NOTE_TYPE_NAME} note.")
        return

    field_names = [f["name"] for f in model["flds"]]
    if "Notes" not in field_names:
        showWarning("Note is missing Notes field.")
        return

    notes_idx = field_names.index("Notes")
    existing = note.fields[notes_idx]

    if '<table>' in existing:
        tooltip("Notes field already contains a table.")
        return

    note.fields[notes_idx] = (_DICT_TABLE_HTML + existing).strip()
    note.flush()
    editor.loadNoteKeepingFocus()
    tooltip("Inserted dictionary table into Notes field.")


def _add_migrate_button(buttons, editor: Editor):
    btn = editor.addButton(
        icon=None,
        cmd="migrate_pitch",
        func=lambda e=editor: _migrate_note(e),
        tip="Migrate Image pitch syntax to Word field",
        label="💈",
        disables=False,
    )
    buttons.append(btn)
    btn2 = editor.addButton(
        icon=None,
        cmd="insert_dict_table",
        func=lambda e=editor: _insert_dict_table(e),
        tip="Insert dictionary lookup table into Notes field",
        label="📄",
        disables=False,
    )
    buttons.append(btn2)


gui_hooks.editor_did_init_buttons.append(_add_migrate_button)
