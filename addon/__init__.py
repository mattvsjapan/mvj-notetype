"""MVJ Note Type Tools — Anki addon for the mvj note type."""

import re

from anki import hooks as anki_hooks
from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import QAction
from .notetype import NOTE_TYPE_NAME

_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


def _is_target_note(editor: Editor) -> bool:
    if editor.note is None:
        return False
    model = editor.note.note_type()
    return model is not None and model["name"] == NOTE_TYPE_NAME


# --- Patch Editor.fnameToLink via wrap() to produce [audio:] at insertion ---


def _fnameToLink_wrapper(self, fname, _old=None):
    result = _old(self, fname)
    if _is_target_note(self):
        result = _SOUND_RE.sub(r"[audio:\1]", result)
    return result


try:
    Editor.fnameToLink = wrap(Editor.fnameToLink, _fnameToLink_wrapper, "around")
except AttributeError:
    pass  # fnameToLink removed in newer Anki versions


# --- Safety net: also convert on field sync ---


def _munge_sound_to_audio(txt: str, editor: Editor) -> str:
    if not _is_target_note(editor):
        return txt
    return _SOUND_RE.sub(r"[audio:\1]", txt)


gui_hooks.editor_will_munge_html.append(_munge_sound_to_audio)


# --- Collection-level hook: convert [sound:] for AnkiConnect / Migaku / Yomichan ---


def _convert_on_add(col, note, deck_id):
    model = note.note_type()
    if model is None or model["name"] != NOTE_TYPE_NAME:
        return
    for i, value in enumerate(note.fields):
        if _SOUND_RE.search(value):
            note.fields[i] = _SOUND_RE.sub(r"[audio:\1]", value)


anki_hooks.note_will_be_added.append(_convert_on_add)


# --- Editor display hook: convert [sound:] when fields are loaded (e.g. Migaku intercept) ---

_converting_editor = False


def _convert_on_editor_load(editor: Editor):
    global _converting_editor
    if _converting_editor:
        return
    if not _is_target_note(editor):
        return
    note = editor.note
    changed = False
    for i, value in enumerate(note.fields):
        if _SOUND_RE.search(value):
            note.fields[i] = _SOUND_RE.sub(r"[audio:\1]", value)
            changed = True
    if changed:
        _converting_editor = True
        try:
            editor.loadNoteKeepingFocus()
        finally:
            _converting_editor = False


gui_hooks.editor_did_load_note.append(_convert_on_editor_load)


from .settings_dialog import SettingsDialog

from .notetype import install_notetype
from aqt.utils import showInfo


def _on_tools_action():
    if mw.col and mw.col.models.by_name(NOTE_TYPE_NAME):
        SettingsDialog(mw).exec()
    else:
        install_notetype(on_success=lambda: showInfo(
            f"{NOTE_TYPE_NAME} note type installed successfully."
        ))


_tools_action = QAction("", mw)
_tools_action.triggered.connect(_on_tools_action)
_tools_action.setShortcut("Alt+S")
mw.form.menuTools.addSeparator()
mw.form.menuTools.addAction(_tools_action)


def _update_tools_label():
    if mw.col is None:
        return
    installed = mw.col.models.by_name(NOTE_TYPE_NAME) is not None
    if installed:
        _tools_action.setText("\U0001f1ef\U0001f1f5 MvJ Note Type")
    else:
        _tools_action.setText("Install \U0001f1ef\U0001f1f5 MvJ Note Type")


mw.form.menuTools.aboutToShow.connect(_update_tools_label)

# Dev-only local template sync (file is .gitignored and excluded from packaging)
try:
    from . import dev_sync  # noqa: F401
except ImportError:
    pass
