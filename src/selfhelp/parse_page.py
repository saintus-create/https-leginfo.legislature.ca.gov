"""Parse a Self-Help Guide page (as markdown-ish text from fetch_page) into a record.

The platform's fetch_page tool renders pages as markdown-like text. This parser
extracts a clean title, body, internal links, glossary terms, and form
references from that text.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlsplit, urljoin

from .config import SELFHELP_BASE_URL

__all__ = ["PageRecord", "parse_page", "slug_from_url", "is_selfhelp_url", "SELFHELP_URL_RE"]

SELFHELP_URL_RE = re.compile(r"https?://selfhelp\.courts\.ca\.gov(/[^\s)\]\"<>]*)?", re.I)
_FORM_RE = re.compile(r"\b([A-Z]{2,4}[-‐–—]?\d{1,4}(?:\s*[\./-]\d+[A-Z]?)?)\b")
_GLOSSARY_TERM_RE = re.compile(r"\*{4}([^*]+)\*{4}")  # platform bolds glossary terms with ****term****
_INTERNAL_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://selfhelp\.courts\.ca\.gov/[^)]+)\)")
_EXTERNAL_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_SKIP_BOX_RE = re.compile(
    r"(Was this helpful\?|reCAPTCHA|Enter your email|Enter your mobile number|"
    r"Select your mobile carrier|We'll only use this email|We'll only use this mobile number|"
    r"Ten digit mobile number|Leave this field blank|did this information help|"
    r"Any Additional Feedback|Email \(optional\)|Recaptcha requires verification|"
    r"I'm not a robot|This question is for testing|Great! Anything you can share|"
    r"Sorry to hear that|PRINTEMAILTEXT|success alert banner:|Look for a \"Chat Now\"|"
    r"What would make this more helpful)",
    re.I,
)


@dataclass
class PageRecord:
    """Structured record for one selfhelp.courts.ca.gov page."""

    url: str
    path: str
    slug: str
    title: str
    text: str
    headings: list[dict] = field(default_factory=list)
    internal_links: list[dict] = field(default_factory=list)
    external_links: list[dict] = field(default_factory=list)
    forms_referenced: list[str] = field(default_factory=list)
    glossary_terms: list[str] = field(default_factory=list)
    sha256: str = ""
    fetched_at: str = ""
    lang: str = "en"
    status: int = 200

    def to_dict(self) -> dict:
        return {
            "kind": "selfhelp-guide-page",
            "url": self.url,
            "path": self.path,
            "slug": self.slug,
            "title": self.title,
            "text": self.text,
            "headings": self.headings,
            "internal_links": self.internal_links,
            "external_links": self.external_links,
            "forms_referenced": self.forms_referenced,
            "glossary_terms": self.glossary_terms,
            "sha256": self.sha256,
            "fetched_at": self.fetched_at,
            "lang": self.lang,
            "status": self.status,
            "char_count": len(self.text),
        }


def slug_from_url(url: str) -> str:
    p = urlsplit(url).path.strip("/") or "__home__"
    return re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-") or "__home__"


def is_selfhelp_url(url: str) -> bool:
    try:
        p = urlsplit(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    return p.netloc.lower().lstrip("www.") == "selfhelp.courts.ca.gov"


def _strip_footer_chaff(text: str) -> str:
    """Remove the 'Was this helpful?' feedback box and other boilerplate that
    fetch_page carries from the shared page chrome."""
    # Cut at the "Was this helpful?" marker if present.
    cut = _SKIP_BOX_RE.search(text)
    if cut:
        text = text[: cut.start()]
    return text


def _clean_markdownish(text: str) -> str:
    """Collapse whitespace, drop image-only lines, normalize."""
    # Drop "Skip to main content" jump
    text = re.sub(r"^\[Skip to main content\]\([^)]+\)\s*", "", text)
    # Drop the banner image (Judicial Branch logo) — first few paragraphs of chrome
    text = re.sub(
        r"^\[!\[Judicial Branch of California branding[^\n]*\n\(https://www\.courts\.ca\.gov/\s+\"[^\"]*\"\)\)\s*",
        "",
        text,
        flags=re.M,
    )
    # Drop generic image lines that are just chrome/alt
    text = re.sub(r"^!\[[^\]]*\]\([^)]+\)\s*$", "", text, flags=re.M)
    # Normalize whitespace
    text = _WS_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def _extract_headings(clean_body: str) -> list[dict]:
    headings = []
    for m in _MD_HEADING_RE.finditer(clean_body):
        level = len(m.group(1))
        title = m.group(2).strip()
        # Strip markdown formatting characters inside heading titles
        title = re.sub(r"[*_`#]+", "", title).strip()
        if title:
            headings.append({"level": level, "title": title})
    return headings


def _normalize_form_number(raw: str) -> str:
    s = raw.upper().replace("‐", "-").replace("–", "-").replace("—", "-").replace(" ", "")
    s = re.sub(r"\.+", ".", s)
    return s


def parse_page(
    url: str,
    markdown_text: str,
    *,
    title: str = "",
    fetched_at: str = "",
    status: int = 200,
    lang: str = "en",
) -> PageRecord:
    """Parse a page from the fetch_page markdown output."""
    raw = markdown_text or ""
    body = _strip_footer_chaff(raw)
    body = _clean_markdownish(body)

    # Title: use explicit title if given, else first H1, else first non-empty line.
    page_title = title.strip()
    h1 = re.match(r"^#\s+(.+)$", body, re.M)
    if not page_title and h1:
        page_title = h1.group(1).strip()
    if not page_title:
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("["):
                page_title = line[:120]
                break
    page_title = re.sub(r"[*_`]+", "", page_title).strip()

    # Strip the trailing site suffix that the <title> carries.
    page_title = re.sub(
        r"\s*\|?\s*California Courts\s*(\|\s*Self Help Guide\s*)?$",
        "",
        page_title,
        flags=re.I,
    ).strip()

    headings = _extract_headings(body)

    # Links
    internal: list[dict] = []
    external: list[dict] = []
    seen_internal: set[str] = set()
    for m in _INTERNAL_LINK_RE.finditer(body):
        label, href = m.group(1).strip(), m.group(2).strip()
        href = href.split("?", 1)[0].rstrip("/") or "/"
        if href not in seen_internal:
            internal.append({"label": _trim_md(label), "url": href})
            seen_internal.add(href)
    for m in _EXTERNAL_LINK_RE.finditer(body):
        label, href = m.group(1).strip(), m.group(2).strip()
        if is_selfhelp_url(href):
            continue  # already captured by internal (the regex is split by host)
        if "safelinks.protection.outlook.com" in href or href.startswith("mailto:") or href.startswith("javascript:"):
            href = _unwind_safelink(href)
            if not href or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
        if href.startswith("#"):
            continue
        external.append({"label": _trim_md(label), "url": href})

    # Form numbers (e.g. FL-300, DV-100, SC-100)
    forms = sorted({_normalize_form_number(m.group(1)) for m in _FORM_RE.finditer(body)})

    # Glossary terms (bolded with **** in the markdown)
    glossary = sorted({m.group(1).strip().strip("*") for m in _GLOSSARY_TERM_RE.finditer(body)})

    # Remove markdown punctuation from final text for a cleaner plain-text body,
    # but keep line structure so section boundaries survive.
    plain = body
    # Strip links but keep label:  [text](url) -> text
    plain = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", plain)
    # Strip images:  ![alt](url) -> ''
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", plain)
    # Strip heading markers
    plain = re.sub(r"^#{1,6}\s+", "", plain, flags=re.M)
    # Collapse bold/italic markers
    plain = re.sub(r"[*_]{2,}", "", plain)
    # Drop escaped backslashes
    plain = plain.replace("\\", "")
    plain = _WS_RE.sub(" ", plain)
    plain = re.sub(r" *\n *", "\n", plain)
    plain = _MULTI_NL_RE.sub("\n\n", plain)
    plain = plain.strip()

    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()

    return PageRecord(
        url=url.rstrip("/") or (SELFHELP_BASE_URL + "/"),
        path=urlsplit(url).path or "/",
        slug=slug_from_url(url),
        title=page_title,
        text=plain,
        headings=headings,
        internal_links=internal,
        external_links=external,
        forms_referenced=forms,
        glossary_terms=glossary,
        sha256=digest,
        fetched_at=fetched_at,
        lang=lang,
        status=status,
    )


def _trim_md(label: str) -> str:
    s = re.sub(r"\\[\n\r]+", " ", label)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[*_`]+", "", s)
    return s.strip()


def _unwind_safelink(url: str) -> str:
    """Microsoft safelinks wraps external URLs; unwrap to the real target."""
    m = re.search(r"[?&]url=([^&]+)", url)
    if not m:
        return url
    from urllib.parse import unquote
    return unquote(m.group(1))
