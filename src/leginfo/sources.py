"""Fetching upstream data: the official bulk feed and the GitHub law-text mirror.

Two sources, in order of preference:

1. ``downloads.leginfo.legislature.ca.gov`` – the official ``pubinfo_<session>.zip``
   (~764 MB). It carries *everything*: the 29 codes with their CAML content files,
   every bill since 1999, its versions, actions, votes, analyses and authors.
   Use :func:`fetch_bulk` where outbound access to the host is allowed.

2. ``github.com/johnakelly-yahoo-com/california-codes`` – a nightly mirror that
   republishes the law text as plain text. Far smaller and reachable from
   network-restricted environments, but law only: no bills. Use
   :func:`fetch_mirror`.
"""

from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path

from .config import MIRROR_TARBALL_URL, bulk_zip_url, session_start_year
from .util import download, get_logger, human_bytes

__all__ = ["fetch_mirror", "fetch_bulk", "extract_bulk", "list_bulk_members"]

LOG = get_logger()


def fetch_mirror(dest_dir: str | os.PathLike[str], *, force: bool = False) -> Path:
    """Download the law-text mirror tarball and extract ``codes/*.txt``.

    Returns the directory holding the ``CA Code - <Name>.txt`` files.
    """
    dest_dir = Path(dest_dir)
    raw_dir = dest_dir / "_mirror"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tarball = raw_dir / "california-codes.tar.gz"

    download(MIRROR_TARBALL_URL, tarball, force=force, label="california-codes tarball")

    out_dir = dest_dir / "codes"
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with tarfile.open(tarball, "r:gz") as tar:
        for member in tar:
            name = Path(member.name).name
            if not name.endswith(".txt") or not name.startswith("CA Code - "):
                continue
            target = out_dir / name
            if target.exists() and not force and target.stat().st_size == member.size:
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            target.write_bytes(source.read())
            extracted += 1
    LOG.info("mirror ready: %s files in %s (%s extracted)", len(list(out_dir.glob('*.txt'))), out_dir, extracted)
    return out_dir


def fetch_bulk(
    dest_dir: str | os.PathLike[str],
    *,
    session_year: int | None = None,
    force: bool = False,
) -> Path:
    """Download the official ``pubinfo_<session>.zip`` into ``dest_dir``."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    session = session_start_year(session_year)
    url = bulk_zip_url(session)
    target = dest_dir / f"pubinfo_{session}.zip"
    download(url, target, force=force, label=f"pubinfo_{session}.zip")
    LOG.info("bulk archive: %s (%s)", target, human_bytes(target.stat().st_size))
    return target


def list_bulk_members(zip_path: str | os.PathLike[str]) -> list[tuple[str, int]]:
    """Return ``(name, uncompressed_size)`` for every member of the archive."""
    with zipfile.ZipFile(zip_path) as zf:
        return [(info.filename, info.file_size) for info in zf.infolist()]


def extract_bulk(
    zip_path: str | os.PathLike[str],
    dest_dir: str | os.PathLike[str],
    members: list[str] | None = None,
    *,
    skip_existing: bool = True,
) -> Path:
    """Extract members from the bulk archive.

    ``members=None`` extracts the top-level ``*.dat`` tables only — the XML content
    files are extracted on demand instead, because there are hundreds of thousands
    of them and the importer streams straight out of the archive.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        if members is None:
            members = [
                info.filename
                for info in zf.infolist()
                if "/" not in info.filename and info.filename.lower().endswith(".dat")
            ]
        for name in members:
            target = dest_dir / name
            if skip_existing and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
    LOG.info("extracted %s members to %s", len(members), dest_dir)
    return dest_dir
