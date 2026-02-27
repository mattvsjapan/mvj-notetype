"""Settings dialog for the MvJ note type — exposes CSS custom properties as radio buttons."""

import re

from aqt import mw
from aqt.qt import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
)
from aqt.utils import showWarning

from .notetype import NOTE_TYPE_NAME

# --- Settings schema ---
# Each entry: (css_var, [options], default)
# Grouped by section for the UI.

_SETTINGS = {
    "Layout": [
        ("--tategaki", ["on", "off"], "off"),
        ("--color-scheme", ["blue", "black", "red", "purple", "white"], "blue"),
        ("--debug", ["on", "off"], "off"),
        ("--audio-labels", ["on", "off"], "on"),
    ],
    "Word": [
        ("--word", ["front", "back", "off"], "front"),
        ("--word-audio", ["front", "back", "off"], "back"),
        ("--word-furigana", ["front", "back", "off"], "front"),
        ("--word-pitch-color", ["front", "back", "off"], "back"),
        ("--pitch-graph", ["on", "off"], "on"),
    ],
    "Sentence": [
        ("--sentence", ["front", "back", "off"], "front"),
        ("--sentence-audio", ["front", "back", "off"], "back"),
        ("--sentence-furigana", ["front", "back", "off"], "front"),
        ("--sentence-pitch-color", ["front", "back", "off"], "back"),
    ],
    "Image": [
        ("--image", ["front", "back", "off"], "back"),
    ],
    "Definitions": [
        ("--definition-text", ["on", "off"], "on"),
        ("--definition-audio", ["on", "off"], "on"),
        ("--definition-mode", ["all", "bilingual", "monolingual", "unlocked"], "all"),
        ("--definition-furigana", ["front", "back", "off"], "back"),
        ("--definition-pitch-color", ["front", "back", "off"], "back"),
    ],
}


def _var_to_label(var: str) -> str:
    """Convert a CSS variable name to a human-readable label.

    '--word-furigana' -> 'Word Furigana'
    """
    return var.lstrip("-").replace("-", " ").title()


def _parse_settings(css: str) -> dict[str, str]:
    """Extract current setting values from CSS text."""
    values = {}
    for entries in _SETTINGS.values():
        for var, _options, default in entries:
            # Match e.g.  --tategaki: off;  (with optional whitespace/comments)
            m = re.search(rf"{re.escape(var)}:\s*(\S+?)\s*;", css)
            values[var] = m.group(1) if m else default
    return values


def _apply_settings(css: str, settings: dict[str, str]) -> str:
    """Replace setting values in the CSS string in-place."""
    for var, value in settings.items():
        css = re.sub(
            rf"({re.escape(var)}:\s*)\S+(;)",
            rf"\g<1>{value}\2",
            css,
            count=1,
        )
    return css


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(f"{NOTE_TYPE_NAME} Settings")
        self.setMinimumWidth(420)

        self._model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not self._model:
            showWarning(
                f'Note type "{NOTE_TYPE_NAME}" not found.\n'
                "Please install it first via Tools menu."
            )
            self.reject()
            return

        css = self._model["css"]
        current = _parse_settings(css)

        outer = QVBoxLayout(self)
        self._groups: dict[str, QButtonGroup] = {}

        for section, entries in _SETTINGS.items():
            group_box = QGroupBox(section)
            form = QFormLayout()
            for var, options, default in entries:
                btn_group = QButtonGroup(self)
                row = QHBoxLayout()
                for opt in options:
                    rb = QRadioButton(opt)
                    if current.get(var, default) == opt:
                        rb.setChecked(True)
                    btn_group.addButton(rb)
                    row.addWidget(rb)
                row.addStretch()
                form.addRow(_var_to_label(var) + ":", row)
                self._groups[var] = btn_group
            group_box.setLayout(form)
            outer.addWidget(group_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _save(self):
        # Re-fetch in case something changed
        model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not model:
            showWarning(f'Note type "{NOTE_TYPE_NAME}" not found.')
            self.reject()
            return

        new_values = {}
        for var, btn_group in self._groups.items():
            checked = btn_group.checkedButton()
            if checked:
                new_values[var] = checked.text()

        model["css"] = _apply_settings(model["css"], new_values)
        mw.col.models.update_dict(model)
        self.accept()
