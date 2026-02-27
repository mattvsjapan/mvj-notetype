"""Download and install/update the 🇯🇵 MvJ note type from GitHub."""

import os
import urllib.request
from urllib.error import HTTPError, URLError

from aqt import mw
from aqt.utils import showWarning, tooltip

NOTE_TYPE_NAME = "\U0001f1ef\U0001f1f5 MvJ"

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

_FIELDS = [
    "Word",
    "Word Audio",
    "Sentence",
    "Sentence Audio",
    "Definition",
    "Definition Audio",
    "am-study-morphs",
    "Image",
    "Translation",
    "Context",
]


def _download_file(url: str) -> bytes:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _download_all() -> dict:
    """Download templates and fonts. Returns dict with keys for each file."""
    results = {}
    all_files = [(f, _BASE_URL + f) for f in _TEMPLATE_FILES] + [
        (f, _BASE_URL + "fonts/" + f) for f in _FONT_FILES
    ]
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
    for field_name in _FIELDS:
        field = mm.new_field(field_name)
        mm.add_field(model, field)
    model["sortf"] = _FIELDS.index("Sentence")
    tmpl = mm.new_template(NOTE_TYPE_NAME)
    tmpl["qfmt"] = front
    tmpl["afmt"] = back
    mm.add_template(model, tmpl)
    model["css"] = css
    mm.add(model)


def _update_notetype(model: dict, front: str, back: str, css: str) -> None:
    model["tmpls"][0]["qfmt"] = front
    model["tmpls"][0]["afmt"] = back
    model["css"] = css
    mw.col.models.update_dict(model)


def install_notetype() -> None:
    """Main entry point — download files then create or update note type."""
    total_files = len(_TEMPLATE_FILES) + len(_FONT_FILES)
    mw.progress.start(max=total_files, label="Starting download...", parent=mw)

    def task():
        return _download_all()

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
                _update_notetype(existing, front, back, css)
                tooltip(f"Updated {NOTE_TYPE_NAME} note type.")
            else:
                _create_notetype(front, back, css)
                tooltip(f"Created {NOTE_TYPE_NAME} note type.")
        except Exception as e:
            showWarning(f"Failed to update note type: {e}")

    mw.taskman.run_in_background(task, on_done)
