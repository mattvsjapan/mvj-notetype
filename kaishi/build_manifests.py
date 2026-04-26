"""Build media manifests from the released zip files.

Generates two JSON manifests (filename -> SHA256) used by the addon to
verify a complete media install:

    media-manifest.json      <- kaishi-media-full-v2.zip
    def-audio-manifest.json  <- kaishi-def-audio-v2.zip

Filenames in the zip stored without the UTF-8 flag bit come back as CP437
mojibake from Python's zipfile; this script applies the same recovery
the addon uses (cp437 -> utf-8) so the manifest matches the names that
land on disk after extraction.

Usage:
    python build_manifests.py <full_zip> <def_audio_zip> <out_dir>
"""

import hashlib
import json
import os
import sys
import zipfile


def _fix_zip_filename(name: str) -> str:
    try:
        return name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def build_manifest(zip_path: str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _fix_zip_filename(os.path.basename(info.filename))
            if not name:
                continue
            with zf.open(info) as fp:
                digest = hashlib.sha256(fp.read()).hexdigest()
            if name in manifest and manifest[name] != digest:
                raise RuntimeError(
                    f"name collision with differing content: {name}"
                )
            manifest[name] = digest
    return dict(sorted(manifest.items()))


def write_manifest(manifest: dict[str, str], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    full_zip, def_audio_zip, out_dir = argv[1:]
    os.makedirs(out_dir, exist_ok=True)

    full = build_manifest(full_zip)
    write_manifest(full, os.path.join(out_dir, "media-manifest.json"))
    print(f"media-manifest.json: {len(full)} entries")

    def_audio = build_manifest(def_audio_zip)
    write_manifest(def_audio, os.path.join(out_dir, "def-audio-manifest.json"))
    print(f"def-audio-manifest.json: {len(def_audio)} entries")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
