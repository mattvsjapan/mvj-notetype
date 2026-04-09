"""Install or migrate the Kaishi 1.5k deck for the MvJ note type."""

import csv
import io
import os
import re
import tempfile
import urllib.request
import zipfile
from urllib.error import HTTPError, URLError

from aqt import mw
from aqt.qt import QMessageBox
from aqt.utils import showInfo, showWarning

from .notetype import NOTE_TYPE_NAME, _OLD_NOTE_TYPE_NAMES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CARDS_TSV_URL = (
    "https://raw.githubusercontent.com/"
    "mattvsjapan/mvj-notetype/main/kaishi/cards.tsv"
)
_RELEASE_BASE = (
    "https://github.com/mattvsjapan/mvj-notetype/"
    "releases/download/kaishi-media-v1/"
)
_FULL_MEDIA_ZIP_URL = _RELEASE_BASE + "kaishi-media-full-v1.zip"
_DEF_AUDIO_ZIP_URL = _RELEASE_BASE + "kaishi-def-audio-v1.zip"

_DECK_NAME = "MvJ Kaishi 1.5k"
_EXISTING_DECK_NAMES = ["Kaishi 1.5k", "MvJ Kaishi 1.5k"]
_KAISHI_NOTE_TYPE = "Kaishi 1.5k"

# TSV columns that map 1:1 to MvJ note type fields (columns 2–9)
_TSV_FIELDS = [
    "Word", "Sentence", "Word Audio", "Sentence Audio",
    "Definition", "Definition Audio", "Image", "Notes",
]

_SOUND_RE = re.compile(r"\[sound:")
_FURIGANA_RE = re.compile(r"\[[^\]]*\]")
# Strip all HTML tags except <b>, </b>, and <b ...attributes>
_NON_BOLD_HTML_RE = re.compile(r"<(?!/?b[ >/])[^>]*>")

_DECK_DESCRIPTION = (
    'The <a href="https://github.com/donkuri/Kaishi">Kaishi 1.5k deck</a>'
    " reformatted for the"
    ' <a href="https://mvj.link/dojo">MvJ Method</a>'
    " (100% listening with"
    ' <a href="https://mvj.link/conceptual-defs">conceptual definitions</a>).'
    "<br><br>"
    "Definitions were generated with Opus 4.6."
    "<br><br>"
    "Go to <code>Tools</code> &gt; <code>\U0001f1ef\U0001f1f5 MvJ Note Type</code>"
    " to customize the note type."
    " <h1>How to Use</h1>"
    "<br>"
    "When reviewing, if you can roughly remember what the target word means,"
    ' then mark the card "good".'
    "<br><br>"
    "<b>Don\u2019t worry about understanding the sentence.</b>"
    " If you understand the sentence, great."
    " If not, that\u2019s fine."
    " The sentence is just there to give you a little extra context"
    " and make the target word easier to remember."
    "<h1>Audio-Specific Hotkeys</h1>"
    "<br>"
    "<i>Note: Anki\u2019s native \u201cr\u201d hotkey for replaying audio"
    " won\u2019t work on the MvJ note type.</i>"
    "<br><br>"
    "Instead, control cards using the following hotkeys"
    " (customizable in the MvJ Note Type settings):"
    "<br>"
    "<ul>"
    "<li><code>z</code> \u2013 Play just word audio</li>"
    "<li><code>x</code> \u2013 Play just sentence audio</li>"
    "<li><code>c</code> \u2013 Play just definition audio</li>"
    "<li><code>,</code> \u2013 Play all audio on card</li>"
    "<li><code>.</code> \u2013 Stop playing audio</li>"
    "<li><code>h</code> \u2013 Reveal hidden definition</li>"
    "<li><code>n</code> \u2013 Reveal details</li>"
    "</ul>"
    "<br>"
    "\u2013<i>Matt vs Japan</i>"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _normalize_key(text: str) -> str:
    """Normalize a sentence field for matching.

    Strips furigana brackets and non-bold HTML but preserves <b>/</b> tags
    (they distinguish cards sharing the same sentence but targeting different
    words).
    """
    text = _FURIGANA_RE.sub("", text)
    text = _NON_BOLD_HTML_RE.sub("", text)
    return text.strip()


def _sound_to_audio(text: str) -> str:
    """Convert [sound:...] tags to [audio:...] for the MvJ note type."""
    return _SOUND_RE.sub("[audio:", text)


def _parse_cards_tsv(data: bytes) -> list[dict]:
    """Parse cards.tsv into a list of row dicts keyed by column name."""
    text = data.decode("utf-8")
    # TSV was written with backslash-escaped quotes; unescape first so the
    # standard csv reader can handle remaining double-quote quoting (Image col).
    text = text.replace('\\"', '"')
    reader = csv.reader(io.StringIO(text), delimiter="\t", quotechar='"')
    header = next(reader)
    return [dict(zip(header, row)) for row in reader]


def _build_key_index(rows: list[dict]) -> dict[str, dict]:
    """Build {normalized_sentence_key: row} lookup for matching."""
    index = {}
    for row in rows:
        for col in ("sentence_key_furigana", "sentence_key_plain"):
            key = _normalize_key(row[col])
            if key not in index:
                index[key] = row
    return index


def _download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _download_with_progress(url: str, dest: str, label: str) -> None:
    """Download a large file with progress updates (call from background thread)."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mw.taskman.run_on_main(
                        lambda p=pct, l=label: mw.progress.update(
                            label=f"{l} ({p}%)..."
                        )
                    )


def _fix_zip_filename(name: str) -> str:
    """Fix ZIP filenames decoded as CP437 instead of UTF-8."""
    try:
        return name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def _extract_zip_to_media(zip_path: str) -> int:
    """Extract all files from a zip into Anki's media folder. Returns count."""
    media_dir = mw.col.media.dir()
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _fix_zip_filename(os.path.basename(info.filename))
            if not name:
                continue
            with zf.open(info) as src, open(os.path.join(media_dir, name), "wb") as dst:
                dst.write(src.read())
            count += 1
    return count


def _get_sentence_field(note, model) -> str | None:
    """Get the sentence text from a note for matching.

    Prefers 'Sentence Furigana' (community Kaishi has this field).
    Falls back to 'Sentence'.
    """
    for fld in model["flds"]:
        name = fld["name"]
        if "furigana" in name.lower() and "sentence" in name.lower():
            try:
                val = note[name]
                if val:
                    return val
            except KeyError:
                pass
    try:
        return note["Sentence"]
    except KeyError:
        return None


def _find_kaishi_note_types() -> list[str]:
    """Find note type names that are Kaishi-like or old MvJ Listening.

    Excludes the current 🇯🇵 MvJ note type (migration target).
    """
    result = []
    for model in mw.col.models.all():
        name = model["name"]
        if name == NOTE_TYPE_NAME:
            continue
        if name.lower() == _KAISHI_NOTE_TYPE.lower() or name in _OLD_NOTE_TYPE_NAMES:
            result.append(name)
    return result


def _has_kaishi_note_type() -> bool:
    """Check if any Kaishi-related note type exists (for Install warning)."""
    for model in mw.col.models.all():
        if "kaishi" in model["name"].lower():
            return True
    return False


def _pick_deck_name() -> str:
    """Return deck name, appending ' (2)' if the default already exists."""
    existing = {d.name for d in mw.col.decks.all_names_and_ids()}
    if _DECK_NAME not in existing:
        return _DECK_NAME
    return f"{_DECK_NAME} (2)"


def _set_deck_options(deck_id: int) -> None:
    """Create 'MvJ' options group with recommended settings (Install only)."""
    try:
        conf = mw.col.decks.add_config("MvJ")
        conf["new"]["perDay"] = 10
        conf["rev"]["perDay"] = 999
        mw.col.decks.save(conf)
        deck = mw.col.decks.get(deck_id)
        deck["conf"] = conf["id"]
        mw.col.decks.save(deck)
    except Exception:
        pass


def _set_deck_description(deck_id: int) -> None:
    try:
        deck = mw.col.decks.get(deck_id)
        deck["desc"] = _DECK_DESCRIPTION
        mw.col.decks.save(deck)
    except Exception:
        pass


def _download_and_extract_zip(url: str, label: str) -> int:
    """Download a zip to a temp file, extract to media dir, clean up."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        _download_with_progress(url, tmp_path, label)
        mw.taskman.run_on_main(
            lambda: mw.progress.update(label="Extracting files...")
        )
        return _extract_zip_to_media(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def run_install() -> None:
    """Entry point for Tools > MvJ Kaishi > Install."""
    if _has_kaishi_note_type():
        reply = QMessageBox.warning(
            mw,
            "Existing Kaishi Detected",
            "You already have Kaishi installed. This will add a separate "
            "copy.\n\n"
            "Use Migrate instead to convert your existing deck "
            "and preserve your scheduling.\n\n"
            "Continue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    deck_name = _pick_deck_name()

    reply = QMessageBox.question(
        mw,
        "Install MvJ Kaishi",
        f"This will download ~92 MB of media and create 1,500 cards "
        f'in deck "{deck_name}".\n\nContinue?',
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    mw.progress.start(label="Downloading card data...", parent=mw)

    def task():
        tsv_data = _download_bytes(_CARDS_TSV_URL)
        rows = _parse_cards_tsv(tsv_data)
        _download_and_extract_zip(_FULL_MEDIA_ZIP_URL, "Downloading media")
        return rows

    def on_done(future):
        mw.progress.finish()
        try:
            rows = future.result()
        except HTTPError as e:
            showWarning(f"Download failed: HTTP {e.code}")
            return
        except URLError as e:
            showWarning(f"Connection failed: {e.reason}")
            return
        except Exception as e:
            showWarning(f"Install failed: {e}")
            return

        model = mw.col.models.by_name(NOTE_TYPE_NAME)
        if not model:
            showWarning(f'Note type "{NOTE_TYPE_NAME}" not found.')
            return

        deck_id = mw.col.decks.id(deck_name)

        # Clear any template deck override so add_note respects our deck_id
        tmpl = model["tmpls"][0]
        old_did = tmpl.get("did")
        if old_did:
            tmpl["did"] = None
            mw.col.models.update_dict(model)

        try:
            from anki.collection import AddNoteRequest
            requests = []
            for row in rows:
                note = mw.col.new_note(model)
                for field in _TSV_FIELDS:
                    note[field] = _sound_to_audio(row[field])
                requests.append(AddNoteRequest(note=note, deck_id=deck_id))
            mw.col.add_notes(requests)
        finally:
            # Restore template deck override if it was set
            if old_did:
                tmpl["did"] = old_did
                mw.col.models.update_dict(model)

        _set_deck_options(deck_id)
        _set_deck_description(deck_id)
        mw.reset()
        showInfo(f"Installed {deck_name} \u2014 {len(rows)} cards created.")

    mw.taskman.run_in_background(task, on_done)


# ---------------------------------------------------------------------------
# Migrate
# ---------------------------------------------------------------------------


def run_migrate() -> None:
    """Entry point for Tools > MvJ Kaishi > Migrate."""
    kaishi_types = _find_kaishi_note_types()
    if not kaishi_types:
        showInfo("No Kaishi or MvJ Listening notes found to migrate.")
        return

    mw.progress.start(label="Downloading card data...", parent=mw)

    def scan_task():
        tsv_data = _download_bytes(_CARDS_TSV_URL)
        rows = _parse_cards_tsv(tsv_data)
        key_index = _build_key_index(rows)

        # Scan collection for matching notes
        # matched: nid → (row_dict, source_model_id)
        matched = {}
        skipped = 0
        total_scanned = 0

        for type_name in kaishi_types:
            model = mw.col.models.by_name(type_name)
            if not model:
                continue
            note_ids = mw.col.find_notes(f'"note:{type_name}"')
            for nid in note_ids:
                total_scanned += 1
                note = mw.col.get_note(nid)
                sentence = _get_sentence_field(note, model)
                if not sentence:
                    skipped += 1
                    continue
                key = _normalize_key(sentence)
                if key in key_index:
                    matched[nid] = (key_index[key], model["id"])
                else:
                    skipped += 1

        return matched, skipped, total_scanned

    def on_scan_done(future):
        mw.progress.finish()
        try:
            matched, skipped, total_scanned = future.result()
        except HTTPError as e:
            showWarning(f"Download failed: HTTP {e.code}")
            return
        except URLError as e:
            showWarning(f"Connection failed: {e.reason}")
            return
        except Exception as e:
            showWarning(f"Scan failed: {e}")
            return

        if not matched:
            showInfo("No matching Kaishi cards found in your collection.")
            return

        msg = (
            f"Found {len(matched)} matching Kaishi cards"
            f" (out of {total_scanned} scanned).\n\n"
            f"This will:\n"
            f"\u2022 Change note type to {NOTE_TYPE_NAME}\n"
            f"\u2022 Overwrite fields with latest card data\n"
            f"\u2022 Download ~20 MB of definition audio\n"
        )
        if skipped:
            msg += (
                f"\n{skipped} cards didn\u2019t match and will be "
                f"left unchanged.\n"
            )
        msg += "\nScheduling will be preserved. Continue?"

        reply = QMessageBox.question(
            mw, "Migrate Kaishi", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        _start_migrate_download(matched)

    mw.taskman.run_in_background(scan_task, on_scan_done)


def _start_migrate_download(matched: dict) -> None:
    """Phase 2: download definition audio, then apply migration."""
    mw.progress.start(label="Downloading definition audio...", parent=mw)

    def download_task():
        _download_and_extract_zip(_DEF_AUDIO_ZIP_URL, "Downloading definition audio")

    def on_download_done(future):
        mw.progress.finish()
        try:
            future.result()
        except HTTPError as e:
            showWarning(f"Download failed: HTTP {e.code}")
            return
        except URLError as e:
            showWarning(f"Connection failed: {e.reason}")
            return
        except Exception as e:
            showWarning(f"Download failed: {e}")
            return

        _apply_migration(matched)
        _migrate_deck()
        mw.reset()

        showInfo(
            f"Migration complete!\n\n"
            f"\u2022 {len(matched)} cards migrated to {NOTE_TYPE_NAME}\n\n"
            f"You can undo with Edit \u2192 Undo."
        )

    mw.taskman.run_in_background(download_task, on_download_done)


def _apply_migration(matched: dict) -> None:
    """Change note types and overwrite fields for matched notes."""
    mvj_model = mw.col.models.by_name(NOTE_TYPE_NAME)
    if not mvj_model:
        showWarning(f'Note type "{NOTE_TYPE_NAME}" not found.')
        return

    # Group by source note type (API requires same source per call)
    by_source: dict[int, list[int]] = {}
    for nid, (_, source_id) in matched.items():
        by_source.setdefault(source_id, []).append(nid)

    # Change note types (preserves scheduling)
    for source_id, nids in by_source.items():
        info = mw.col.models.change_notetype_info(
            old_notetype_id=source_id,
            new_notetype_id=mvj_model["id"],
        )
        req = info.input
        req.note_ids.extend(nids)
        mw.col.models.change_notetype_of_notes(req)

    # Overwrite fields from TSV data
    pos = mw.col.add_custom_undo_entry("Migrate Kaishi notes to MvJ")
    modified = []
    for nid, (row, _) in matched.items():
        note = mw.col.get_note(nid)
        for field in _TSV_FIELDS:
            note[field] = _sound_to_audio(row[field])
        modified.append(note)
    mw.col.update_notes(modified)
    mw.col.merge_undo_entries(pos)


def _migrate_deck() -> None:
    """Rename existing Kaishi deck and update description."""
    for d in mw.col.decks.all_names_and_ids():
        if d.name in _EXISTING_DECK_NAMES:
            if d.name != _DECK_NAME:
                mw.col.decks.rename(d.id, _DECK_NAME)
            _set_deck_description(d.id)
            break
