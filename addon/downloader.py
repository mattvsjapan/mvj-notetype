"""Resumable, verified file downloads for the MvJ add-on.

Pure module (no aqt/anki imports) so it can be unit-tested directly, mirroring
``pitch_migration.py`` / ``pitch_converter.py``. ``kaishi.py`` keeps its Anki glue
(progress bar, dialogs) and delegates the actual transfer here.

The Kaishi media zip is ~200 MB. Some users sit behind antivirus, a proxy, or a
connection that consistently cuts a large download partway through. A plain read
loop silently treats such a truncated transfer as complete -- CPython's
``http.client`` returns an empty read on early EOF rather than raising -- which
later surfaces as a baffling "File is not a zip file". This module instead
verifies the byte count against ``Content-Length``, resumes from where it stopped
via an HTTP ``Range`` request, and retries until the file is whole.
"""

import http.client
import time
import urllib.request
import zipfile
from urllib.error import HTTPError, URLError

# Transient HTTP statuses worth retrying; anything else (404, 403, 416, ...) is a
# hard error and surfaced to the caller immediately.
_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class DownloadError(Exception):
    """Base class for download failures carrying a user-facing message."""


class IncompleteDownloadError(DownloadError):
    """A download finished with fewer bytes than the server advertised."""

    def __init__(self, downloaded: int, total: int):
        self.downloaded = downloaded
        self.total = total
        super().__init__(
            f"Download incomplete: got {_mb(downloaded)} of {_mb(total)}. "
            "Check your connection and try again."
        )


class CorruptDownloadError(DownloadError):
    """A full-sized download that isn't the expected zip (e.g. an error page)."""


class _BadRangeResponse(DownloadError):
    """Internal: a server mishandled our Range request; discard and refetch.

    Subclasses DownloadError so that, in the rare case it survives every retry,
    the caller's ``except DownloadError`` still shows a sensible message.
    """

    def __init__(self):
        super().__init__(
            "The download server returned an unexpected response. "
            "Please try again."
        )


def _mb(n: int) -> str:
    """Format a byte count as a rounded decimal-MB string for messages."""
    return f"{n / 1_000_000:.0f} MB"


def _parse_content_range(resp) -> tuple:
    """Parse a 206 ``Content-Range: bytes <start>-<end>/<total>`` header.

    Returns ``(start, total)``, or ``(None, None)`` when the header is missing or
    cannot be parsed.
    """
    header = resp.headers.get("Content-Range", "") or ""
    try:
        spec = header.split()[1]                 # "60-99/100"
        range_part, total_part = spec.split("/")
        start = int(range_part.split("-")[0])
        return start, int(total_part)
    except (IndexError, ValueError):
        return None, None


def download_to_file(
    url: str,
    dest: str,
    *,
    on_progress=None,
    opener=urllib.request.urlopen,
    timeout: int = 120,
    chunk_size: int = 65536,
    max_stalls: int = 5,
    max_attempts: int = 30,
) -> None:
    """Download *url* to *dest*, resuming partial transfers and verifying size.

    Streams the response to disk. If the connection drops before the advertised
    ``Content-Length`` is reached, it retries -- resuming from the byte offset via
    a ``Range`` request when the server honours it (HTTP 206), otherwise
    restarting the whole file.

    Because each retry resumes, a dropped connection still makes forward
    progress, so the loop keeps going as long as the byte count advances. It
    gives up only after *max_stalls* consecutive attempts make no progress, with
    *max_attempts* as an absolute backstop against pathological tiny-chunk loops.

    Args:
        on_progress: optional ``callable(downloaded: int, total: int)`` invoked as
            bytes arrive (only when the total size is known).
        opener: a ``urlopen``-compatible callable, overridable for tests.

    Raises:
        IncompleteDownloadError: the file stayed short of ``Content-Length``.
        HTTPError: a non-retryable HTTP status (e.g. 404).
        URLError / OSError: a persistent connection failure.
    """
    downloaded = total = stalls = attempts = 0
    last_err = None

    while True:
        attempts += 1
        before = downloaded
        try:
            req = urllib.request.Request(url)
            if downloaded:
                req.add_header("Range", f"bytes={downloaded}-")
            with opener(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if downloaded and status == 206:
                    start, full = _parse_content_range(resp)
                    if start != downloaded or not full:
                        # Server didn't honour our offset; appending its body
                        # onto our prefix would corrupt the file. Drop what we
                        # have and let the next attempt refetch from scratch.
                        downloaded = 0
                        raise _BadRangeResponse()
                    total, mode = full, "ab"
                else:
                    # First attempt, or the server ignored Range (status 200).
                    downloaded, mode = 0, "wb"
                    total = int(resp.headers.get("Content-Length", 0))
                with open(dest, mode) as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(downloaded, total)
            if total and downloaded != total:
                raise IncompleteDownloadError(downloaded, total)
            return
        except HTTPError as e:
            if e.code not in _RETRYABLE_HTTP:
                raise               # 404/403/416/... are deterministic
            last_err = e
        except (URLError, OSError, http.client.IncompleteRead,
                IncompleteDownloadError, _BadRangeResponse) as e:
            last_err = e

        # Any forward progress resets the stall counter and skips backoff, so a
        # choppy-but-advancing transfer isn't throttled.
        stalls = 0 if downloaded > before else stalls + 1
        if stalls >= max_stalls or attempts >= max_attempts:
            raise last_err
        if stalls:
            time.sleep(min(2 ** stalls, 8))


def verify_zip(path: str) -> None:
    """Raise CorruptDownloadError if *path* isn't a readable zip file."""
    if not zipfile.is_zipfile(path):
        raise CorruptDownloadError(
            "The downloaded media file is not a valid zip "
            "(the download may have been corrupted). Please try again."
        )
