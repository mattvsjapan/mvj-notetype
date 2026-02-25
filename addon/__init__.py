"""MVJ Note Type Tools — Anki addon for the mvj note type."""

import re

from anki.hooks import wrap
from aqt import gui_hooks
from aqt.editor import Editor

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
