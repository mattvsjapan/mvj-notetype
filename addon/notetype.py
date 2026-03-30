"""Download and install/update the 🇯🇵 MvJ note type from GitHub."""

import os
import re
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


# Matches the entire SETTINGS + MODES region: from the ⚙ SETTINGS banner
# through the standalone ═══ closing banner.  The closing banner is the
# first line that is *only* /* ═══…═══ */ (single-line comment with no ⚙).
# old name → new name (applied during update)
_FIELD_RENAMES = {"Translation": "Notes"}

_SETTINGS_RE = re.compile(
    r"(/\*\s*═+\s*\n\s*⚙\s+SETTINGS\b.*?\n[ \t]*/\*\s*═+\s*\*/)",
    re.DOTALL,
)


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
    # Add any missing fields before updating templates that reference them
    existing_names = {f["name"] for f in model["flds"]}
    for field_name, description, font, font_size in _FIELDS:
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
    mw.progress.start(max=total_files, label="Starting download...", parent=mw)

    def task():
        return _download_all(skip_fonts=skip_fonts)

    def on_done(future):
        mw.progress.finish()
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
