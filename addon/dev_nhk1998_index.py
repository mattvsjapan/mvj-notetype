"""Dev-only: build an index DB for the NHK 1998 audio collection.

The collection at _AUDIO_DIR is ~149k loose mp3 files named

    <headword>.<type><HEXID>_<HEX>.mp3

where <type> is one of yomi / jyoshi / reibun. There is no pitch-accent
information in the filenames, so this is an audio-only source: dev_lookup
matches a word against the headword prefix and attaches the audio.

Scanning 149k filenames on every lookup is wasteful, so this script builds
a small SQLite index (mirroring the daijisen.db / nhk.db layout under
dictionary/) keyed by headword. The mp3s themselves stay at _AUDIO_DIR.

This file is .gitignored / excluded from packaging (dictionary/* is too).

Run from the repo:  python3 addon/dev_nhk1998_index.py
"""

import os
import re
import sqlite3

_AUDIO_DIR = "/Users/matt/Documents/Audio/nhk1998"
_DB_PATH = os.path.join(
    os.path.dirname(__file__), "dictionary", "nhk1998", "nhk1998.db"
)

# <headword>.<type><HEXID>_<HEX>.mp3 — the trailing structure is rigid enough
# that a greedy headword still anchors correctly.
_NAME_RE = re.compile(
    r'^(?P<hw>.+)\.(?P<type>yomi|jyoshi|reibun)'
    r'(?P<id>[0-9A-Fa-f]+)_[0-9A-Fa-f]+\.mp3$'
)


def build_index() -> None:
    if not os.path.isdir(_AUDIO_DIR):
        raise SystemExit(f"Audio dir not found: {_AUDIO_DIR}")

    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)

    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE files ("
        "  headword TEXT NOT NULL,"
        "  type     TEXT NOT NULL,"
        "  filename TEXT NOT NULL,"
        "  position INTEGER NOT NULL"  # int of the hex record id, for stable order
        ")"
    )

    rows: list[tuple[str, str, str, int]] = []
    skipped = 0
    for name in os.listdir(_AUDIO_DIR):
        if not name.endswith(".mp3"):
            continue
        m = _NAME_RE.match(name)
        if not m:
            skipped += 1
            continue
        rows.append(
            (m.group("hw"), m.group("type"), name, int(m.group("id"), 16))
        )

    conn.executemany(
        "INSERT INTO files (headword, type, filename, position) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.execute("CREATE INDEX idx_files_headword ON files (headword)")
    conn.commit()

    by_type = conn.execute(
        "SELECT type, COUNT(*) FROM files GROUP BY type ORDER BY type"
    ).fetchall()
    headwords = conn.execute(
        "SELECT COUNT(DISTINCT headword) FROM files"
    ).fetchone()[0]
    conn.close()

    print(f"Indexed {len(rows)} files ({headwords} distinct headwords) "
          f"into {_DB_PATH}")
    for t, c in by_type:
        print(f"  {t}: {c}")
    if skipped:
        print(f"  skipped (unparsed name): {skipped}")


if __name__ == "__main__":
    build_index()
