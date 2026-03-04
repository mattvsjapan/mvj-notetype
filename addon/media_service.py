"""
Media analysis service for the MvJ note type addon.

Provides functions to extract media references from notes and analyze
media usage across source and Anki media folders. Adapted from
MvJ Japanese's media service for standalone use.
"""

import html
import os
import re
from urllib.parse import unquote

from aqt import mw

SOUND_TAG_PATTERN = re.compile(r'\[(?:sound|audio):([^\]]+)\]')
IMG_TAG_PATTERN = re.compile(r'<img[^>]+src=(?:"([^"]+)"|\'([^\']+)\')')


def _log(msg):
    print(f"[MvJ Media] {msg}")


def _extract_media_from_fields(fields):
    """Extract media filenames from a list of field strings."""
    media_files = set()
    for field in fields:
        sounds = [html.unescape(s) for s in SOUND_TAG_PATTERN.findall(field or "")]
        media_files.update(sounds)
        images = [
            unquote(html.unescape(g1 or g2))
            for g1, g2 in IMG_TAG_PATTERN.findall(field or "")
            if not (g1 or g2).strip().lower().startswith("data:")
        ]
        media_files.update(images)
    return media_files


def extract_media_files(note, media_type=None):
    """Extract all media file references from a note.

    Args:
        note: Anki Note object
        media_type: None (all), 'audio', or 'image'

    Returns:
        Set of filenames referenced by the note
    """
    if media_type is None:
        return _extract_media_from_fields(note.fields)

    media_files = set()

    for field in note.fields:
        if media_type != 'image':
            sounds = [html.unescape(s) for s in SOUND_TAG_PATTERN.findall(field or "")]
            media_files.update(sounds)
            if media_type == 'audio':
                continue

        if media_type != 'audio':
            images = [
                unquote(html.unescape(g1 or g2))
                for g1, g2 in IMG_TAG_PATTERN.findall(field or "")
                if not (g1 or g2).strip().lower().startswith("data:")
            ]
            media_files.update(images)

    return media_files


def _build_media_reference_map(exclude_note_ids=None):
    """Build a reverse index mapping media files to note IDs that reference them.

    Args:
        exclude_note_ids: Set of note IDs to exclude from the map

    Returns:
        Dict mapping filename -> set of note IDs that reference it
    """
    if not mw or not mw.col:
        return {}

    if exclude_note_ids is None:
        exclude_note_ids = set()

    media_map = {}

    try:
        rows = mw.col.db.all("select id, flds from notes")
        checked = 0

        for nid, flds in rows:
            if nid in exclude_note_ids:
                continue
            checked += 1

            fields = flds.split("\x1f")
            media_files = _extract_media_from_fields(fields)

            for filename in media_files:
                if filename not in media_map:
                    media_map[filename] = set()
                media_map[filename].add(nid)

        _log(f"Built media reference map: {len(media_map)} unique files across "
             f"{checked} notes")
        return media_map

    except Exception as e:
        _log(f"Error building media reference map: {e}")
        return {}


def get_mvj_source_folder():
    """Get the MvJ Japanese source media folder, if available.

    Reads the configured source folder from MvJ Japanese addon config
    via Anki's public addon API. Falls back to checking the default
    user_files/database.media location.

    Returns:
        Path string if found, or None if MvJ Japanese is not installed
        or no source folder exists.
    """
    if not mw:
        return None

    try:
        config = mw.addonManager.getConfig("MvJ Japanese")
        if config:
            source = config.get("media", {}).get("media_source_folder", "")
            if source and os.path.isdir(source):
                return source
    except Exception:
        pass

    # Fallback: check default location
    try:
        addon_dir = os.path.join(mw.addonManager.addonsFolder(), "MvJ Japanese")
        default_path = os.path.join(addon_dir, "user_files", "database.media")
        if os.path.isdir(default_path):
            return default_path
    except Exception:
        pass

    return None


def analyze_media_usage(source_folder=None):
    """Analyze media usage across source folder and Anki media folder.

    Args:
        source_folder: Path to source media folder, or None to skip
                       source analysis (e.g. when MvJ Japanese not installed)

    Returns:
        Dict with categorized media files:
        {
            'source_unreferenced': [filenames],
            'source_duplicated': [filenames],
            'source_used': [filenames],
            'anki_orphaned': [filenames],
            'anki_protected': [filenames],
            'anki_used': [filenames]
        }
    """
    if not mw or not mw.col:
        return {
            'source_unreferenced': [],
            'source_duplicated': [],
            'source_used': [],
            'anki_orphaned': [],
            'anki_protected': [],
            'anki_used': []
        }

    media_dir = mw.col.media.dir()

    result = {
        'source_unreferenced': [],
        'source_duplicated': [],
        'source_used': [],
        'anki_orphaned': [],
        'anki_protected': [],
        'anki_used': []
    }

    # Build media reference map (mapping filename -> set of note IDs)
    _log("Building media reference map for analysis...")
    media_ref_map = _build_media_reference_map(set())

    # Scan Anki media folder first so source analysis can use the set
    anki_files = []
    anki_files_set = set()
    if media_dir and os.path.exists(media_dir):
        _log(f"Scanning Anki media folder: {media_dir}")
        try:
            anki_files = [e.name for e in os.scandir(media_dir) if e.is_file()]
            anki_files_set = set(anki_files)
        except Exception as e:
            _log(f"Error scanning Anki media folder: {e}")

    # Analyze source folder
    if source_folder and os.path.exists(source_folder):
        _log(f"Analyzing source folder: {source_folder}")
        try:
            source_files = [e.name for e in os.scandir(source_folder) if e.is_file()]

            for filename in source_files:
                ref_count = len(media_ref_map.get(filename, set()))
                in_anki = filename in anki_files_set

                # Also count LOCKED_ references (legacy notes not yet regenerated)
                disabled_version = f"LOCKED_{filename}"
                disabled_ref_count = len(media_ref_map.get(disabled_version, set()))
                effective_ref_count = ref_count + disabled_ref_count

                if effective_ref_count == 0:
                    result['source_unreferenced'].append(filename)
                elif in_anki:
                    result['source_duplicated'].append(filename)
                else:
                    result['source_used'].append(filename)

            _log(f"Source folder: {len(result['source_unreferenced'])} unreferenced, "
                 f"{len(result['source_duplicated'])} duplicated, "
                 f"{len(result['source_used'])} used")
        except Exception as e:
            _log(f"Error analyzing source folder: {e}")

    # Analyze Anki media folder
    if anki_files:
        _log(f"Analyzing Anki media folder: {media_dir}")
        for filename in anki_files:
            ref_count = len(media_ref_map.get(filename, set()))

            if ref_count == 0:
                if filename.startswith('_'):
                    result['anki_protected'].append(filename)
                else:
                    # Check LOCKED_ references (legacy notes not yet regenerated)
                    disabled_version = f"LOCKED_{filename}"
                    disabled_ref_count = len(media_ref_map.get(disabled_version, set()))
                    if disabled_ref_count > 0:
                        result['anki_used'].append(filename)
                    else:
                        result['anki_orphaned'].append(filename)
            else:
                result['anki_used'].append(filename)

        _log(f"Anki folder: {len(result['anki_orphaned'])} orphaned, "
             f"{len(result['anki_protected'])} protected, "
             f"{len(result['anki_used'])} in-use")

    return result
