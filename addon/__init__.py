"""MVJ Note Type Tools — Anki addon for the mvj note type."""

import re

from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import QAction
from aqt.utils import showWarning, tooltip

NOTE_TYPE = "\U0001f1ef\U0001f1f5 Japanese"
_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


def _is_target_note(editor: Editor) -> bool:
    if editor.note is None:
        return False
    model = editor.note.note_type()
    return model is not None and model["name"] == NOTE_TYPE


# --- Patch Editor.fnameToLink via wrap() to produce [audio:] at insertion ---


def _fnameToLink_wrapper(self, fname, _old=None):
    result = _old(self, fname)
    if _is_target_note(self):
        result = _SOUND_RE.sub(r"[audio:\1]", result)
    return result


Editor.fnameToLink = wrap(Editor.fnameToLink, _fnameToLink_wrapper, "around")


# --- Safety net: also convert on field sync ---


def _munge_sound_to_audio(txt: str, editor: Editor) -> str:
    if not _is_target_note(editor):
        return txt
    return _SOUND_RE.sub(r"[audio:\1]", txt)


gui_hooks.editor_will_munge_html.append(_munge_sound_to_audio)


# --- Browser: bulk convert [sound:] to [audio:] ---


def _bulk_convert_sound_to_audio(browser):
    note_ids = mw.col.find_notes(f'"note:{NOTE_TYPE}"')
    if not note_ids:
        tooltip("No matching notes found.", parent=browser)
        return

    converted = 0

    def task():
        nonlocal converted
        modified = []
        total = len(note_ids)
        for i, nid in enumerate(note_ids):
            note = mw.col.get_note(nid)
            changed = False
            for j, field in enumerate(note.fields):
                new_field = _SOUND_RE.sub(r"[audio:\1]", field)
                if new_field != field:
                    note.fields[j] = new_field
                    changed = True
            if changed:
                modified.append(note)
            if i % 10 == 0:
                mw.taskman.run_on_main(
                    lambda v=i + 1: mw.progress.update(
                        label=f"Scanning note {v}/{total}...",
                        value=v,
                    )
                )
        converted = len(modified)
        if modified:
            pos = mw.col.add_custom_undo_entry(
                f"Convert [sound:] to [audio:] in {converted} notes"
            )
            mw.col.update_notes(modified)
            mw.col.merge_undo_entries(pos)

    def on_done(future):
        mw.progress.finish()
        try:
            future.result()
        except Exception as e:
            showWarning(str(e))
            return
        browser.model.reset()
        tooltip(f"Converted {converted} notes.", parent=browser)

    mw.progress.start(
        max=len(note_ids),
        label="Scanning notes...",
        parent=browser,
    )
    mw.taskman.run_in_background(task, on_done)


def _setup_browser_menu(browser):
    action = QAction("Convert [sound:] to [audio:]", browser)
    action.triggered.connect(lambda: _bulk_convert_sound_to_audio(browser))
    browser.form.menu_Notes.addSeparator()
    browser.form.menu_Notes.addAction(action)


gui_hooks.browser_menus_did_init.append(_setup_browser_menu)
