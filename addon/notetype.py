"""Download and install/update the 🇯🇵 MvJ note type from GitHub."""

import os
import re
import sys
import urllib.request
from urllib.error import HTTPError, URLError

from aqt import mw
from aqt.utils import showWarning

NOTE_TYPE_NAME = "\U0001f1ef\U0001f1f5 MvJ"
_OLD_NOTE_TYPE_NAMES = ["\U0001f1ef\U0001f1f5 MvJ Listening", "MvJ Listening"]

_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "mattvsjapan/mvj-notetype/main/note-types/mvj/"
)
_TEMPLATE_FILES = ["front.html", "back.html", "css.css"]
_FONT_FILES = [
    "_pitch_num.woff2",
    "_inter.woff2",
    "_jetbrains-mono.woff2",
    "_noto-serif-jp.woff2",
    "_yukyokasho-bold.woff2",
]

_JP_FONT = "YuMincho"
#                (name, description, font, font_size)
_FIELDS = [
    ("Sentence", "Example sentence", _JP_FONT, None),
    ("Sentence Audio", "Example sentence audio", None, 12),
    ("Word", "Target word", _JP_FONT, 20),
    ("Word Audio", "Target word audio", None, 12),
    ("Definition", "Definition of target word", None, None),
    ("Definition Audio", "TTS audio of the definition", None, 12),
    ("am-study-morphs", "Unknown words (for AnkiMorphs & MvJ Japanese)", None, None),
    ("Image", "Image", None, 12),
    ("Notes", "English translation & LLM explanation", None, None),
    ("Context", "For LLMs to better understand the sentence", None, None),
]

# Created on initial install, but never re-created on update: if the user has
# deleted it from an existing note type, leave it gone.
_CREATE_ONLY_FIELDS = {"Context"}


# Matches the entire SETTINGS + MODES region: from the ⚙ SETTINGS banner
# through the standalone ═══ closing banner.  The closing banner is the
# first line that is *only* /* ═══…═══ */ (single-line comment with no ⚙).
# old name → new name (applied during update)
_FIELD_RENAMES = {"Translation": "Notes"}

_SETTINGS_RE = re.compile(
    r"(/\*\s*═+\s*\n\s*⚙\s+SETTINGS\b.*?\n[ \t]*/\*\s*═+\s*\*/)",
    re.DOTALL,
)

# MvJ Japanese add-on integration: when it has no note type selected,
# auto-select 🇯🇵 MvJ and map its logical fields onto our field names.
# Folder/package name of the MvJ Japanese add-on (matches media_service usage).
_MVJ_JAPANESE_MODULE = "MvJ Japanese"
_MVJ_JP_FIELD_MAP = {
    "word": "Word",
    "fallback_word": "am-study-morphs",
    "sentence": "Sentence",
    "sentence_audio": "Sentence Audio",
    "word_audio": "Word Audio",
    "definition": "Definition",
    "definition_audio": "Definition Audio",
    "translation": "Notes",
    "image": "Image",
    # monolingual_definition: no corresponding field — left untouched
}

# Single-shot guard so a "manager not ready yet" retry never loops.
_mvj_retry_scheduled = False


def _merge_css_settings(old_css: str, new_css: str) -> str:
    """Preserve the user's SETTINGS/MODES region when updating CSS."""
    old_match = _SETTINGS_RE.search(old_css)
    new_match = _SETTINGS_RE.search(new_css)
    if old_match and new_match:
        return new_css[: new_match.start()] + old_match.group(1) + new_css[new_match.end() :]
    return new_css


def _download_file(url: str) -> bytes:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _download_all(skip_fonts: bool = False) -> dict:
    """Download templates and fonts. Returns dict with keys for each file."""
    results = {}
    all_files = [(f, _BASE_URL + f) for f in _TEMPLATE_FILES]
    if not skip_fonts:
        all_files += [(f, _BASE_URL + "fonts/" + f) for f in _FONT_FILES]
    total = len(all_files)
    for i, (name, url) in enumerate(all_files):
        mw.taskman.run_on_main(
            lambda v=i + 1, n=name: mw.progress.update(
                label=f"Downloading {n} ({v}/{total})...",
                value=v,
            )
        )
        results[name] = _download_file(url)
    return results


def _install_fonts(files: dict) -> None:
    media_dir = mw.col.media.dir()
    for name in _FONT_FILES:
        path = os.path.join(media_dir, name)
        with open(path, "wb") as f:
            f.write(files[name])


def _create_notetype(front: str, back: str, css: str) -> None:
    mm = mw.col.models
    model = mm.new(NOTE_TYPE_NAME)
    for field_name, description, font, font_size in _FIELDS:
        field = mm.new_field(field_name)
        field["description"] = description
        if font:
            field["font"] = font
        if font_size:
            field["size"] = font_size
        mm.add_field(model, field)
    model["sortf"] = [name for name, *_ in _FIELDS].index("Sentence")
    tmpl = mm.new_template(NOTE_TYPE_NAME)
    tmpl["qfmt"] = front
    tmpl["afmt"] = back
    mm.add_template(model, tmpl)
    model["css"] = css
    mm.add(model)


def _update_notetype(
    model: dict, front: str, back: str, css: str, *, reset_css: bool = False,
) -> None:
    mm = mw.col.models
    # Rename fields first (e.g. Translation → Notes)
    existing_names = {f["name"] for f in model["flds"]}
    for fld in model["flds"]:
        new_name = _FIELD_RENAMES.get(fld["name"])
        if new_name and new_name not in existing_names:
            mm.rename_field(model, fld, new_name)
    # Add any missing fields before updating templates that reference them.
    # Create-only fields (e.g. Context) are never re-added on update: if the
    # user removed one from an existing note type, respect that.
    existing_names = {f["name"] for f in model["flds"]}
    for field_name, description, font, font_size in _FIELDS:
        if field_name in _CREATE_ONLY_FIELDS:
            continue
        if field_name not in existing_names:
            field = mm.new_field(field_name)
            field["description"] = description
            if font:
                field["font"] = font
            if font_size:
                field["size"] = font_size
            mm.add_field(model, field)
    # Now safe to update templates — all referenced fields exist
    model["tmpls"][0]["qfmt"] = front
    model["tmpls"][0]["afmt"] = back
    model["css"] = css if reset_css else _merge_css_settings(model["css"], css)
    # Update field metadata for existing fields
    field_map = {name: (desc, font, size) for name, desc, font, size in _FIELDS}
    for fld in model["flds"]:
        if fld["name"] in field_map:
            desc, font, size = field_map[fld["name"]]
            fld["description"] = desc
            if font:
                fld["font"] = font
            if size:
                fld["size"] = size
    mm.update_dict(model)


def _fonts_exist() -> bool:
    """Check whether all font files are already in the media folder."""
    media_dir = mw.col.media.dir()
    return all(os.path.exists(os.path.join(media_dir, f)) for f in _FONT_FILES)


def _get_mvj_japanese_manager():
    """Return MvJ Japanese's live MvjConfigManager, or None if unavailable.

    Uses the already-imported module from ``sys.modules`` (the add-on bootstrap
    imports ``<pkg>.mvj.actions``) rather than re-importing, so we never trigger
    a fresh load with side effects.
    """
    actions = sys.modules.get(f"{_MVJ_JAPANESE_MODULE}.mvj.actions")
    if actions is None:
        return None
    try:
        return actions.get_config_manager()
    except Exception:
        return None


def _mvj_settings_dialog_open() -> bool:
    """True if a visible MvJ Japanese settings dialog is currently open.

    We skip auto-config while it is open: clicking OK rebuilds the field config
    from the (stale) UI and would overwrite a selection we wrote underneath it.
    """
    try:
        from aqt.qt import QApplication

        settings_mod = sys.modules.get(f"{_MVJ_JAPANESE_MODULE}.mvj.settings")
        dialog_cls = getattr(settings_mod, "SettingsDialog", None) if settings_mod else None
        if dialog_cls is None:
            return False
        return any(
            isinstance(w, dialog_cls) and w.isVisible()
            for w in QApplication.topLevelWidgets()
        )
    except Exception:
        return False


def _mvj_field_assignments(selected_notetype_id, model_id, profile):
    """Pure: attr→value map to apply, or None if a selection already exists.

    Only acts when no note type is selected; any existing selection (our note
    type or another, however its fields are mapped) is left untouched.
    """
    if selected_notetype_id is not None:
        return None
    assignments = {
        "selected_notetype_id": model_id,
        "selected_notetype_profile": profile,
    }
    assignments.update(_MVJ_JP_FIELD_MAP)
    return assignments


def _configure_mvj_japanese(start_profile=None) -> None:
    """Point the MvJ Japanese add-on at 🇯🇵 MvJ if nothing is selected.

    Mutates MvJ Japanese's *live* config manager and calls its ``save()`` so
    the in-memory object, meta.json, the per-profile settings file, and Anki's
    config cache all stay consistent. No-op when MvJ Japanese is not installed,
    already has a note type selected, or is mid edit in its settings dialog.

    Always prepares ``japanese_fields`` (the Chinese block is never touched). In
    Japanese mode that block is also the active import mirror; in Chinese mode
    it only takes effect once the user switches back to Japanese.
    """
    global _mvj_retry_scheduled
    if not mw or not mw.col or not mw.pm:
        return
    # Profile may have switched during the background download (note type ids
    # are per-collection), so bail if we are no longer in the initiating profile.
    if start_profile is not None and mw.pm.name != start_profile:
        return

    manager = _get_mvj_japanese_manager()
    if manager is None:
        if not _mvj_retry_scheduled:
            # MvJ Japanese may not have finished init yet — retry once, later.
            _mvj_retry_scheduled = True
            try:
                from aqt.qt import QTimer

                QTimer.singleShot(3000, lambda: _configure_mvj_japanese(start_profile))
            except Exception:
                pass
        return

    if _mvj_settings_dialog_open():
        return  # don't race a dialog the user is actively editing

    try:
        data = manager.data
        jp = data.japanese_fields
    except Exception:
        return

    model = mw.col.models.by_name(NOTE_TYPE_NAME)
    if not model:
        return

    assignments = _mvj_field_assignments(
        getattr(jp, "selected_notetype_id", None),
        model["id"],
        mw.pm.name,
    )
    if not assignments:
        return  # already selected — leave it entirely alone

    snapshot = {attr: getattr(jp, attr, None) for attr in assignments}
    for attr, value in assignments.items():
        setattr(jp, attr, value)

    try:
        manager.save()
    except Exception as e:
        # Restore the in-memory object so MvJ doesn't show an unpersisted
        # selection, then resync from disk for good measure.
        for attr, value in snapshot.items():
            setattr(jp, attr, value)
        try:
            manager.reload()
        except Exception:
            pass
        print(f"[MvJ] Failed to save MvJ Japanese config: {e}")
        return

    if getattr(data, "target_language", "japanese") == "japanese":
        print(f"[MvJ] Selected {NOTE_TYPE_NAME} as MvJ Japanese note type")
    else:
        print(
            f"[MvJ] Prepared Japanese field mapping for {NOTE_TYPE_NAME} "
            "(MvJ Japanese is in Chinese mode; takes effect on switch)"
        )


def install_notetype(on_success=None, *, reset_css: bool = False) -> None:
    """Main entry point — download files then create or update note type.

    Args:
        on_success: Optional callback invoked (on the main thread) after a
            successful install or update.
        reset_css: If True, overwrite all CSS instead of preserving the
            user's SETTINGS region.
    """
    skip_fonts = _fonts_exist()
    total_files = len(_TEMPLATE_FILES) + (0 if skip_fonts else len(_FONT_FILES))
    # Remember which profile started this; the download is async and the user
    # could switch profiles before it finishes. Note type ids are per-collection.
    start_profile = mw.pm.name if mw.pm else None
    mw.progress.start(max=total_files, label="Starting download...", parent=mw)

    def task():
        return _download_all(skip_fonts=skip_fonts)

    def on_done(future):
        mw.progress.finish()
        if not mw.col or (mw.pm and mw.pm.name != start_profile):
            # Profile switched (or closed) mid-download — abort to avoid
            # writing the note type / config into the wrong collection.
            return
        try:
            files = future.result()
        except HTTPError as e:
            showWarning(f"Download failed: HTTP {e.code} for {e.url}")
            return
        except URLError as e:
            showWarning(f"Connection failed: {e.reason}")
            return
        except Exception as e:
            showWarning(f"Download failed: {e}")
            return

        if not skip_fonts:
            try:
                _install_fonts(files)
            except Exception as e:
                showWarning(f"Failed to install fonts: {e}")
                return

        front = files["front.html"].decode("utf-8")
        back = files["back.html"].decode("utf-8")
        css = files["css.css"].decode("utf-8")

        try:
            existing = mw.col.models.by_name(NOTE_TYPE_NAME)
            if existing:
                _update_notetype(existing, front, back, css, reset_css=reset_css)
            else:
                _create_notetype(front, back, css)
        except Exception as e:
            showWarning(f"Failed to update note type: {e}")
            return

        _remove_cardgen_guard()

        try:
            _configure_mvj_japanese(start_profile)
        except Exception as e:
            # Never let MvJ Japanese integration break note type install
            print(f"[MvJ] MvJ Japanese auto-config failed: {e}")

        if on_success:
            on_success()

    mw.taskman.run_in_background(task, on_done)


# ---------------------------------------------------------------------------
# Remove legacy cross-note-type autoplay guard
# ---------------------------------------------------------------------------

_CARDGEN_SNIPPET = '<script>window.__cardGen=(window.__cardGen||0)+1;</script>'


def _remove_cardgen_guard():
    """Remove the legacy cardGen snippet from non-MvJ front templates."""
    mm = mw.col.models
    for model in mm.all():
        if model["name"] == NOTE_TYPE_NAME:
            continue
        changed = False
        for tmpl in model["tmpls"]:
            if _CARDGEN_SNIPPET in tmpl["qfmt"]:
                tmpl["qfmt"] = tmpl["qfmt"].replace("\n" + _CARDGEN_SNIPPET, "")
                tmpl["qfmt"] = tmpl["qfmt"].replace(_CARDGEN_SNIPPET, "")
                changed = True
        if changed:
            mm.update_dict(model)


# ---------------------------------------------------------------------------
# Migration from old "🇯🇵 MvJ Listening" / "MvJ Listening" note types
# ---------------------------------------------------------------------------


def _find_old_notetype():
    """Return the first old note type model dict found, or None."""
    for name in _OLD_NOTE_TYPE_NAMES:
        model = mw.col.models.by_name(name)
        if model:
            return model
    return None


def change_notes_to_mvj(on_success=None, on_error=None):
    """Move all notes from old note type into 🇯🇵 MvJ, then delete old type.

    Args:
        on_success: Callback(old_name, count) on main thread after success.
        on_error: Callback(error_msg) on main thread on failure.
    """
    old_model = _find_old_notetype()
    new_model = mw.col.models.by_name(NOTE_TYPE_NAME)
    if not old_model or not new_model:
        if on_error:
            on_error("Old or new note type not found.")
        return

    old_name = old_model["name"]
    note_ids = mw.col.find_notes(f'"note:{old_name}"')
    if not note_ids:
        # No notes — just delete the empty old type
        mw.col.models.remove(old_model["id"])
        if on_success:
            on_success(old_name, 0)
        return

    # Get auto-matched field mapping (matches by name)
    info = mw.col.models.change_notetype_info(
        old_notetype_id=old_model["id"],
        new_notetype_id=new_model["id"],
    )
    req = info.input
    req.note_ids.extend(note_ids)

    # Execute the change
    mw.col.models.change_notetype_of_notes(req)

    # Delete the now-empty old note type
    mw.col.models.remove(old_model["id"])

    if on_success:
        on_success(old_name, len(note_ids))
