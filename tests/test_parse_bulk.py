"""Tests for the official bulk-archive parser.

The archive is ~764 MB, so these tests build a *synthetic* ZIP with the same
layout (flat ``.dat`` tables + XML content files referenced by relative path)
and the same quoting rules as the real one.
"""

from __future__ import annotations

import zipfile

import pytest

from leginfo.parse_bulk import (
    BulkArchive,
    open_bulk,
    parse_bill_xml,
    read_dat,
)

BILL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<caml:Bill xmlns:caml="http://www.leginfo.ca.gov/CAML" xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <caml:BillHeader>
    <caml:BillId>202520260AB1</caml:BillId>
  </caml:BillHeader>
  <caml:Title>An act relating to widgets.</caml:Title>
  <caml:Subject>Widgets: certification.</caml:Subject>
  <caml:Content>
    <caml:DigestText>
      <xhtml:p>Existing law requires widget safety.</xhtml:p>
      <xhtml:p>This bill would require certification.</xhtml:p>
    </caml:DigestText>
    <xhtml:p>THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:</xhtml:p>
    <xhtml:p>SECTION 1. Section 1234 is added to the Widget Code.</xhtml:p>
  </caml:Content>
</caml:Bill>
"""

BILL_TBL = (
    "202520260AB1\t2025\t2026\tAB\t1\tI\t\t\t\t\t202520260AB199\tY\t"
    "user\t2025-12-01 00:00:00\tASM. FLOOR\t\tA\tIn Committee\tN\n"
    "202520260SB2\t2025\t2026\tSB\t2\tI\t\t\t\t\t202520260SB299\tY\t"
    "user\t2025-12-02 00:00:00\tSEN. FLOOR\t\tS\tIn Committee\tN\n"
)

BILL_VERSION_TBL = (
    "202520260AB199\t202520260AB1\t1\t2025-12-01 00:00:00\tIntroduced\t\t"
    "Widgets: certification.\tMAJ\tNo\tNo\tNo\tNo\tNo\tNo\t"
    "202520260AB199.xml\tY\tuser\t2025-12-01 00:00:00\n"
)


@pytest.fixture()
def archive(tmp_path):
    zip_path = tmp_path / "pubinfo_2025.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("BILL_TBL.dat", BILL_TBL)
        zf.writestr("BILL_VERSION_TBL.dat", BILL_VERSION_TBL)
        zf.writestr("202520260AB199.xml", BILL_XML)
    return open_bulk(zip_path, work_dir=tmp_path / "work")


def test_read_dat_unwraps_backticks(tmp_path):
    path = tmp_path / "CODES_TBL.dat"
    path.write_text("`GOV`\t`Government Code`\n`PEN`\t`Penal Code`\n", encoding="utf-8")
    rows = list(read_dat(path))
    assert rows == [
        {"code": "GOV", "title": "Government Code"},
        {"code": "PEN", "title": "Penal Code"},
    ]


def test_read_dat_keeps_unexpected_extra_columns(tmp_path):
    path = tmp_path / "CODES_TBL.dat"
    path.write_text("GOV\tGovernment Code\tSURPRISE\n", encoding="utf-8")
    row = next(read_dat(path))
    assert row["_extra_0"] == "SURPRISE"


def test_bill_rows(archive):
    rows = list(read_dat(archive.table_path("BILL_TBL.dat")))
    assert rows[0]["bill_id"] == "202520260AB1"
    assert rows[0]["measure_type"] == "AB"
    assert rows[0]["measure_num"] == "1"
    assert rows[0]["current_location"] == "ASM. FLOOR"


def test_bill_version_rows_and_text(archive):
    rows = list(archive.__class__ and read_dat(archive.table_path("BILL_VERSION_TBL.dat")))
    row = rows[0]
    assert row["bill_version_id"] == "202520260AB199"
    assert row["xml_path"] == "202520260AB199.xml"
    assert row["subject"] == "Widgets: certification."

    xml = archive.read_xml(row["xml_path"])
    parsed = parse_bill_xml(xml)
    assert parsed.title == "An act relating to widgets."
    assert parsed.subject == "Widgets: certification."
    assert "Existing law requires widget safety." in parsed.digest
    assert parsed.text.startswith("THE PEOPLE OF THE STATE OF CALIFORNIA")
    # The digest must not be duplicated into the bill text.
    assert "Existing law requires widget safety." not in parsed.text
    # Paragraph order is document order.
    assert parsed.text.index("THE PEOPLE") < parsed.text.index("SECTION 1.")


def test_missing_content_file_returns_none(archive):
    assert archive.read_xml("does-not-exist.xml") is None
    assert archive.read_xml("") is None


def test_iter_bill_versions_joins_text(archive):
    from leginfo.parse_bulk import iter_bill_versions

    versions = list(iter_bill_versions(archive))
    assert len(versions) == 1
    assert versions[0]["char_count"] > 0
    assert "SECTION 1." in versions[0]["text"]


def test_malformed_xml_falls_back_to_tag_stripping():
    broken = b"<caml:Bill><caml:Content><xhtml:p>Unclosed paragraph"
    parsed = parse_bill_xml(broken)
    assert "Unclosed paragraph" in parsed.text


def test_archive_context_manager_closes(tmp_path):
    with open_bulk(tmp_path / "missing.zip") as archive:  # noqa: SIM117 - construction is lazy
        pass
    assert isinstance(archive, BulkArchive)
