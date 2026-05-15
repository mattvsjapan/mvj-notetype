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
from .pitch_migration import (
    convert_comment_syntax as _convert_comment_syntax,
    mark_front_visible as _mark_front_visible,
    splice_word_kanji as _splice_word_kanji,
)

_LOG_DIR = os.path.join(os.path.dirname(__file__), "user_files")
_LOG_FILE = os.path.join(_LOG_DIR, "migration_log.txt")

_SYNTAX_COMMENT_RE = re.compile(
    r'<!--\s*generated using syntax:\s*"([^"]+)"\s*-->'
)
_AUDIO_RE = re.compile(r'\[audio:([^\]]+)\]')

# Matches <li>DICT_NAME: PITCH_VALUES</li> in the context field
_CONTEXT_DICT_RE = re.compile(r'<li>([^<:]+):\s*(.*?)</li>')


def _log(note_id, word_before, image_before, word_after):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"=== {datetime.now().isoformat()} | nid:{note_id} ===\n")
        f.write(f"Word BEFORE:  {word_before}\n")
        f.write(f"Image BEFORE: {image_before}\n")
        f.write(f"Word AFTER:   {word_after}\n")
        f.write("\n")


_DICT_NAMES = ('大辞泉', 'ＮＨＫ', '新明解', '大辞林', '新選', '三省堂', '例解')

# Inline styles so the table renders in the editor field view too — Anki's
# editor (desktop and mobile) doesn't apply the note type's card CSS to
# field content. Override from card CSS with !important if needed.
_TABLE_STYLE = 'border-collapse:collapse;margin:0'
_CELL_STYLE = 'border:1px solid #ccc;padding:2px 8px'


def _format_dict_value(values):
    return re.sub(r'</?b>', '', values.strip())


def _row(name, value):
    return (
        f'<tr><td style="{_CELL_STYLE}">{name}</td>'
        f'<td style="{_CELL_STYLE}">{value}</td></tr>'
    )


def _build_dict_table(values_by_name):
    """Render the dict-table with canonical rows first (defaulting to []),
    then any extra entries from the source preserved at the end.
    Newlines between rows make the field's HTML view easier to hand-edit;
    whitespace between <tr>s is ignored by the renderer."""
    rows = [_row(name, values_by_name.get(name, '[]')) for name in _DICT_NAMES]
    canonical = set(_DICT_NAMES)
    rows.extend(
        _row(name, value)
        for name, value in values_by_name.items()
        if name not in canonical
    )
    return (
        f'<table class="dict-table" style="{_TABLE_STYLE}">\n'
        '<tbody>\n'
        + '\n'.join(rows)
        + '\n</tbody></table>'
    )


def _context_to_dict_table(html):
    """Convert Context field dictionary list HTML to a table."""
    entries = _CONTEXT_DICT_RE.findall(html)
    if not entries:
        return None
    values_by_name = {name.strip(): _format_dict_value(values) for name, values in entries}
    return _build_dict_table(values_by_name)


def _migrate_note_core(note) -> bool:
    """Run the migration on a loaded note. Returns True if the note was modified.

    Issues warnings/tooltips for validation failures and no-op outcomes itself,
    so callers only need to handle UI refresh on a True return.
    """
    model = note.note_type()
    if model is None or model["name"] != NOTE_TYPE_NAME:
        showWarning(f"This note is not a {NOTE_TYPE_NAME} note.")
        return False

    field_names = [f["name"] for f in model["flds"]]
    for needed in ("Image", "Word", "Word Audio", "Sentence Audio", "Context", "Notes"):
        if needed not in field_names:
            showWarning(f"Note is missing {needed} field.")
            return False

    img_idx = field_names.index("Image")
    word_idx = field_names.index("Word")
    word_audio_idx = field_names.index("Word Audio")
    sent_audio_idx = field_names.index("Sentence Audio")
    context_idx = field_names.index("Context")
    notes_idx = field_names.index("Notes")

    image_content = note.fields[img_idx]
    new_syntax = None
    warnings = []
    moved_audio = []

    syntax_matches = _SYNTAX_COMMENT_RE.findall(image_content) if image_content.strip() else []
    if syntax_matches:
        word_before = note.fields[word_idx]

        # Each syntax comment becomes its own line in the new Word field
        # (one graph per line on the MvJ back; see commit 217cab6).
        converted_lines = []
        for raw in syntax_matches:
            converted, conv_warnings = _convert_comment_syntax(raw)
            warnings.extend(conv_warnings)
            # Preserve kanji form from the existing Word field when the
            # comment syntax was kana-only.
            converted, splice_warnings = _splice_word_kanji(converted, word_before)
            warnings.extend(splice_warnings)
            converted_lines.append(converted)
        new_syntax = '<br>'.join(converted_lines)
        new_syntax = _mark_front_visible(new_syntax, word_before)

        # Move sentence audio from Word Audio to Sentence Audio:
        # - filenames containing "reibun"
        # - filenames with no Japanese characters (kanji/kana)
        word_audio = note.fields[word_audio_idx]
        audio_files = _AUDIO_RE.findall(word_audio)
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

    if new_syntax is None and not dict_table:
        if not image_content.strip():
            tooltip("Image field is empty, nothing to migrate.")
        else:
            tooltip("No pitch syntax comment found in Image field.")
        return False

    # New notes (in the Add dialog) have no id yet and can't be flushed.
    if note.id:
        note.flush()

    parts = []
    if new_syntax is not None:
        parts.append(f"Migrated: {new_syntax}")
    if dict_table:
        parts.append("Dict table → Notes")
    if moved_audio:
        parts.append(f"Moved {len(moved_audio)} reibun audio to Sentence Audio")
    msg = " | ".join(parts)
    if warnings:
        msg += f" (warnings: {', '.join(warnings)})"
    tooltip(msg)
    return True


def _migrate_note(editor: Editor):
    if editor.note is None:
        showWarning("No note loaded.")
        return
    if _migrate_note_core(editor.note):
        editor.loadNoteKeepingFocus()


def _migrate_note_from_reviewer():
    if mw.reviewer is None or mw.reviewer.card is None:
        showWarning("No card.")
        return
    note = mw.reviewer.card.note()
    if _migrate_note_core(note):
        mw.reset()


_DICT_TABLE_HTML = _build_dict_table({})


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
    if note.id:
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


def _add_reviewer_menu(reviewer, menu):
    action = menu.addAction("\U0001F488 Migrate pitch syntax")
    action.triggered.connect(_migrate_note_from_reviewer)


gui_hooks.editor_did_init_buttons.append(_add_migrate_button)
gui_hooks.reviewer_will_show_context_menu.append(_add_reviewer_menu)
