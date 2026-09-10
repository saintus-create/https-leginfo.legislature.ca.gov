"""Small, dependency-free helpers shared by the collectors and parsers.

The whole pipeline intentionally uses the Python standard library only, so it
runs anywhere Python 3.9+ runs: no virtualenv, no pip install, no surprises.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

__all__ = [
    "get_logger",
    "download",
    "sha256_file",
    "atomic_write",
    "write_jsonl_gz",
    "read_jsonl_gz",
    "write_json",
    "human_bytes",
    "clean_text",
    "is_blank",
]

LOG = logging.getLogger("leginfo")

USER_AGENT = "leginfo-dataset/1.0 (+ California Legislative Information public-domain data)"
REQUEST_TIMEOUT = 60
REQUEST_RETRIES = 4
REQUEST_BACKOFF = 2.0


def get_logger(name: str = "leginfo") -> logging.Logger:
    """Return a configured logger (idempotent)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def human_bytes(n: float) -> str:
    """Render a byte count as MB/GB."""
    step = 1024.0
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < step or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} TB"


def download(
    url: str,
    dest: str | os.PathLike[str],
    *,
    force: bool = False,
    label: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
    retries: int = REQUEST_RETRIES,
) -> Path:
    """Download ``url`` to ``dest`` with retries, HTTP Range resume and progress.

    Large upstream files (the official bulk ZIP is ~764 MB) are the norm here, so
    partial downloads are resumed rather than restarted.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log = get_logger()
    name = label or dest.name

    if dest.exists() and not force:
        log.info("%s already downloaded (%s) — skipping", name, human_bytes(dest.stat().st_size))
        return dest

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        resume_from = dest.stat().st_size if dest.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if resume_from and response.status != 206:
                    # Server ignored the Range request; start over.
                    resume_from = 0
                mode = "ab" if resume_from else "wb"
                total = response.headers.get("Content-Length")
                total_size = int(total) + resume_from if total else None
                downloaded = resume_from
                started = time.time()
                with open(dest, mode) as handle:
                    while True:
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        elapsed = max(time.time() - started, 1e-6)
                        rate = downloaded / elapsed / 1024 / 1024
                        if total_size:
                            pct = 100 * downloaded / total_size
                            log.info(
                                "%s: %s / %s (%.1f%%, %.1f MB/s)",
                                name,
                                human_bytes(downloaded),
                                human_bytes(total_size),
                                pct,
                                rate,
                            )
                        else:
                            log.info("%s: %s downloaded (%.1f MB/s)", name, human_bytes(downloaded), rate)
            log.info("finished %s (%s)", name, human_bytes(dest.stat().st_size))
            return dest
        except (urllib.error.URLError, TimeoutError, OSError) as exc:  # noqa: PERF203
            last_error = exc
            log.warning("download attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(REQUEST_BACKOFF * attempt)

    raise RuntimeError(f"could not download {url}: {last_error}")


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Stream a file through SHA-256 (files here are far too big to read at once)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: str | os.PathLike[str], writer) -> Path:
    """Write via a temp file in the same directory, then rename into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")[1])
    try:
        writer(tmp)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not JSON serializable: {type(obj)!r}")


def write_jsonl_gz(path: str | os.PathLike[str], records: Iterable[dict[str, Any]]) -> int:
    """Write records as gzip-compressed JSON Lines; return the record count."""
    path = Path(path)
    count = 0

    def _write(tmp: Path) -> None:
        nonlocal count
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, default=_json_default))
                handle.write("\n")
                count += 1

    atomic_write(path, _write)
    return count


def read_jsonl_gz(path: str | os.PathLike[str]) -> Iterator[dict[str, Any]]:
    """Stream records back out of a gzip-compressed JSON Lines file."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: str | os.PathLike[str], payload: Any, *, indent: int = 2) -> Path:
    """Write pretty-printed JSON atomically."""

    def _write(tmp: Path) -> None:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=indent, default=_json_default)
            handle.write("\n")

    return atomic_write(path, _write)


_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalise whitespace inside a block of statutory text."""
    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def is_blank(line: str) -> bool:
    """True for empty/whitespace-only lines."""
    return not line.strip()
