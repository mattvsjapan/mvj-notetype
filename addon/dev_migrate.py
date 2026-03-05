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

# Comment syntax has pitch outside brackets: 堰[せき];1 -
# convert_word_field expects it inside: 堰[せき;1] -
_PITCH_OUTSIDE_RE = re.compile(r'\[([^\]]+)\];([^\s]+)')


def _reformat_syntax(text):
    """Move semicolon+pitch from outside brackets to inside."""
    return _PITCH_OUTSIDE_RE.sub(r'[\1;\2]', text)


def _log(note_id, word_before, image_before, word_after):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"=== {datetime.now().isoformat()} | nid:{note_id} ===\n")
        f.write(f"Word BEFORE:  {word_before}\n")
        f.write(f"Image BEFORE: {image_before}\n")
        f.write(f"Word AFTER:   {word_after}\n")
        f.write("\n")


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
    if "Image" not in field_names or "Word" not in field_names:
        showWarning("Note is missing Image or Word field.")
        return

    img_idx = field_names.index("Image")
    word_idx = field_names.index("Word")

    image_content = note.fields[img_idx]
    if not image_content.strip():
        tooltip("Image field is empty, nothing to migrate.")
        return

    m = _SYNTAX_COMMENT_RE.search(image_content)
    if not m:
        tooltip("No pitch syntax comment found in Image field.")
        return

    old_syntax = _reformat_syntax(m.group(1))
    new_syntax, warnings = convert_word_field(old_syntax)

    word_before = note.fields[word_idx]
    _log(note.id, word_before, image_content, new_syntax)

    note.fields[word_idx] = new_syntax
    note.fields[img_idx] = ""

    note.flush()
    editor.loadNoteKeepingFocus()

    msg = f"Migrated: {new_syntax}"
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
    )
    buttons.append(btn)


gui_hooks.editor_did_init_buttons.append(_add_migrate_button)
