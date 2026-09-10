"""Parse the official LegInfo bulk archive (``pubinfo_<session>.zip``).

Archive layout
--------------
The ZIP contains flat, tab-delimited tables and a large tree of XML "lob"
content files:

* ``BILL_TBL.dat``              – one row per bill
* ``BILL_VERSION_TBL.dat``      – one row per bill version; the 15th field is a
                                  *relative path* to that version's XML
* ``BILL_HISTORY_TBL.dat``      – the action history ("08/12/25 Referred to ...")
* ``BILL_SUMMARY_VOTE_TBL.dat`` – vote tallies (ayes/noes/abstain)
* ``BILL_DETAIL_VOTE_TBL.dat``  – how each legislator voted
* ``BILL_VERSION_AUTHORS_TBL.dat``, ``BILL_ANALYSIS_TBL.dat``, ``BILL_MOTION_TBL.dat``,
  ``LEGISLATOR_TBL.dat``, ``LOCATION_CODE_TBL.dat``, ``COMMITTEE_HEARING_TBL.dat``
* ``CODES_TBL.dat``, ``LAW_TOC_TBL.dat``, ``LAW_TOC_SECTIONS_TBL.dat``,
  ``LAW_SECTION_TBL.dat``   – the statutory codes (content in ``*_*.lob`` files)

Fields are tab separated and optionally wrapped in backticks. Column orders below
were taken from the Legislature's own ``pubinfo_load`` SQL scripts (see
``docs/SOURCES.md``); unknown or extra columns are preserved rather than dropped,
so a schema change upstream degrades to a warning instead of a crash.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator
from xml.etree import ElementTree as ET

from .util import clean_text, get_logger

__all__ = [
    "DAT_SCHEMAS",
    "read_dat",
    "iter_law_sections",
    "iter_bill_versions",
    "parse_bill_xml",
    "xml_to_text",
    "open_bulk",
]

LOG = get_logger()

#: Column order for each table, as published in the Legislature's load scripts.
#: ``@var1`` marks the field that holds a path to an XML content file.
DAT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "BILL_TBL.dat": (
        "bill_id", "session_year", "session_num", "measure_type", "measure_num",
        "measure_state", "chapter_year", "chapter_type", "chapter_session_num",
        "chapter_num", "latest_bill_version_id", "active_flg", "trans_uid",
        "trans_update", "current_location", "current_secondary_loc", "current_house",
        "current_status", "days_31st_in_print",
    ),
    "BILL_VERSION_TBL.dat": (
        "bill_version_id", "bill_id", "version_num", "action_date", "action",
        "request_num", "subject", "vote_required", "appropriation", "fiscal_committee",
        "local_program", "substantive_changes", "urgency", "taxlevy", "xml_path",
        "active_flg", "trans_uid", "trans_update",
    ),
    "BILL_HISTORY_TBL.dat": (
        "bill_id", "bill_history_id", "action_date", "action", "trans_uid",
        "trans_update", "action_sequence", "action_code", "action_status",
        "primary_location", "secondary_location", "ternary_location", "end_status",
    ),
    "BILL_DETAIL_VOTE_TBL.dat": (
        "bill_id", "location_code", "legislator_name", "vote_date_time",
        "vote_date_seq", "vote_code", "motion_id", "trans_uid", "trans_update",
        "member_order", "session_date", "speaker",
    ),
    "BILL_SUMMARY_VOTE_TBL.dat": (
        "bill_id", "location_code", "vote_date_time", "vote_date_seq", "motion_id",
        "ayes", "noes", "abstain", "vote_result", "trans_uid", "trans_update",
        "file_item_num", "file_location", "display_lines", "session_date",
    ),
    "BILL_VERSION_AUTHORS_TBL.dat": (
        "bill_version_id", "type", "house", "name", "contribution",
        "committee_members", "active_flg", "trans_uid", "trans_update",
        "primary_author_flg",
    ),
    "BILL_ANALYSIS_TBL.dat": (
        "analysis_id", "bill_id", "house", "analysis_type", "committee_code",
        "committee_name", "amendment_author", "analysis_date", "amendment_date",
        "page_num", "xml_path", "released_floor", "active_flg", "trans_uid",
        "trans_update",
    ),
    "BILL_MOTION_TBL.dat": ("motion_id", "motion_text", "trans_uid", "trans_update"),
    "LEGISLATOR_TBL.dat": (
        "district", "session_year", "legislator_name", "house_type", "author_name",
        "first_name", "last_name", "middle_initial", "name_suffix", "name_title",
        "web_name_title", "party", "active_flg", "trans_uid", "trans_update",
        "active_legislator",
    ),
    "LOCATION_CODE_TBL.dat": (
        "session_year", "location_code", "location_type", "consent_calendar_code",
        "description", "long_description", "active_flg", "trans_uid", "trans_update",
        "inactive_file_flg",
    ),
    "COMMITTEE_HEARING_TBL.dat": (
        "committee_code", "hearing_date", "hearing_time", "location_code",
        "session_num", "session_year", "bill_id", "trans_uid", "trans_update",
    ),
    "VETO_MESSAGE_TBL.dat": ("bill_id", "veto_date", "xml_path", "trans_uid", "trans_update"),
    "DAILY_FILE_TBL.dat": (
        "bill_id", "location_code", "consent_calendar_code", "file_location",
        "publication_date", "floor_manager", "trans_uid", "trans_update_date",
        "session_num", "status",
    ),
    "CODES_TBL.dat": ("code", "title"),
    "LAW_TOC_TBL.dat": (
        "law_code", "division", "title", "part", "chapter", "article", "heading",
        "active_flg", "trans_uid", "trans_update", "node_sequence", "node_level",
        "node_position", "node_treepath", "contains_law_sections", "history_note",
        "op_statues", "op_chapter", "op_section",
    ),
    "LAW_TOC_SECTIONS_TBL.dat": (
        "id", "law_code", "node_treepath", "section_num", "section_order", "title",
        "op_statues", "op_chapter", "op_section", "trans_uid", "trans_update",
        "law_section_version_id", "seq_num",
    ),
    "LAW_SECTION_TBL.dat": (
        "id", "law_code", "section_num", "op_statues", "op_chapter", "op_section",
        "effective_date", "law_section_version_id", "division", "title", "part",
        "chapter", "article", "history", "xml_path", "active_flg", "trans_uid",
        "trans_update",
    ),
}


def _strip_quotes(field: str) -> str:
    if len(field) >= 2 and field.startswith("`") and field.endswith("`"):
        return field[1:-1]
    return field


def read_dat(path: str | os.PathLike[str], columns: Iterable[str] | None = None) -> Iterator[dict]:
    """Stream a backtick-quoted, tab-delimited ``.dat`` table as dictionaries.

    Rows with more fields than the schema are kept (extras land under
    ``_extra_0``, ``_extra_1``, ...) so an upstream column addition is visible
    instead of silently truncated.
    """
    path = Path(path)
    name = path.name
    schema = tuple(columns) if columns else DAT_SCHEMAS.get(name)
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if not line:
                continue
            fields = [_strip_quotes(f) for f in line.split("\t")]
            if schema is None:
                yield {f"col_{i}": value for i, value in enumerate(fields)}
                continue
            row = {column: (fields[i] if i < len(fields) else None) for i, column in enumerate(schema)}
            for extra in range(len(schema), len(fields)):
                row[f"_extra_{extra - len(schema)}"] = fields[extra]
            yield row


class BulkArchive:
    """Random access to the bulk ZIP plus its extracted tables."""

    def __init__(self, zip_path: str | os.PathLike[str], work_dir: str | os.PathLike[str] | None = None):
        self.zip_path = Path(zip_path)
        self.work_dir = Path(work_dir) if work_dir else self.zip_path.parent / "extracted"
        self._zf: zipfile.ZipFile | None = None

    @property
    def zf(self) -> zipfile.ZipFile:
        if self._zf is None:
            self._zf = zipfile.ZipFile(self.zip_path)
        return self._zf

    def close(self) -> None:
        if self._zf is not None:
            self._zf.close()
            self._zf = None

    def __enter__(self) -> "BulkArchive":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def names(self) -> list[str]:
        return self.zf.namelist()

    def table_path(self, table: str) -> Path:
        """Path to a ``.dat`` table, extracting it from the archive if needed."""
        target = self.work_dir / table
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.write_bytes(self.zf.read(table))
            except KeyError:
                # Some archives nest tables one level deep.
                candidates = [n for n in self.zf.namelist() if n.endswith(table)]
                if not candidates:
                    raise FileNotFoundError(f"{table} not found in {self.zip_path.name}")
                target.write_bytes(self.zf.read(candidates[0]))
        return target

    def read_xml(self, xml_path: str | None) -> bytes | None:
        """Read a content (``.lob``/``.xml``) file by its archive-relative path."""
        if not xml_path:
            return None
        path = xml_path.replace("\\", "/")
        try:
            return self.zf.read(path)
        except KeyError:
            # Fall back to the extracted directory, then to a basename search.
            local = self.work_dir / path
            if local.exists():
                return local.read_bytes()
            matches = [n for n in self.zf.namelist() if n.endswith(Path(path).name)]
            if matches:
                return self.zf.read(matches[0])
            LOG.warning("missing content file: %s", xml_path)
            return None


def open_bulk(zip_path: str | os.PathLike[str], work_dir: str | os.PathLike[str] | None = None) -> BulkArchive:
    """Open a bulk archive for reading."""
    return BulkArchive(zip_path, work_dir)


# --------------------------------------------------------------------------- XML


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element) -> str:
    return clean_text("".join(element.itertext()))


_TAG_RE = re.compile(r"<[^>]+>")


def xml_to_text(xml: str | bytes) -> str:
    """Convert CAML/XML statute or bill content to readable plain text.

    Uses ElementTree when the document is well formed and falls back to a
    tag-stripping regex otherwise — the upstream content files occasionally
    contain stray markup that a strict parser rejects.
    """
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        text = xml
        text = re.sub(r"<span\s+class=\"EnSpace\"\s*/?\s*>", " ", text)
        text = re.sub(r"</p>\s*<p>", "\n\n", text)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = _TAG_RE.sub("", text)
        return clean_text(_unescape(text))

    paragraphs: list[str] = []
    # Single pass, tracking whether we are inside a DigestText block so the
    # legislative counsel's summary is not duplicated into the bill text.
    stack: list[tuple[ET.Element, bool]] = [(root, False)]
    while stack:
        element, inside_digest = stack.pop()
        name = _local_name(element.tag)
        if name == "DigestText":
            inside_digest = True
        elif name == "p" and not inside_digest:
            text = _element_text(element)
            if text:
                paragraphs.append(text)
        for child in reversed(list(element)):  # pop() takes the first child first
            stack.append((child, inside_digest))

    if not paragraphs:
        return clean_text(_element_text(root))
    return clean_text("\n\n".join(paragraphs))


def _unescape(text: str) -> str:
    import html

    return html.unescape(text)


@dataclass
class BillXml:
    """Fields pulled out of a bill version's CAML document."""

    title: str = ""
    subject: str = ""
    digest: str = ""
    text: str = ""


def parse_bill_xml(data: bytes | str) -> BillXml:
    """Extract title, subject, legislative-counsel digest and full text."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    result = BillXml()
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        LOG.debug("bill XML is not well formed; using regex fallback")
        result.text = xml_to_text(data)
        return result

    for element in root.iter():
        name = _local_name(element.tag)
        if name == "Title" and not result.title:
            result.title = _element_text(element)
        elif name == "Subject" and not result.subject:
            result.subject = _element_text(element)
        elif name == "DigestText" and not result.digest:
            result.digest = clean_text("\n\n".join(_element_text(p) for p in element.iter() if _local_name(p.tag) == "p"))
    result.text = xml_to_text(data)
    return result


# ------------------------------------------------------------------- iterators


def iter_law_sections(archive: BulkArchive, *, active_only: bool = True) -> Iterator[dict]:
    """Yield law-section rows from ``LAW_SECTION_TBL.dat`` with their XML content."""
    path = archive.table_path("LAW_SECTION_TBL.dat")
    for row in read_dat(path):
        if active_only and (row.get("active_flg") or "Y").upper() != "Y":
            continue
        xml = archive.read_xml(row.get("xml_path"))
        row["content"] = xml_to_text(xml) if xml else ""
        row["char_count"] = len(row["content"])
        yield row


def iter_bill_versions(archive: BulkArchive, *, with_text: bool = True) -> Iterator[dict]:
    """Yield bill-version rows, optionally with the parsed XML bill text."""
    path = archive.table_path("BILL_VERSION_TBL.dat")
    for row in read_dat(path):
        if with_text:
            xml = archive.read_xml(row.get("xml_path"))
            if xml:
                parsed = parse_bill_xml(xml)
                row["title"] = parsed.title
                row["digest"] = parsed.digest
                row["text"] = parsed.text
                row.setdefault("subject", parsed.subject)
        row["char_count"] = len(row.get("text") or "")
        yield row
