"""Utility functions for converting .m4a media files to .mp3 via ffmpeg."""

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional


def find_ffmpeg() -> Optional[str]:
    """Locate the ffmpeg binary. Checks PATH then common install locations.

    GUI apps (like Anki) often don't inherit the shell PATH, so we also
    check platform-specific common install directories.
    """
    path = shutil.which("ffmpeg")
    if path:
        return path

    if platform.system() == "Windows":
        candidates = [
            Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
            Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
    else:
        # macOS and Linux — same list as Audio Trimmer addon
        candidates = [
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
            Path("/bin/ffmpeg"),
        ]

    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def convert_m4a_to_mp3(m4a_path: str, mp3_path: str, ffmpeg_path: str = "ffmpeg") -> None:
    """Convert a single .m4a file to .mp3 using ffmpeg.

    Raises subprocess.CalledProcessError on failure.
    """
    kwargs: dict = {}
    # Prevent console window flash on Windows
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(
        [ffmpeg_path, "-i", m4a_path, "-y", mp3_path],
        check=True,
        capture_output=True,
        **kwargs,
    )


_M4A_AUDIO_RE = re.compile(r"\[audio:([^\]]*\.m4a)\]", re.IGNORECASE)


def m4a_to_mp3_filename(fname: str) -> str:
    """Replace .m4a extension with .mp3 (case-insensitive)."""
    base, ext = os.path.splitext(fname)
    if ext.lower() == ".m4a":
        return base + ".mp3"
    return fname


def rewrite_m4a_tags(text: str, media_dir: Optional[str] = None) -> str:
    """Rewrite [audio:*.m4a] → [audio:*.mp3] in text.

    If media_dir is provided, only rewrites refs where the .mp3 file actually
    exists on disk (i.e. the conversion succeeded). This prevents broken
    references when ffmpeg is missing or conversion fails.
    """
    def _replace(m):
        mp3_name = m4a_to_mp3_filename(m.group(1))
        if media_dir is not None:
            mp3_path = os.path.join(media_dir, mp3_name)
            if not os.path.exists(mp3_path):
                return m.group(0)  # keep original .m4a ref
        return f"[audio:{mp3_name}]"
    return _M4A_AUDIO_RE.sub(_replace, text)


def convert_m4a_files(
    m4a_filenames: list[str],
    media_dir: str,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> list[tuple[str, str]]:
    """Batch-convert .m4a files to .mp3 in the given media directory.

    Returns list of (old_name, new_name) pairs for files that were converted
    or already had an .mp3 equivalent. Skips files where the .mp3 already
    exists. Does NOT delete originals.

    Raises RuntimeError if ffmpeg is not found (and there are files to convert).
    """
    results: list[tuple[str, str]] = []
    need_convert: list[tuple[str, str]] = []

    for fname in m4a_filenames:
        mp3_name = m4a_to_mp3_filename(fname)
        m4a_path = os.path.join(media_dir, fname)
        mp3_path = os.path.join(media_dir, mp3_name)

        if os.path.exists(mp3_path):
            results.append((fname, mp3_name))
        elif os.path.exists(m4a_path):
            need_convert.append((fname, mp3_name))
        # else: source file missing, skip silently

    if need_convert:
        ffmpeg = find_ffmpeg()
        if ffmpeg is None:
            raise RuntimeError(
                "ffmpeg is not installed or not on PATH.\n\n"
                "Install ffmpeg to enable automatic .m4a → .mp3 conversion.\n"
                "  macOS: brew install ffmpeg\n"
                "  Windows: winget install ffmpeg\n"
                "  Linux: sudo apt install ffmpeg"
            )

        for i, (old_name, new_name) in enumerate(need_convert):
            if on_progress:
                on_progress(i, len(need_convert))
            m4a_path = os.path.join(media_dir, old_name)
            mp3_path = os.path.join(media_dir, new_name)
            convert_m4a_to_mp3(m4a_path, mp3_path, ffmpeg_path=ffmpeg)
            results.append((old_name, new_name))

    return results
