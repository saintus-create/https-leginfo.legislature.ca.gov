"""Seed URLs and site-map helpers for selfhelp.courts.ca.gov.

This module provides two things:

1.  A curated list of seed URLs (topic landing pages and the most-linked
    subsidiary pages) that can be fetched even from a network-restricted
    environment where outbound TLS to selfhelp.courts.ca.gov is blocked by
    routing all page fetches through the platform's ``fetch_page`` tool.

2.  A ``fetch_direct`` helper used in environments that *can* reach the host
    directly, so the crawler can be run without the platform.
"""

from __future__ import annotations

from .config import SELFHELP_BASE_URL, TOPICS

__all__ = ["seed_urls", "topic_seed_urls", "index_pages", "fetch_direct"]

# Curated deep-links from the homepage's interactive pickers and topic indexes.
# These are the high-traffic entry points that self-represented litigants use
# most; they in turn link out to the step-by-step sub-pages.
_DEEP_LINKS: tuple[str, ...] = (
    # Service / "Served papers" picker forms
    "/served-papers",
    # Start-a-case / picker targets
    "/start-divorce-case",
    "/divorce-disclosures-info",
    "/divorce/finalize-divorce",
    "/divorce/property-debts",
    "/divorce/date-separation",
    "/divorce/trial",
    "/divorce/spousal-support",
    "/divorce/joint-petition",
    "/spousal-support/longterm",
    "/spousal-support/temporary",
    "/divorce-california/summary-dissolution/qualifications",
    "/start-restraining-order",
    "/DV-restraining-order",
    "/DV-restraining-order/prepare-court-date",
    "/DV-restraining-order/enforce-restraining-order",
    "/CH-restraining-order",
    "/CH-restraining-order/enforce-restraining-order",
    "/EA-restraining-order",
    "/elder-abuse",
    "/civil-harassment-restraining-order",
    "/workplace-violence-restraining-order",
    "/gun-violence-restraining-order",
    "/eviction-landlord",
    "/eviction-tenant",
    "/small-claims/before-you-start",
    "/small-claims/start-case",
    "/small-claims/trial",
    "/small-claims/after-trial",
    "/small-claims/ask-for-money/mediation",
    "/debt-lawsuits",
    "/debt-lawsuits/respond",
    "/debt-lawsuits/trial",
    "/debt-lawsuits/judgment",
    "/name-change/adult",
    "/name-change/child",
    "/gender-recognition",
    "/guardianship",
    "/conservatorship",
    "/guardianship/start",
    "/parentage",
    "/parentage/start",
    "/emancipation",
    "/stepparent-adoption",
    "/wills-estates-probate",
    "/helping-person-impairment-or-disability",
    "/juvenile-justice",
    "/clean-your-record",
    "/criminal-court",
    "/criminal-court/victim-rights",
    "/protective-orders",
    "/appeals/steps",
    "/appeals/resources",
    "/appeals/which-court",
    "/appeals/index",
    # Work on my case
    "/request-for-order",
    "/request-for-order/child-support",
    "/request-for-order/child-custody",
    "/request-for-order/spousal-support",
    "/request-for-order/domestic-violence",
    "/request-for-order/hearing/what-to-expect-at-hearing",
    "/discovery-civil",
    "/discovery-civil/request",
    "/discovery-civil/respond",
    "/discovery-family-law",
    "/subpoena",
    # Court services
    "/fee-waiver",
    "/fee-waiver/forms",
    "/find-court-form",
    "/court-basics",
    "/court-basics/find-fill-out-forms",
    "/court-basics/get-ready-court",
    "/tips-your-day-court",
    "/getting-legal-help",
    "/self-help-center",
    "/find-courthouse",
    "/interpreter",
    "/disability-access",
    "/remote-hearing",
    "/prepare-for-remote-hearing",
    "/jury-duty",
    "/service",
    "/service-personal-and-mail",
    "/service-how-to-find-someone",
    # Traffic
    "/traffic/ask-lower-fine",
    "/traffic/court-trial",
    "/traffic/trial-declaration",
    "/traffic/traffic-school",
    "/fix-it-ticket",
    "/traffic/scam-warning",
    "/traffic/pay-ticket",
    # Index pages
    "/divorce-index",
    "/small-claims-index",
    "/child-support-index",
    "/child-custody-and-parenting-time-index",
    "/name-change-case-map",
    "/eviction-index",
    "/criminal-court/index",
    "/traffic/index",
    # Misc top-level utility pages
    "/start-divorce-case",
    "/respond-divorce-papers-0",
    "/parentage/respond",
    "/make-decisions-finish-your-divorce",
    "/domestic-violence-child-custody",
    "/what-expect-restraining-order-hearing",
    "/safety-accommodations-during-mediation",
)


def topic_seed_urls() -> list[str]:
    return [t.url for t in TOPICS]


def index_pages() -> list[str]:
    return [
        f"{SELFHELP_BASE_URL}/",
        *topic_seed_urls(),
    ]


def seed_urls() -> list[str]:
    urls = [SELFHELP_BASE_URL + "/"]
    # Topic landing pages
    urls.extend(topic_seed_urls())
    # Deep links
    urls.extend(f"{SELFHELP_BASE_URL}{path}" for path in _DEEP_LINKS)
    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = u.rstrip("/") or "/"
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def fetch_direct(url: str, *, timeout: int = 30, retries: int = 3) -> bytes:
    """Fetch a page's raw HTML directly from selfhelp.courts.ca.gov.

    Only works in environments where outbound TLS to the host is permitted;
    otherwise raises a RuntimeError. Used by the command-line crawler when
    run outside the platform.
    """
    import ssl
    import urllib.request
    from urllib.error import URLError

    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "leginfo-selfhelp/1.0 (+public-domain corpus; see repo README)",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        except (URLError, TimeoutError, OSError, ssl.SSLError) as exc:
            last_err = exc
            import time as _t
            _t.sleep(2 * (attempt + 1))
    raise RuntimeError(f"direct fetch failed for {url}: {last_err}")
