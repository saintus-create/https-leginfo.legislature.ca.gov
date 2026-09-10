"""Static metadata about California codes, sessions and upstream data sources.

Everything in here is either published by the California Legislative Counsel
Bureau (code names/abbreviations, session years, bulk-data URLs) or derived from
the nightly mirror repository we fall back to when the official bulk feed is
unreachable.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Code",
    "CODES",
    "CODES_BY_ABBR",
    "BULK_BASE_URL",
    "MIRROR_REPO",
    "MIRROR_TARBALL_URL",
    "session_start_year",
    "bulk_zip_url",
    "mirror_code_filename",
]


@dataclass(frozen=True)
class Code:
    """A California statutory code (29 codes plus the Constitution)."""

    abbr: str  # LegInfo code abbreviation, e.g. "GOV"
    name: str  # Human name, e.g. "Government Code"
    order: int  # Display order used by LegInfo's code picker

    @property
    def slug(self) -> str:
        """Stem used by the plain-text mirror, e.g. "CA Code - Government Code"."""
        return f"CA Code - {self.name}"


# Order and abbreviations follow LegInfo's own "Quick Code Search" picker.
CODES: tuple[Code, ...] = (
    Code("CONS", "California Constitution", 0),
    Code("BPC", "Business and Professions Code", 1),
    Code("CIV", "Civil Code", 2),
    Code("CCP", "Code of Civil Procedure", 3),
    Code("COM", "Commercial Code", 4),
    Code("CORP", "Corporations Code", 5),
    Code("EDC", "Education Code", 6),
    Code("ELEC", "Elections Code", 7),
    Code("EVID", "Evidence Code", 8),
    Code("FAM", "Family Code", 9),
    Code("FIN", "Financial Code", 10),
    Code("FGC", "Fish and Game Code", 11),
    Code("FAC", "Food and Agricultural Code", 12),
    Code("GOV", "Government Code", 13),
    Code("HNC", "Harbors and Navigation Code", 14),
    Code("HSC", "Health and Safety Code", 15),
    Code("INS", "Insurance Code", 16),
    Code("LAB", "Labor Code", 17),
    Code("MVC", "Military and Veterans Code", 18),
    Code("PEN", "Penal Code", 19),
    Code("PROB", "Probate Code", 20),
    Code("PCC", "Public Contract Code", 21),
    Code("PRC", "Public Resources Code", 22),
    Code("PUC", "Public Utilities Code", 23),
    Code("RTC", "Revenue and Taxation Code", 24),
    Code("SHC", "Streets and Highways Code", 25),
    Code("UIC", "Unemployment Insurance Code", 26),
    Code("VEH", "Vehicle Code", 27),
    Code("WAT", "Water Code", 28),
    Code("WIC", "Welfare and Institutions Code", 29),
)

CODES_BY_ABBR: dict[str, Code] = {c.abbr: c for c in CODES}

#: Official bulk download site (tab-delimited tables + CAML XML content files).
BULK_BASE_URL = "https://downloads.leginfo.legislature.ca.gov"

#: Nightly GitHub mirror of the law text extracted from the official bulk feed.
#: Used as a fallback source when downloads.leginfo is unreachable.
MIRROR_REPO = "johnakelly-yahoo-com/california-codes"
MIRROR_TARBALL_URL = f"https://codeload.github.com/{MIRROR_REPO}/tar.gz/refs/heads/main"


def session_start_year(year: int | None = None) -> int:
    """Return the first year of the legislative session containing ``year``.

    California sessions are two-year cycles that start in odd-numbered years,
    so 2025 and 2026 both belong to the 2025-2026 session.
    """
    from datetime import datetime

    y = year if year is not None else datetime.now().year
    return y if y % 2 == 1 else y - 1


def bulk_zip_url(session_year: int | None = None) -> str:
    """URL of the official bulk-data ZIP for a session (e.g. ``pubinfo_2025.zip``)."""
    return f"{BULK_BASE_URL}/pubinfo_{session_start_year(session_year)}.zip"


def mirror_code_filename(abbr: str) -> str:
    """Plain-text filename for ``abbr`` inside the mirror repository."""
    return f"{CODES_BY_ABBR[abbr].slug}.txt"
