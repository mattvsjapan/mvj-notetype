"""Dev-only: sync local template files into the Anki note type.

This file is .gitignored and excluded from packaging.
It adds a 'Sync Local Templates' menu item under Tools.
"""

import os

from aqt import gui_hooks, mw
from aqt.qt import QKeySequence, QShortcut
from aqt.utils import showWarning, tooltip

from .notetype import NOTE_TYPE_NAME, _update_notetype, _merge_css_settings

# ── Switch which note type to sync ──
# Set to "mvj" or "chinese"
_ACTIVE = "chinese"

_CONFIGS = {
    "mvj": {
        "dir": "/Volumes/OWC Envoy Pro FX/Documents/dev/pitch-graphs/note-types/mvj",
        "note_type": NOTE_TYPE_NAME,  # 🇯🇵 MvJ
    },
    "chinese": {
        "dir": "/Volumes/OWC Envoy Pro FX/Documents/dev/pitch-graphs/note-types/chinese",
        "note_type": "🇹🇼 Chinese",
    },
}

_LOCAL_DIR = _CONFIGS[_ACTIVE]["dir"]
_SYNC_NOTE_TYPE = _CONFIGS[_ACTIVE]["note_type"]
_TEMPLATE_FILES = {"front": "front.html", "back": "back.html", "css": "css.css"}


def sync_local_templates(*, reset_css: bool = False, config: str = _ACTIVE):
    """Read local front/back/css and push them into the note type."""
    if not mw.col:
        showWarning("No collection open.")
        return

    cfg = _CONFIGS[config]
    local_dir = cfg["dir"]
    note_type = cfg["note_type"]

    model = mw.col.models.by_name(note_type)
    if not model:
        showWarning(f"Note type '{note_type}' not found.")
        return

    # Read local files
    contents = {}
    for key, filename in _TEMPLATE_FILES.items():
        path = os.path.join(local_dir, filename)
        if not os.path.exists(path):
            showWarning(f"Missing: {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            contents[key] = f.read()

    _update_notetype(model, contents["front"], contents["back"], contents["css"], reset_css=reset_css)
    tooltip(f"Local templates synced ({config}).")


# Add button to main toolbar
def _on_top_toolbar_did_init_links(links, toolbar):
    link = toolbar.create_link(
        cmd="sync-local-templates",
        label="Update",
        func=sync_local_templates,
    )
    links.insert(5, link)

gui_hooks.top_toolbar_did_init_links.append(_on_top_toolbar_did_init_links)

QShortcut(QKeySequence("Alt+Y"), mw).activated.connect(sync_local_templates)
