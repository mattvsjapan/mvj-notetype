"""Settings dialog for the MvJ note type — exposes CSS custom properties as dropdowns."""

import copy
import json
import os
import re
import shutil
from dataclasses import dataclass, field

from aqt import mw
from aqt.qt import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager
from aqt.utils import showInfo, showWarning, tooltip
from aqt.webview import AnkiWebView, AnkiWebViewKind

from .notetype import NOTE_TYPE_NAME, install_notetype

_SAMPLE_IMAGE = "_mvj_sample.jpg"

# --- Sample card for the live preview ---
_SAMPLE_FIELDS = {
    "Word": "日本語[にほんご]:0-",
    "Word Audio": "[audio:_]",
    "Sentence": "日本語[にほんご]:0 って: 難[むずか]し\\い:h3 よね: 、 分[わ]かる:k",
    "Sentence Audio": "[audio:_]",
    "Definition": (
        '<!-- def-type="bilingual" -->'
        "A language that is spoken by the people of Japan as their primary means of communication."
        "<!-- def-end -->"
        '<!-- def-br-start --><br><br><!-- def-br-end -->'
        '<!-- def-type="monolingual" -->'
        "にほん‐ご [0]【日本語】<br>"
        "日本列島で話される言語。主語・目的語・述語の順に並び、動詞に助動詞や助詞が いくつも つく。音節の種類が少ない。"
        "<!-- def-end -->"
    ),
    "Definition Audio": (
        '<!-- def-type="bilingual" -->[audio:_]<!-- def-end -->'
        '<!-- def-type="monolingual" -->[audio:_]<!-- def-end -->'
    ),
    "Image": f'<img src="{_SAMPLE_IMAGE}">',
}

# --- Settings schema ---
# Each entry: (css_var, [options], default)
# Grouped by section for the UI.

_HOTKEYS = [
    ("--hotkey-word-audio", "n"),
    ("--hotkey-sentence-audio", "h"),
    ("--hotkey-definition-audio", ","),
    ("--hotkey-play-all", "z"),
    ("--hotkey-stop-all", "?"),
    ("--hotkey-jp-toggle", "."),
]

_SETTINGS = {
    "Layout": [
        ("--tategaki", ["on", "off"], "off"),
        ("--color-scheme", ["blue", "black", "red", "purple", "white"], "blue"),
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

# All settings the JS mode system can override (matches front.html settings array).
_OVERRIDABLE = [
    "tategaki", "color-scheme", "debug", "audio-labels",
    "word", "word-audio", "word-furigana", "word-pitch-color", "pitch-graph",
    "sentence", "sentence-audio", "sentence-furigana", "sentence-pitch-color",
    "image",
    "definition-text", "definition-audio", "definition-mode",
    "definition-furigana", "definition-pitch-color",
]

# Regex to find the modes *content* (between the MODES banner and the closing ═══ banner).
_MODES_CONTENT_RE = re.compile(
    r"(⚙\s+MODES\b.*?═+\s*\*/)"   # end of MODES banner  (group 1 — kept)
    r"(.*?)"                         # mode content          (group 2 — replaced)
    r"(\n[ \t]*/\*\s*═+\s*\*/)",    # closing ═══ banner    (group 3 — kept)
    re.DOTALL,
)

_OVERRIDE_ACTIVE_STYLE = "QComboBox { background-color: rgba(76, 175, 80, 0.10); }"


@dataclass
class Mode:
    name: str
    tag: str
    deck: str
    overrides: dict[str, str] = field(default_factory=dict)


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
    for var, default in _HOTKEYS:
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


def _parse_modes(css: str) -> list[Mode]:
    """Extract mode definitions from CSS custom properties."""
    modes: list[Mode] = []
    for i in range(1, 21):
        tag_m = re.search(rf"--mode-{i}-tag:\s*([^;]*);", css)
        deck_m = re.search(rf"--mode-{i}-deck:\s*([^;]*);", css)
        if not tag_m and not deck_m:
            break

        tag = tag_m.group(1).strip() if tag_m else ""
        deck = deck_m.group(1).strip() if deck_m else ""

        # Name: try --mode-N-name variable first, then comment header
        name = ""
        name_m = re.search(rf"--mode-{i}-name:\s*([^;]*);", css)
        if name_m and name_m.group(1).strip():
            name = name_m.group(1).strip()
        else:
            comment_m = re.search(rf"/\*\s*——\s*Mode\s+{i}:\s*(\S+)", css)
            if comment_m:
                name = comment_m.group(1).strip()

        overrides: dict[str, str] = {}
        for setting in _OVERRIDABLE:
            m = re.search(
                rf"--mode-{i}-{re.escape(setting)}:\s*(\S+?)\s*;", css
            )
            if m:
                overrides[f"--{setting}"] = m.group(1)

        modes.append(Mode(name=name, tag=tag, deck=deck, overrides=overrides))
    return modes


def _serialize_modes(modes: list[Mode]) -> str:
    """Generate CSS text for all modes."""
    _DASH = "\u2014"
    lines: list[str] = []
    for i, mode in enumerate(modes, 1):
        name_part = f": {mode.name} " if mode.name else " "
        dashes = max(1, 55 - len(f"Mode {i}{name_part}"))
        lines.append("")
        lines.append(
            f"    /* {_DASH}{_DASH} Mode {i}{name_part}"
            f"{_DASH * dashes} */"
        )
        if mode.name:
            lines.append(f"    --mode-{i}-name: {mode.name};")
        lines.append(f"    --mode-{i}-tag: {mode.tag};")
        lines.append(f"    --mode-{i}-deck: {mode.deck};")
        for var, value in mode.overrides.items():
            setting = var.lstrip("-")
            lines.append(f"    --mode-{i}-{setting}: {value};")
    lines.append("")
    return "\n".join(lines)


def _apply_modes(css: str, modes: list[Mode]) -> str:
    """Replace the modes region in the CSS with serialized mode data."""
    content = _serialize_modes(modes)

    def replacer(m: re.Match) -> str:
        return m.group(1) + content + m.group(3)

    return _MODES_CONTENT_RE.sub(replacer, css, count=1)


class SettingsDialog(QDialog):
    _preview_timer: QTimer | None = None
    _web: AnkiWebView | None = None

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(f"{NOTE_TYPE_NAME} Settings")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build (or rebuild) the dialog contents."""
        self._cleanup()

        # Tear down any existing layout
        old = self.layout()
        if old:
            QWidget().setLayout(old)

        self._model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not self._model:
            self.setMinimumSize(0, 0)
            self.resize(300, 100)
            layout = QVBoxLayout(self)
            layout.addWidget(
                QPushButton("Install Note Type", clicked=self._install_and_close)
            )
            return

        screen = QApplication.primaryScreen()
        available_h = screen.availableGeometry().height() if screen else 1200
        self.resize(1400, min(1200, available_h - 50))

        css = self._model["css"]
        self._defaults = _parse_settings(css)
        self._modes = _parse_modes(css)
        self._selected_index = -1  # -1 = Defaults

        # Widget refs (populated by detail panel builders)
        self._combos: dict[str, QComboBox] = {}
        self._hotkey_inputs: dict[str, QLineEdit] = {}
        self._mode_overrides: dict[str, tuple[QCheckBox, QComboBox]] = {}
        self._mode_name_input: QLineEdit | None = None
        self._mode_tag_input: QLineEdit | None = None
        self._mode_deck_input: QLineEdit | None = None

        outer = QVBoxLayout(self)

        # --- Splitter: settings on left, preview on right ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left panel ----
        left = QWidget()
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Mode list
        self._mode_list = QListWidget()
        self._mode_list.setFixedHeight(180)
        self._mode_list.currentRowChanged.connect(
            self._on_mode_list_selection_changed
        )
        left_layout.addWidget(self._mode_list)

        # Button row
        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("+")
        self._btn_del = QPushButton("\u2212")   # minus sign
        self._btn_up = QPushButton("\u25b2")    # ▲
        self._btn_down = QPushButton("\u25bc")  # ▼
        for btn in (self._btn_add, self._btn_del, self._btn_up, self._btn_down):
            btn.setFixedWidth(30)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        self._btn_add.clicked.connect(self._add_mode)
        self._btn_del.clicked.connect(self._delete_mode)
        self._btn_up.clicked.connect(self._move_mode_up)
        self._btn_down.clicked.connect(self._move_mode_down)
        left_layout.addLayout(btn_row)

        # Detail scroll area (content swapped on selection change)
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        left_layout.addWidget(self._detail_scroll, 1)

        splitter.addWidget(left)

        # ---- Right panel: preview (unchanged) ----
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # Front/Back toggle
        toggle_row = QHBoxLayout()
        self._btn_front = QPushButton("Front")
        self._btn_back = QPushButton("Back")
        self._btn_front.setCheckable(True)
        self._btn_back.setCheckable(True)
        self._btn_back.setChecked(True)  # default to showing back
        self._btn_front.clicked.connect(self._on_front_clicked)
        self._btn_back.clicked.connect(self._on_back_clicked)
        toggle_row.addWidget(self._btn_front)
        toggle_row.addWidget(self._btn_back)
        toggle_row.addStretch()
        preview_layout.addLayout(toggle_row)

        self._init_preview(preview_layout)

        splitter.addWidget(preview_container)
        splitter.setSizes([550, 650])

        outer.addWidget(splitter, 1)

        # --- Dialog buttons ---
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        update_btn = QPushButton("Update to Newest Version")
        update_btn.clicked.connect(self._install)
        btn_box.addButton(update_btn, QDialogButtonBox.ButtonRole.ActionRole)
        convert_btn = QPushButton("Convert [sound:] \u2192 [audio:]")
        convert_btn.clicked.connect(self._convert_sound_to_audio)
        btn_box.addButton(convert_btn, QDialogButtonBox.ButtonRole.ActionRole)
        outer.addWidget(btn_box)

        # --- Populate mode list & detail panel ---
        self._rebuild_mode_list()
        self._rebuild_detail_panel()
        self._update_button_states()

    # --- Mode list ---

    def _rebuild_mode_list(self) -> None:
        """Repopulate the mode list widget from self._modes."""
        self._mode_list.blockSignals(True)
        self._mode_list.clear()

        # Pinned "Defaults" row
        defaults_item = QListWidgetItem("\u2605 Defaults")
        font = defaults_item.font()
        font.setBold(True)
        defaults_item.setFont(font)
        defaults_item.setFlags(
            defaults_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
        )
        self._mode_list.addItem(defaults_item)

        for i, mode in enumerate(self._modes):
            if mode.name:
                text = f"{i + 1}. {mode.name}"
            elif mode.tag:
                text = f"{i + 1}. [{mode.tag}]"
            else:
                text = f"{i + 1}. (untitled)"
            self._mode_list.addItem(QListWidgetItem(text))

        # Restore selection
        self._mode_list.setCurrentRow(self._selected_index + 1)
        self._mode_list.blockSignals(False)

    def _update_button_states(self) -> None:
        is_default = self._selected_index == -1
        self._btn_del.setEnabled(not is_default)
        self._btn_up.setEnabled(self._selected_index > 0)
        self._btn_down.setEnabled(
            not is_default and self._selected_index < len(self._modes) - 1
        )

    def _on_mode_list_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        self._sync_current_to_data()
        self._selected_index = row - 1  # row 0 = Defaults → -1
        self._rebuild_detail_panel()
        self._update_button_states()
        self._on_setting_changed()

    # --- Detail panel builders ---

    def _rebuild_detail_panel(self) -> None:
        old = self._detail_scroll.takeWidget()
        if old:
            old.deleteLater()

        if self._selected_index == -1:
            widget = self._build_defaults_view()
        else:
            widget = self._build_mode_view(self._modes[self._selected_index])
        self._detail_scroll.setWidget(widget)

    def _build_defaults_view(self) -> QWidget:
        """Build the defaults editing panel (dropdowns + hotkeys)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._combos = {}

        for section, entries in _SETTINGS.items():
            group_box = QGroupBox(section)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            for var, options, default in entries:
                combo = QComboBox()
                combo.addItems(options)
                combo.setCurrentText(self._defaults.get(var, default))
                combo.currentTextChanged.connect(self._on_setting_changed)
                form.addRow(_var_to_label(var) + ":", combo)
                self._combos[var] = combo
            group_box.setLayout(form)
            layout.addWidget(group_box)

        # Hotkeys group box
        self._hotkey_inputs = {}
        hotkey_box = QGroupBox("Hotkeys")
        hotkey_form = QFormLayout()
        hotkey_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        hotkey_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        for var, default in _HOTKEYS:
            line_edit = QLineEdit()
            line_edit.setMaxLength(1)
            line_edit.setFixedWidth(30)
            line_edit.setText(self._defaults.get(var, default))
            line_edit.textChanged.connect(self._on_setting_changed)
            # Strip "Hotkey " prefix since they're in a "Hotkeys" group
            label = _var_to_label(var).removeprefix("Hotkey ")
            if var == "--hotkey-jp-toggle":
                label = "Hidden Definition Toggle"
            hotkey_form.addRow(label + ":", line_edit)
            self._hotkey_inputs[var] = line_edit
        hotkey_box.setLayout(hotkey_form)
        layout.addWidget(hotkey_box)

        layout.addStretch()
        return widget

    def _build_mode_view(self, mode: Mode) -> QWidget:
        """Build the mode editing panel (triggers + override checkboxes)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._mode_overrides = {}

        # --- Triggers ---
        triggers_box = QGroupBox("Mode Settings")
        triggers_form = QFormLayout()
        triggers_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        triggers_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self._mode_name_input = QLineEdit(mode.name)
        self._mode_name_input.setPlaceholderText("e.g. Sentence")
        self._mode_name_input.textChanged.connect(self._on_mode_name_changed)
        triggers_form.addRow("Name:", self._mode_name_input)

        self._mode_tag_input = QLineEdit(mode.tag)
        self._mode_tag_input.setPlaceholderText("e.g. _jp::sentence")
        self._mode_tag_input.textChanged.connect(self._on_setting_changed)
        triggers_form.addRow("Tag:", self._mode_tag_input)

        self._mode_deck_input = QLineEdit(mode.deck)
        self._mode_deck_input.setPlaceholderText("e.g. Mining::Vocab")
        self._mode_deck_input.textChanged.connect(self._on_setting_changed)
        triggers_form.addRow("Deck:", self._mode_deck_input)

        triggers_box.setLayout(triggers_form)
        layout.addWidget(triggers_box)

        # --- Override sections (same groups as defaults, minus Hotkeys) ---
        for section, entries in _SETTINGS.items():
            group_box = QGroupBox(section)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            for var, options, default in entries:
                row = QHBoxLayout()
                cb = QCheckBox()
                combo = QComboBox()
                combo.addItems(options)

                is_overridden = var in mode.overrides
                cb.setChecked(is_overridden)
                if is_overridden:
                    combo.setCurrentText(mode.overrides[var])
                    combo.setStyleSheet(_OVERRIDE_ACTIVE_STYLE)
                else:
                    combo.setCurrentText(self._defaults.get(var, default))
                    combo.setEnabled(False)

                cb.toggled.connect(
                    lambda checked, c=combo, v=var, d=default:
                        self._on_override_toggled(checked, c, v, d)
                )
                combo.currentTextChanged.connect(self._on_setting_changed)

                row.addWidget(cb)
                row.addWidget(combo, 1)
                form.addRow(_var_to_label(var) + ":", row)
                self._mode_overrides[var] = (cb, combo)
            group_box.setLayout(form)
            layout.addWidget(group_box)

        layout.addStretch()
        return widget

    def _on_override_toggled(
        self, checked: bool, combo: QComboBox, var: str, default: str,
    ) -> None:
        combo.setEnabled(checked)
        if checked:
            combo.setStyleSheet(_OVERRIDE_ACTIVE_STYLE)
        else:
            combo.setStyleSheet("")
            # Reset to inherited default
            combo.setCurrentText(self._defaults.get(var, default))
        self._on_setting_changed()

    def _on_mode_name_changed(self, text: str) -> None:
        if self._selected_index >= 0:
            self._modes[self._selected_index].name = text
            row = self._selected_index + 1
            item = self._mode_list.item(row)
            if item:
                idx = self._selected_index
                if text:
                    item.setText(f"{idx + 1}. {text}")
                elif self._modes[idx].tag:
                    item.setText(f"{idx + 1}. [{self._modes[idx].tag}]")
                else:
                    item.setText(f"{idx + 1}. (untitled)")
        self._on_setting_changed()

    # --- Sync widget state ↔ data model ---

    def _sync_current_to_data(self) -> None:
        """Write current widget values back to the data model."""
        if self._selected_index == -1:
            if not self._combos:
                return
            for var, combo in self._combos.items():
                self._defaults[var] = combo.currentText()
            for var, line_edit in self._hotkey_inputs.items():
                text = line_edit.text()
                if text:
                    self._defaults[var] = text
        else:
            if not self._mode_overrides:
                return
            mode = self._modes[self._selected_index]
            if self._mode_name_input:
                mode.name = self._mode_name_input.text()
            if self._mode_tag_input:
                mode.tag = self._mode_tag_input.text()
            if self._mode_deck_input:
                mode.deck = self._mode_deck_input.text()

            # Preserve overrides not shown in the UI (e.g. --debug)
            ui_vars = set(self._mode_overrides.keys())
            new_overrides = {
                k: v for k, v in mode.overrides.items() if k not in ui_vars
            }
            for var, (cb, combo) in self._mode_overrides.items():
                if cb.isChecked():
                    new_overrides[var] = combo.currentText()
            mode.overrides = new_overrides

    # --- Mode list operations ---

    def _refresh_after_list_change(self) -> None:
        self._rebuild_mode_list()
        self._rebuild_detail_panel()
        self._update_button_states()
        self._on_setting_changed()

    def _add_mode(self) -> None:
        if len(self._modes) >= 20:
            return
        self._sync_current_to_data()
        self._modes.append(Mode(name="", tag="", deck="", overrides={}))
        self._selected_index = len(self._modes) - 1
        self._refresh_after_list_change()

    def _delete_mode(self) -> None:
        if self._selected_index < 0:
            return
        self._modes.pop(self._selected_index)
        self._selected_index = -1
        self._refresh_after_list_change()

    def _move_mode_up(self) -> None:
        idx = self._selected_index
        if idx <= 0:
            return
        self._sync_current_to_data()
        self._modes[idx - 1], self._modes[idx] = (
            self._modes[idx], self._modes[idx - 1]
        )
        self._selected_index = idx - 1
        self._refresh_after_list_change()

    def _move_mode_down(self) -> None:
        idx = self._selected_index
        if idx < 0 or idx >= len(self._modes) - 1:
            return
        self._sync_current_to_data()
        self._modes[idx], self._modes[idx + 1] = (
            self._modes[idx + 1], self._modes[idx]
        )
        self._selected_index = idx + 1
        self._refresh_after_list_change()

    # --- Preview ---

    def _init_preview(self, layout: QVBoxLayout) -> None:
        """Set up the preview webview with a synthetic sample card."""
        # Ensure sample image is in media folder
        src = os.path.join(os.path.dirname(__file__), _SAMPLE_IMAGE)
        dst = os.path.join(mw.col.media.dir(), _SAMPLE_IMAGE)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

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

    def _get_effective_settings(self) -> dict[str, str]:
        """Get settings for preview: defaults overlaid with selected mode overrides."""
        self._sync_current_to_data()
        settings = dict(self._defaults)
        if self._selected_index >= 0:
            mode = self._modes[self._selected_index]
            settings.update(mode.overrides)
        return settings

    def _render_preview(self) -> None:
        """Render the preview card with current settings applied."""
        if not self._web:
            return

        self._cancel_preview_timer()

        settings = self._get_effective_settings()
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
        """Debounce preview updates when a setting changes."""
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

    # --- Install / Convert / Save / Cancel ---

    def _install_and_close(self):
        self.accept()
        install_notetype(on_success=lambda: showInfo(
            f"{NOTE_TYPE_NAME} note type installed successfully."
        ))

    def _install(self):
        install_notetype(on_success=self._build_ui)

    def _convert_sound_to_audio(self):
        sound_re = re.compile(r"\[sound:([^\]]+)\]")
        note_ids = mw.col.find_notes(f'"note:{NOTE_TYPE_NAME}"')
        if not note_ids:
            tooltip("No matching notes found.", parent=self)
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
                    new_field = sound_re.sub(r"[audio:\1]", field)
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
            tooltip(f"Converted {converted} notes.", parent=self)

        mw.progress.start(
            max=len(note_ids),
            label="Scanning notes...",
            parent=self,
        )
        mw.taskman.run_in_background(task, on_done)

    def _save(self):
        # Re-fetch in case something changed
        model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not model:
            showWarning(f'Note type "{NOTE_TYPE_NAME}" not found.')
            self.reject()
            return

        self._sync_current_to_data()
        model["css"] = _apply_settings(model["css"], self._defaults)
        model["css"] = _apply_modes(model["css"], self._modes)
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
