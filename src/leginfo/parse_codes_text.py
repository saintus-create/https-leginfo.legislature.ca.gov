"""Turn the plain-text rendition of a California code into structured records.

The upstream mirror publishes one ``.txt`` file per code that looks like this::

    ======================================================================
      Evidence Code
      State of California
    ======================================================================

    DIVISION 2. WORDS AND PHRASES DEFINED [100. - 260.]

    105.

    "Action" includes a civil action and a criminal action.

    (History: Enacted by Stats. 1965, Ch. 299.)
    -------------------------------------------

``parse_code_file`` walks that document and emits two record types:

* ``section``  – one numbered section of law, with its breadcrumb, body text,
  legislative history and citation.
* ``heading``  – a structural node (division / part / title / chapter / article).

Two details make this more than a line splitter:

* Heading nesting differs per code (the Education Code starts at Title, the
  Evidence Code at Division), so nesting depth is learned from the order the
  heading kinds first appear in each file rather than hard-coded.
* The legislative-history trailer is distinguished from body text that merely
  starts with a parenthesis -- ``(a) A person is guilty of...`` is text, while
  ``(History: Enacted by Stats. 1965, Ch. 299.)`` is history.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .util import clean_text, is_blank

__all__ = [
    "ParseStats",
    "ParseResult",
    "parse_code_file",
    "parse_code_directory",
]

#: Structural heading kinds that wrap statutory sections, deepest last.
HEADING_KINDS = (
    "TITLE",
    "DIVISION",
    "PART",
    "SUBPART",
    "CHAPTER",
    "SUBCHAPTER",
    "ARTICLE",
    "SUBDIVISION",
)

_HEADING_RE = re.compile(r"^(?P<kind>" + "|".join(HEADING_KINDS) + r")\s+(?P<rest>\S.*)$")

#: Trailer such as "[1. - 12.]" that the mirror appends to heading lines.
_RANGE_RE = re.compile(r"\s*\[(?P<start>[^\]\-]+?)\s*[-–]\s*(?P<end>[^\]]+?)\]\s*$")

#: A codified section label, e.g. "105." or "1000.10." or "11362.7a.".
#: A minority of codes print the number with no trailing full stop, so it is
#: optional here (the label is only recognised when it is alone on its line).
_SECTION_RE = re.compile(r"^(?P<num>\d{1,7}[A-Za-z]?(?:\.\d{1,7}[A-Za-z]?){0,3})\.?$")

#: Constitution labels: "SEC. 7.5.", "SECTION 1.", and the odd "SEC. 6½.".
_CONST_SECTION_RE = re.compile(
    r"^(?:SEC\.?|SECTION)\s*(?P<num>[0-9]{1,3}(?:[½¼¾]|\.[0-9]{1,3})?[A-Za-z]?)\.?$",
    re.IGNORECASE,
)

#: Separator rules the mirror emits between blocks.
_SEPARATOR_RE = re.compile(r"^[-=]{10,}$")

#: Every legislative-history trailer in the source corpus opens with "(History:".
#: (Verified across all 30 code files: 162,432 trailers, no exceptions.) Matching on
#: that literal keeps body text like "(a) This section shall become operative..."
#: out of the history field.
_HISTORY_START_RE = re.compile(
    r"^\((?:History|Repealed|Expired|Added|Amended|Enacted|Re-enacted|Renumbered|"
    r"Operative|Effective|Source|Note)\b",
    re.IGNORECASE,
)
_REPEALED_RE = re.compile(r"\b(Repealed|Expired)\b", re.IGNORECASE)


@dataclass
class ParseStats:
    """Counters used to sanity-check a parse run."""

    source_file: str = ""
    lines: int = 0
    sections: int = 0
    headings: int = 0
    blocks: int = 0
    unclassified_paragraphs: int = 0
    sections_with_history: int = 0
    repealed_sections: int = 0
    empty_sections: int = 0
    duplicate_sections: int = 0
    uid_collisions: int = 0
    multi_section_blocks: int = 0
    samples: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "samples"}


@dataclass
class ParseResult:
    """Structured output for one code file."""

    code: str
    source_file: str
    sections: list[dict] = field(default_factory=list)
    headings: list[dict] = field(default_factory=list)
    stats: ParseStats = field(default_factory=ParseStats)
    updated: str | None = None


def _split_blocks(lines: list[str]) -> Iterator[list[str]]:
    """Yield the runs of lines between the mirror's ``-----`` / ``=====`` rules."""
    current: list[str] = []
    for line in lines:
        if _SEPARATOR_RE.match(line.strip()):
            if current:
                yield current
            current = []
            continue
        current.append(line.rstrip("\n"))
    if current:
        yield current


def _paragraphs(block: list[str]) -> list[list[str]]:
    """Split a block into paragraphs (runs of non-blank lines)."""
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in block:
        if is_blank(line):
            if current:
                paragraphs.append(current)
            current = []
            continue
        current.append(line.strip())
    if current:
        paragraphs.append(current)
    return paragraphs


def _parse_heading(line: str) -> dict | None:
    """Parse a structural heading line.

    Handles both layouts the upstream text uses::

        DIVISION 2. WORDS AND PHRASES DEFINED [100. - 260.]
        [PART 1.7. HEALTH FACILITIES DISCLOSURE ACT] [440.10. - 440.50.]
    """
    text = line.strip()
    trailing_bracket = None
    if text.startswith("["):
        text = text[1:].strip()
        close = text.find("]")
        if close != -1:
            trailing_bracket = text[close + 1 :].strip()
            text = text[:close].strip()

    range_start = range_end = None
    range_match = re.match(r"^\[(?P<start>[^\]\-]+?)\s*[-–]\s*(?P<end>[^\]]+?)\]\.?$", trailing_bracket or "")
    if range_match:
        range_start = range_match.group("start").strip().rstrip(".")
        range_end = range_match.group("end").strip().rstrip(".")
    else:
        range_match = _RANGE_RE.search(text)
        if range_match:
            start, end = range_match.group("start"), range_match.group("end")
            range_start = re.sub(r"^(SEC\.?|SECTION)\s*", "", start, flags=re.IGNORECASE).strip().rstrip(".")
            range_end = re.sub(r"^(SEC\.?|SECTION)\s*", "", end, flags=re.IGNORECASE).strip().rstrip(".")
            text = text[: range_match.start()].strip()

    match = _HEADING_RE.match(text)
    if not match:
        return None
    kind = match.group("kind").lower()
    rest = match.group("rest").strip()

    parts = rest.split(None, 1)
    number = parts[0].rstrip(".") if parts else ""
    title = parts[1].strip() if len(parts) > 1 else ""

    # The Constitution numbers its lettered articles "ARTICLE XIII A", "XIII B", …
    # The letter belongs to the article number, not to its title.
    lettered = re.match(r"^([A-Z])\s+(.*)$", title)
    if kind == "article" and lettered:
        number = f"{number} {lettered.group(1)}"
        title = lettered.group(2).strip()

    return {
        "kind": kind,
        "number": number,
        "title": title,
        "range_start": range_start,
        "range_end": range_end,
    }


def _parse_section_label(line: str) -> str | None:
    """Parse a standalone section label, returning the section number or None."""
    stripped = line.strip()
    match = _CONST_SECTION_RE.match(stripped)
    if match:
        return match.group("num")
    match = _SECTION_RE.match(stripped)
    return match.group("num") if match else None


def _looks_like_history_start(paragraph: list[str]) -> bool:
    """True when a paragraph opens a legislative-history trailer."""
    return bool(_HISTORY_START_RE.match(paragraph[0]))


def _continues_history(paragraph: list[str]) -> bool:
    """True when a paragraph is a continuation of a history trailer."""
    first = paragraph[0]
    if first.startswith("("):
        return True
    return bool(re.match(r"^(Other Source|Source|Note|Formerly)\b", first, re.IGNORECASE))


def _split_body_history(paragraphs: list[list[str]]) -> tuple[str, str]:
    """Split a section's body paragraphs into (law text, legislative history).

    The history trailer is always last, so the first candidate paragraph whose
    successors all look like history wins. This keeps ``(a) ...`` subdivision
    text out of the history field.
    """
    history_at = None
    for index, paragraph in enumerate(paragraphs):
        if not _looks_like_history_start(paragraph):
            continue
        if all(_continues_history(later) for later in paragraphs[index + 1 :]):
            history_at = index
            break
    if history_at is None:
        text_paragraphs, history_paragraphs = paragraphs, []
    else:
        text_paragraphs, history_paragraphs = paragraphs[:history_at], paragraphs[history_at:]
    text = clean_text("\n\n".join(" ".join(p) for p in text_paragraphs))
    history = clean_text(" ".join(" ".join(p) for p in history_paragraphs))
    return text, history


def _section_sort_key(section: str) -> tuple:
    """Sort sections numerically ("97" before "97.5" before "98"), not lexically."""
    parts: list[tuple[float, str]] = []
    for chunk in section.split("."):
        match = re.match(r"^(\d+)(.*)$", chunk)
        if match:
            parts.append((int(match.group(1)), match.group(2)))
        else:
            parts.append((0.0, chunk))
    return tuple(parts)


def _fmt(node: dict | None) -> str | None:
    """Render a heading node as "3. Homicide"."""
    if not node:
        return None
    number = node.get("number", "")
    title = node.get("title", "")
    if number and title:
        return f"{number}. {title}"
    return number or title or None


def _build_path(nodes: list[dict]) -> str:
    return " > ".join(p for p in (_fmt(n) for n in nodes) if p)


def citation_for(code: str, section: str, article: str | None = None) -> str:
    """Human citation, e.g. "Gov. Code § 6250" or "Cal. Const. art. I, § 1"."""
    if code == "CONS":
        if article:
            return f"Cal. Const. art. {article}, § {section}"
        return f"Cal. Const. § {section}"
    return f"{code} § {section}"


def _find_content_start(lines: list[str]) -> int:
    """Index of the first structural heading or section label (skips the banner)."""
    for index, line in enumerate(lines):
        stripped = line.strip()
        if _parse_heading(stripped) is not None:  # also matches "[PART 1.7. …]"
            return index
        if _SECTION_RE.match(stripped) or _CONST_SECTION_RE.match(stripped):
            return index
    return 0


def parse_code_file(path: str | os.PathLike[str], code: str) -> ParseResult:
    """Parse one ``CA Code - <Name>.txt`` file into sections and headings."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    result = ParseResult(code=code, source_file=path.name)
    stats = result.stats
    stats.source_file = path.name
    stats.lines = len(lines)

    for line in lines[:80]:
        if "Last Updated by State of California" in line:
            result.updated = line.split(":", 1)[-1].strip()
            break

    context: dict[str, dict] = {}  # kind -> heading record
    kind_rank: dict[str, int] = {}  # kind -> nesting depth, learned per file
    section_ordinal = 0
    heading_ordinal = 0
    seen_sections: set[tuple[str, str]] = set()  # (section, text digest) dedupe
    seen_uids: set[str] = set()
    nonlocal_section_ordinal = [section_ordinal]  # mutated by flush_section()

    for block in _split_blocks(lines[_find_content_start(lines) :]):
        stats.blocks += 1
        paragraphs = _paragraphs(block)
        index = 0
        section: dict | None = None
        body: list[list[str]] = []

        def flush_section() -> None:
            assert section is not None
            text, history = _split_body_history(body)
            # "(History: Repealed and added by ...)" is *current* law, so only
            # sections with no operative text at all are flagged as repealed.
            repealed = not text and bool(_REPEALED_RE.search(history))
            dedupe_key = (section["section"], hashlib.md5("".join(text.split()).encode("utf-8")).hexdigest())
            if dedupe_key in seen_sections:
                # The upstream text repeats a few sections verbatim (they hang off
                # more than one table-of-contents node). Keep the first copy.
                stats.duplicate_sections += 1
                return
            seen_sections.add(dedupe_key)
            article = context.get("article", {}).get("number")
            article_key = article.replace(" ", "") if article else None
            uid = f"{code}:{article_key}-{section['section']}" if article_key else f"{code}:{section['section']}"
            if uid in seen_uids:
                # Same number published twice with genuinely different text (two bills
                # creating the same section number). Keep both under distinct ids.
                stats.uid_collisions += 1
                suffix = 2
                while f"{uid}#{suffix}" in seen_uids:
                    suffix += 1
                uid = f"{uid}#{suffix}"
            seen_uids.add(uid)

            section.update(
                {
                    "uid": uid,
                    "citation": citation_for(code, section["section"], article),
                    "text": text,
                    "history": history,
                    "repealed": repealed,
                    "division": _fmt(context.get("division")),
                    "part": _fmt(context.get("part")),
                    "title": _fmt(context.get("title")),
                    "chapter": _fmt(context.get("chapter")),
                    "article": _fmt(context.get("article")),
                    "path": _build_path(list(context.values())),
                    "char_count": len(text),
                }
            )
            section["ordinal"] = nonlocal_section_ordinal[0]
            result.sections.append(section)
            nonlocal_section_ordinal[0] += 1
            stats.sections += 1
            if history:
                stats.sections_with_history += 1
            if repealed:
                stats.repealed_sections += 1
            if not text:
                stats.empty_sections += 1

        while index < len(paragraphs):
            paragraph = paragraphs[index]

            if section is None:
                heading = _parse_heading(" ".join(paragraph)) if len(paragraph) > 1 else _parse_heading(paragraph[0])
                if heading is None:
                    heading = _parse_heading(paragraph[0])
                if heading is not None:
                    kind = heading["kind"]
                    if kind not in kind_rank:
                        kind_rank[kind] = len(kind_rank)
                    rank = kind_rank[kind]
                    for existing_kind in list(context):
                        if kind_rank[existing_kind] >= rank:
                            del context[existing_kind]
                    heading["code"] = code
                    heading["ordinal"] = heading_ordinal
                    heading["path"] = _build_path([*context.values(), heading])
                    context[kind] = heading
                    heading_ordinal += 1
                    result.headings.append(heading)
                    stats.headings += 1
                    index += 1
                    continue

                label = _parse_section_label(paragraph[0]) if len(paragraph) == 1 else None
                if label is not None:
                    section = {"kind": "section", "code": code, "section": label}
                    index += 1
                    continue

                stats.unclassified_paragraphs += 1
                stats.samples.setdefault("unclassified", []).append(" ".join(paragraph)[:200])
                index += 1
                continue

            # Inside a section: everything up to the end of the block is body text.
            # Blocks hold at most one section, so bare numbers, embedded compact
            # headings and wrapped subdivisions all belong to the section.
            body.append(paragraph)
            index += 1

        if section is not None:
            flush_section()

    result.sections.sort(key=lambda s: _section_sort_key(s["section"]))
    for position, section in enumerate(result.sections):
        section["ordinal"] = position
    return result


def parse_code_directory(directory: str | os.PathLike[str], codes: Iterable) -> Iterator[ParseResult]:
    """Parse every ``CA Code - <Name>.txt`` file present in ``directory``."""
    directory = Path(directory)
    for code in codes:
        path = directory / f"{code.slug}.txt"
        if not path.exists():
            continue
        yield parse_code_file(path, code.abbr)
