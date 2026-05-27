"""Tests for the resumable, verified downloader (addon/downloader.py).

Pure unit tests driven by a fake ``urlopen`` -- no network, no Anki. Run directly:

    python3 addon/tests/test_downloader.py
"""

import http.client
import os
import sys
import tempfile
import types
import zipfile
from urllib.error import HTTPError, URLError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import downloader  # noqa: E402
from downloader import (  # noqa: E402
    CorruptDownloadError,
    IncompleteDownloadError,
    download_to_file,
    verify_zip,
)

# Don't actually sleep during backoff. Rebinding the module's ``time`` name (vs.
# mutating the shared time module) keeps the patch local to the downloader.
downloader.time = types.SimpleNamespace(sleep=lambda *a, **k: None)

URL = "http://example.test/media.zip"
DATA = bytes(i % 256 for i in range(100))


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeResp:
    """Minimal stand-in for an urlopen result / http.client.HTTPResponse."""

    def __init__(self, body, status=200, headers=None):
        self._body = body
        self._pos = 0
        self.status = status
        self.headers = headers or {}

    def read(self, n):
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Returns a scripted response/exception per call; records Range headers."""

    def __init__(self, script):
        self._script = list(script)
        self.ranges = []
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        self.ranges.append(req.get_header("Range"))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix=".bin")
    os.close(fd)
    return path


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _rm(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _ok200(body, total=None):
    total = len(body) if total is None else total
    return FakeResp(body, 200, {"Content-Length": str(total)})


def _part206(body, start, total):
    return FakeResp(body, 206, {"Content-Range": f"bytes {start}-{total - 1}/{total}"})


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_complete():
    opener = FakeOpener([_ok200(DATA)])
    progress = []
    path = _tmp_path()
    try:
        download_to_file(URL, path, on_progress=lambda d, t: progress.append((d, t)),
                         opener=opener)
        assert _read(path) == DATA, "file content mismatch"
        assert progress[-1] == (len(DATA), len(DATA)), f"final progress {progress[-1]}"
    finally:
        _rm(path)


def test_truncated_no_progress():
    # Every attempt connects but delivers zero bytes; Content-Length claims 100.
    opener = FakeOpener([_ok200(b"", total=100) for _ in range(10)])
    path = _tmp_path()
    try:
        err = None
        try:
            download_to_file(URL, path, opener=opener)
        except IncompleteDownloadError as e:
            err = e
        assert err is not None, "expected IncompleteDownloadError"
        assert err.total == 100 and err.downloaded == 0, (err.downloaded, err.total)
        assert opener.calls == 5, f"expected 5 attempts (max_stalls), got {opener.calls}"
    finally:
        _rm(path)


def test_choppy_progress():
    # Each attempt delivers the next 10 bytes then EOF, but always advances.
    script = [_ok200(DATA[0:10], total=100)]
    for s in range(10, 100, 10):
        script.append(_part206(DATA[s:s + 10], s, 100))
    opener = FakeOpener(script)
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA, "reassembled content mismatch"
        assert opener.calls == 10, f"expected 10 attempts, got {opener.calls}"
        assert opener.calls > 5, "more attempts than max_stalls proves the reset"
        assert opener.ranges[0] is None and opener.ranges[1] == "bytes=10-", opener.ranges
    finally:
        _rm(path)


def test_resume_206():
    opener = FakeOpener([
        _ok200(DATA[0:60], total=100),          # cut off at 60 bytes
        _part206(DATA[60:100], 60, 100),        # resume the rest
    ])
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA
        assert opener.calls == 2
        assert opener.ranges[1] == "bytes=60-", opener.ranges
    finally:
        _rm(path)


def test_bad_206_not_corrupting():
    opener = FakeOpener([
        _ok200(DATA[0:60], total=100),                          # cut off at 60
        _part206(b"X" * 40, 0, 100),                            # 206 starts at 0, not 60
        _ok200(DATA, total=100),                                # fresh full refetch
    ])
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA, "bad 206 body must not corrupt the file"
        assert opener.calls == 3
        assert opener.ranges == [None, "bytes=60-", None], opener.ranges
    finally:
        _rm(path)


def test_urlerror_retried():
    opener = FakeOpener([URLError("boom"), _ok200(DATA)])
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA
        assert opener.calls == 2
    finally:
        _rm(path)


def test_incompleteread_retried():
    opener = FakeOpener([http.client.IncompleteRead(b"partial"), _ok200(DATA)])
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA
        assert opener.calls == 2
    finally:
        _rm(path)


def test_transient_503_retried():
    opener = FakeOpener([
        HTTPError(URL, 503, "busy", {}, None),
        _ok200(DATA),
    ])
    path = _tmp_path()
    try:
        download_to_file(URL, path, opener=opener)
        assert _read(path) == DATA
        assert opener.calls == 2
    finally:
        _rm(path)


def test_404_not_retried():
    opener = FakeOpener([HTTPError(URL, 404, "Not Found", {}, None)])
    path = _tmp_path()
    try:
        err = None
        try:
            download_to_file(URL, path, opener=opener)
        except HTTPError as e:
            err = e
        assert err is not None and err.code == 404, "expected HTTPError 404"
        assert opener.calls == 1, f"404 must not retry, got {opener.calls} calls"
    finally:
        _rm(path)


def test_verify_zip():
    good, bad = _tmp_path(), _tmp_path()
    try:
        with zipfile.ZipFile(good, "w") as zf:
            zf.writestr("a.txt", "hello")
        verify_zip(good)  # must not raise

        with open(bad, "wb") as f:
            f.write(b"definitely not a zip file")
        raised = False
        try:
            verify_zip(bad)
        except CorruptDownloadError:
            raised = True
        assert raised, "expected CorruptDownloadError for a non-zip file"
    finally:
        _rm(good)
        _rm(bad)


def main() -> int:
    tests = [
        ("complete download", test_complete),
        ("truncated w/ no progress -> IncompleteDownloadError", test_truncated_no_progress),
        ("choppy but progressing completes (stall reset)", test_choppy_progress),
        ("resume via 206 Range", test_resume_206),
        ("bad 206 discarded, file not corrupted", test_bad_206_not_corrupting),
        ("URLError retried", test_urlerror_retried),
        ("IncompleteRead retried", test_incompleteread_retried),
        ("transient HTTP 503 retried", test_transient_503_retried),
        ("HTTP 404 not retried", test_404_not_retried),
        ("verify_zip valid/invalid", test_verify_zip),
    ]
    failed = 0
    for label, fn in tests:
        try:
            fn()
            print(f"PASS  {label}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {label}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {label}: {type(e).__name__}: {e}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
