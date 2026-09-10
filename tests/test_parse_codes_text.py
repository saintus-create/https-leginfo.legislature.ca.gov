"""Parser tests for the plain-text statutory codes.

The fixtures are small synthetic documents shaped exactly like the upstream
mirror's output (banner, structural headings, section labels, history trailers),
including the two cases that broke naive parsing: subdivision text beginning
with "(a)" and the Constitution's "SEC. 6½." labels.
"""

from __future__ import annotations

import pytest

from leginfo.parse_codes_text import parse_code_file


SAMPLE = """
======================================================================
  Evidence Code
  State of California
======================================================================

Source: Official California Legislative Information
        https://downloads.leginfo.legislature.ca.gov/
Last Updated by State of California: November 27, 2025



======================================================================

DIVISION 2. WORDS AND PHRASES DEFINED [100. - 260.]

105.

"Action" includes a civil action and a criminal action.

(History: Enacted by Stats. 1965, Ch. 299.)
-------------------------------------------

ARTICLE 2. PRESUMPTIONS
[600. - 668.]

607.

(a) When a person is in possession of a thing, the possession is presumed
to be lawful.

(b) This section shall become operative on January 1, 2027, and applies to
actions filed after that date.

(History: Amended by Stats. 2020, Ch. 12, Sec. 3. (AB 34) Effective
January 1, 2021.)
-------------------------------------------

ARTICLE 3. REPEALED PROVISIONS

700.

(Repealed by Stats. 1988, Ch. 1259, Sec. 1.)
-------------------------------------------
"""


@pytest.fixture()
def parsed(tmp_path):
    path = tmp_path / "CA Code - Evidence Code.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    return parse_code_file(path, "EVID")


def test_sections_and_breadcrumbs(parsed):
    sections = {s["section"]: s for s in parsed.sections}
    assert set(sections) == {"105", "607", "700"}

    action = sections["105"]
    assert action["text"] == '"Action" includes a civil action and a criminal action.'
    assert action["history"] == "(History: Enacted by Stats. 1965, Ch. 299.)"
    assert action["division"] == "2. WORDS AND PHRASES DEFINED"

    presumptions = sections["607"]
    assert presumptions["article"] == "2. PRESUMPTIONS"
    assert presumptions["path"] == "2. WORDS AND PHRASES DEFINED > 2. PRESUMPTIONS"


def test_subdivision_text_is_not_history(parsed):
    """Body text starting with "(a)" must stay in the text field."""
    section = next(s for s in parsed.sections if s["section"] == "607")
    assert section["text"].startswith("(a) When a person is in possession")
    assert "shall become operative on January 1, 2027" in section["text"]
    assert not section["text"].startswith("(History")
    assert section["history"].startswith("(History: Amended by Stats. 2020")
    assert "operative" not in section["history"].lower()


def test_repealed_section(parsed):
    section = next(s for s in parsed.sections if s["section"] == "700")
    assert section["repealed"] is True
    assert section["text"] == ""


def test_headings_are_captured_with_ranges(parsed):
    headings = [(h["kind"], h["number"], h["title"]) for h in parsed.headings]
    assert ("division", "2", "WORDS AND PHRASES DEFINED") in headings
    assert ("article", "2", "PRESUMPTIONS") in headings
    division = next(h for h in parsed.headings if h["kind"] == "division")
    assert (division["range_start"], division["range_end"]) == ("100", "260")


def test_wrapped_heading_title_is_rejoined(parsed):
    article = next(h for h in parsed.headings if h["kind"] == "article" and h["number"] == "2")
    assert article["title"] == "PRESUMPTIONS"


def test_updated_date_and_citations(parsed):
    assert parsed.updated == "November 27, 2025"
    section = next(s for s in parsed.sections if s["section"] == "105")
    assert section["citation"] == "EVID § 105"
    assert section["uid"] == "EVID:105"


CONSTITUTION_SAMPLE = """
ARTICLE I DECLARATION OF RIGHTS [SECTION 1. - SEC. 32.]

SECTION 1.

All people are by nature free and independent and have inalienable rights.

(History: Sec. 1 added Nov. 5, 1974, by Proposition 7. Resolution Chapter 90, 1974.)
-------------------------------------------

SEC. 6½.

Nothing in this constitution contained shall forbid the formation of districts.

(History: Sec. 6½ added Nov. 7, 1922, by Prop. 26. Res.Ch. 46, 1921.)
-------------------------------------------

ARTICLE XIII B GOVERNMENT SPENDING LIMITATION [SEC. 1. - SEC. 15.]

SEC. 1.

The total annual appropriations subject to limitation shall not exceed.

(History: Sec. 1 added Nov. 6, 1979, by Prop. 4. Res.Ch. 4, 1979.)
-------------------------------------------
"""


def test_constitution_labels_and_lettered_articles(tmp_path):
    path = tmp_path / "CA Code - California Constitution.txt"
    path.write_text(CONSTITUTION_SAMPLE, encoding="utf-8")
    result = parse_code_file(path, "CONS")

    sections = {(s["uid"], s["section"]) for s in result.sections}
    assert ("CONS:I-1", "1") in sections          # "SECTION 1." label
    assert ("CONS:I-6½", "6½") in sections        # fractional section number
    assert ("CONS:XIIIB-1", "1") in sections      # lettered article keeps its letter

    spending = next(s for s in result.sections if s["uid"] == "CONS:XIIIB-1")
    assert spending["citation"] == "Cal. Const. art. XIII B, § 1"

    first = next(s for s in result.sections if s["uid"] == "CONS:I-1")
    assert first["citation"] == "Cal. Const. art. I, § 1"


def test_sections_are_sorted_numerically(tmp_path):
    text = "".join(f"{n}.\n\nText of section {n}.\n\n(History: Enacted 1872.)\n{'-' * 43}\n\n" for n in (2, 10, 1.5, 1))
    path = tmp_path / "CA Code - Civil Code.txt"
    path.write_text(text, encoding="utf-8")
    result = parse_code_file(path, "CIV")
    assert [s["section"] for s in result.sections] == ["1", "1.5", "2", "10"]


def test_section_label_without_trailing_period(tmp_path):
    """Some codes print the number bare ("1568.099"), without a full stop."""
    path = tmp_path / "CA Code - Health and Safety Code.txt"
    path.write_text(
        "1568.099\n\nThe acceptance or storage of a resident's firearm.\n\n"
        "(History: Added by Stats. 2019, Ch. 840, Sec. 3.)\n" + "-" * 43 + "\n\n",
        encoding="utf-8",
    )
    sections = parse_code_file(path, "HSC").sections
    assert [s["section"] for s in sections] == ["1568.099"]
    assert sections[0]["text"].startswith("The acceptance or storage")


def test_six_digit_section_numbers(tmp_path):
    path = tmp_path / "CA Code - Public Utilities Code.txt"
    path.write_text(
        "100000.\n\nThis part shall be known as the Transit District Act.\n\n"
        "(History: Amended by Stats. 1999, Ch. 724, Sec. 7.)\n" + "-" * 43 + "\n\n",
        encoding="utf-8",
    )
    sections = parse_code_file(path, "PUC").sections
    assert [s["section"] for s in sections] == ["100000"]


def test_bracketed_heading_with_range(tmp_path):
    """The Health and Safety Code wraps headings and ranges in brackets."""
    path = tmp_path / "CA Code - Health and Safety Code.txt"
    path.write_text(
        "[PART 1.7. HEALTH FACILITIES DISCLOSURE ACT] [440.10. - 440.50.]\n\n"
        "440.10.\n\nDisclosure is required.\n\n(History: Added by Stats. 2001, Ch. 1.)\n" + "-" * 43 + "\n\n",
        encoding="utf-8",
    )
    result = parse_code_file(path, "HSC")
    part = next(h for h in result.headings if h["kind"] == "part")
    assert part["title"] == "HEALTH FACILITIES DISCLOSURE ACT"
    assert (part["range_start"], part["range_end"]) == ("440.10", "440.50")
    assert result.sections[0]["part"] == "1.7. HEALTH FACILITIES DISCLOSURE ACT"


def test_heading_inside_a_section_belongs_to_that_section(tmp_path):
    """Interstate compacts restated inside a section carry their own headings.

    Those headings are part of the statutory text (GOV 66801 is the Tahoe
    Regional Planning Compact), so the text after them must not be dropped.
    """
    path = tmp_path / "CA Code - Government Code.txt"
    path.write_text(
        "66801.\n\n"
        "The provisions of this interstate compact are set out below.\n\n"
        "TAHOE REGIONAL PLANNING COMPACT\n\n"
        "ARTICLE I.FINDINGS AND DECLARATIONS OF POLICY\n\n"
        "(a) It is found and declared that:\n\n"
        "(History: Added by Stats. 1967, Ch. 1589.)\n" + "-" * 43 + "\n\n"
        "66802.\n\nThe next section.\n\n(History: Added by Stats. 1967, Ch. 1589.)\n" + "-" * 43 + "\n\n",
        encoding="utf-8",
    )
    result = parse_code_file(path, "GOV")
    compact = next(s for s in result.sections if s["section"] == "66801")
    assert "TAHOE REGIONAL PLANNING COMPACT" in compact["text"]
    assert "(a) It is found and declared that:" in compact["text"]
    assert result.stats.unclassified_paragraphs == 0
    # A heading that *does* introduce a new section is still structural.
    assert [s["section"] for s in result.sections] == ["66801", "66802"]
