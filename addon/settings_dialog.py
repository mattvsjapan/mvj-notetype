"""Settings dialog for the MvJ note type — exposes CSS custom properties as radio buttons."""

import copy
import json
import re

from aqt import mw
from aqt.qt import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager
from aqt.utils import showWarning
from aqt.webview import AnkiWebView, AnkiWebViewKind

from .notetype import NOTE_TYPE_NAME

# --- Sample card for the live preview ---
_SAMPLE_FIELDS = {
    "Word": "日本語[にほんご]:0-",
    "Word Audio": "[audio:_]",
    "Sentence": "日本語[にほんご]:0 って: 難[むずか]し\\い:h3 よね: 、 分[わ]かる:k",
    "Sentence Audio": "[audio:_]",
    "Definition": (
        '<!-- def-type="bilingual" -->'
        "(the) Japanese language"
        "<!-- def-end -->"
        '<!-- def-type="monolingual" -->'
        "日本[にほん]:0 の 国語[こくご]:0 。"
        "<!-- def-end -->"
    ),
    "Definition Audio": "[audio:_]",
}

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
    _preview_timer: QTimer | None = None
    _web: AnkiWebView | None = None

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(f"{NOTE_TYPE_NAME} Settings")
        self.setMinimumSize(900, 600)

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

        # --- Splitter: settings on left, preview on right ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: scrollable settings panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(320)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

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
                btn_group.buttonClicked.connect(self._on_setting_changed)
            group_box.setLayout(form)
            settings_layout.addWidget(group_box)

        settings_layout.addStretch()
        scroll.setWidget(settings_widget)
        splitter.addWidget(scroll)

        # Right: preview panel
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # Front/Back toggle
        toggle_row = QHBoxLayout()
        self._btn_front = QPushButton("Front")
        self._btn_back = QPushButton("Back")
        self._btn_front.setCheckable(True)
        self._btn_back.setCheckable(True)
        self._btn_front.setChecked(True)  # default to showing front
        self._btn_front.clicked.connect(self._on_front_clicked)
        self._btn_back.clicked.connect(self._on_back_clicked)
        toggle_row.addWidget(self._btn_front)
        toggle_row.addWidget(self._btn_back)
        toggle_row.addStretch()
        preview_layout.addLayout(toggle_row)

        self._init_preview(preview_layout)

        splitter.addWidget(preview_container)
        splitter.setSizes([400, 500])

        outer.addWidget(splitter, 1)

        # --- Dialog buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # --- Preview ---

    def _init_preview(self, layout: QVBoxLayout) -> None:
        """Set up the preview webview with a synthetic sample card."""
        self._note = mw.col.new_note(self._model)
        for name, value in _SAMPLE_FIELDS.items():
            if name in self._note:
                self._note[name] = value

        self._web = AnkiWebView(kind=AnkiWebViewKind.CARD_LAYOUT)
        self._web.stdHtml(
            mw.reviewer.revHtml(),
            css=["css/reviewer.css"],
            js=[
                "js/mathjax.js",
                "js/vendor/mathjax/tex-chtml-full.js",
                "js/reviewer.js",
            ],
            context=self,
        )
        self._web.set_bridge_command(self._on_bridge_cmd, self)
        self._web.setPlaybackRequiresGesture(True)

        layout.addWidget(self._web, 1)

        # First render after webview page finishes loading
        QTimer.singleShot(200, self._render_preview)

    def _get_current_settings(self) -> dict[str, str]:
        """Read all radio button values into a dict."""
        values = {}
        for var, btn_group in self._groups.items():
            checked = btn_group.checkedButton()
            if checked:
                values[var] = checked.text()
        return values

    def _render_preview(self) -> None:
        """Render the preview card with current settings applied."""
        if not self._web:
            return

        self._cancel_preview_timer()

        settings = self._get_current_settings()
        model_copy = copy.deepcopy(self._model)
        model_copy["css"] = _apply_settings(model_copy["css"], settings)

        card = self._note.ephemeral_card(
            0, custom_note_type=model_copy
        )

        show_front = self._btn_front.isChecked()
        if show_front:
            html = card.question()
        else:
            html = card.answer()

        text = mw.prepare_card_text_for_display(html)
        bodyclass = theme_manager.body_classes_for_card_ord(card.ord)
        self._web.eval(f"_showAnswer({json.dumps(text)},'{bodyclass}');")

    def _on_setting_changed(self) -> None:
        """Debounce preview updates when a radio button changes."""
        self._cancel_preview_timer()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._render_preview)
        self._preview_timer.start()

    def _on_front_clicked(self) -> None:
        self._btn_front.setChecked(True)
        self._btn_back.setChecked(False)
        self._render_preview()

    def _on_back_clicked(self) -> None:
        self._btn_back.setChecked(True)
        self._btn_front.setChecked(False)
        self._render_preview()

    def _on_bridge_cmd(self, cmd: str) -> bool:
        return False

    def _cancel_preview_timer(self) -> None:
        if self._preview_timer:
            self._preview_timer.stop()
            self._preview_timer = None

    # --- Save / Cancel ---

    def _save(self):
        # Re-fetch in case something changed
        model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not model:
            showWarning(f'Note type "{NOTE_TYPE_NAME}" not found.')
            self.reject()
            return

        new_values = self._get_current_settings()
        model["css"] = _apply_settings(model["css"], new_values)
        mw.col.models.update_dict(model)

        self._cleanup()
        self.accept()

    def reject(self) -> None:
        self._cleanup()
        super().reject()

    def _cleanup(self) -> None:
        self._cancel_preview_timer()
        if self._web:
            self._web.cleanup()
            self._web = None
