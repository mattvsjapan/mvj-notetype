"""MVJ Note Type Tools — Anki addon for the mvj note type."""

import re

from anki import hooks as anki_hooks
from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import QAction, Qt
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


# --- Intercept Check Media to warn about [audio:] tag incompatibility ---


def _check_media_with_warning() -> None:
    """Show warning dialog before allowing Check Media to proceed."""
    from aqt.mediacheck import check_media_db
    from aqt.qt import QMessageBox

    from . import media_service as ms
    from .media_manager_dialog import MediaManagerDialog

    source_folder = ms.get_mvj_source_folder()
    has_mvj = source_folder is not None

    msg_box = QMessageBox(mw)
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle("Check Media Warning - MvJ Note Type")

    lines = [
        "\u26a0\ufe0f Warning\n",
        "Deleting unused media with Anki's native media checker may delete audio files "
        "that are actually in use.\n",
        "The MvJ note type uses [audio:] tags for all audio (word, sentence, and definition). "
        "Anki's native media checker only recognizes [sound:] tags, so it will flag all "
        "MvJ audio files as unused.\n",
    ]
    if has_mvj:
        lines.append(
            "Additionally, all media in the source media folder will appear as missing "
            "to Anki's native media checker.\n"
        )
    lines.append("Use the MvJ Media Manager to safely manage unused media.")

    msg_box.setText("\n".join(lines))

    media_mgr_btn = msg_box.addButton("Open MvJ Media Manager", QMessageBox.ButtonRole.ActionRole)
    proceed_btn = msg_box.addButton("Open native media checker", QMessageBox.ButtonRole.ActionRole)
    cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(media_mgr_btn)

    msg_box.exec()

    if msg_box.clickedButton() == proceed_btn:
        check_media_db(mw)
    elif msg_box.clickedButton() == media_mgr_btn:
        MediaManagerDialog.show_dialog(source_folder=source_folder, parent=mw)


def _intercept_check_media(_mw=None) -> None:
    """Find Check Media in Tools menu and replace its handler with our warning."""
    if not mw or not mw.form:
        return

    menu = mw.form.menuTools
    if not menu:
        return

    for action in menu.actions():
        action_text = action.text()
        if "Check Media" in action_text or ("Media" in action_text and "Check" in action_text):
            try:
                action.triggered.disconnect()
            except TypeError:
                pass
            action.triggered.connect(_check_media_with_warning)
            return


gui_hooks.main_window_did_init.append(_intercept_check_media)


# Dev-only local template sync (file is .gitignored and excluded from packaging)
try:
    from . import dev_sync  # noqa: F401
except ImportError:
    pass

# Dev-only migration tool (excluded from packaging)
try:
    from . import dev_migrate  # noqa: F401
except ImportError:
    pass
