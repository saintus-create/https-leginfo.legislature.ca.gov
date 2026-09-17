"""Static metadata about the California Courts Self-Help Guide (selfhelp.courts.ca.gov).

The site is published by the Judicial Branch of California and is the court
system's plain-language portal for self-represented litigants. Unlike leginfo,
it is procedural and instructional — what form to file, how to serve papers,
what to expect at a hearing — rather than statutory text.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Topic",
    "TOPICS",
    "TOPICS_BY_SLUG",
    "SELFHELP_BASE_URL",
    "SOURCE_NAME",
]

SELFHELP_BASE_URL = "https://selfhelp.courts.ca.gov"
SOURCE_NAME = "California Courts Self-Help Guide"


@dataclass(frozen=True)
class Topic:
    """A top-level topic landing page on the Self-Help Guide."""

    slug: str       # URL stem, e.g. "divorce"
    title: str      # human title, e.g. "Divorce"
    path: str       # site path, e.g. "/divorce"
    description: str

    @property
    def url(self) -> str:
        return f"{SELFHELP_BASE_URL}{self.path}"


# Curated from the site's topic picker on the homepage. Order matches the
# "Get information about a legal topic" menu.
TOPICS: tuple[Topic, ...] = (
    Topic("appeals", "Appeals", "/appeals",
          "Start or work on an appeal in the California Court of Appeal."),
    Topic("care-act", "CARE Act", "/care-act",
          "Community Assistance, Recovery, and Empowerment (CARE) Act proceedings."),
    Topic("criminal-law", "Criminal law", "/criminal-law",
          "Criminal court, cleaning your record, victims' rights, protective orders."),
    Topic("divorce", "Divorce", "/divorce",
          "Divorce, legal separation, and summary dissolution in California."),
    Topic("domestic-violence", "Domestic violence", "/domestic-violence",
          "Domestic Violence Restraining Orders and related custody/support issues."),
    Topic("eviction", "Eviction", "/eviction",
          "Eviction cases (unlawful detainer) for landlords and tenants."),
    Topic("families-children", "Families and children", "/child-custody",
          "Child custody, visitation (parenting time), and parenting plans."),
    Topic("gender-change", "Gender change", "/gender-recognition",
          "Court-ordered name change and gender recognition."),
    Topic("disability", "Help for someone with a disability", "/helping-person-impairment-or-disability",
          "Conservatorships, limited conservatorships, and supported decision-making."),
    Topic("immigration", "Immigration", "/immigration",
          "Immigration issues that intersect with California courts."),
    Topic("money-debt", "Money and debt", "/debt-lawsuits",
          "Debt collection lawsuits, levies, and judgments."),
    Topic("name-change", "Name change", "/name-change",
          "Adult and child name changes, updating identity documents."),
    Topic("restraining-orders", "Restraining orders", "/restraining-orders",
          "Domestic violence, civil harassment, elder abuse, workplace, and gun-violence restraining orders."),
    Topic("small-claims", "Small claims", "/small-claims",
          "Small claims court: starting a case, trial, collecting a judgment."),
    Topic("suing-someone", "Suing someone (civil lawsuit)", "/suing-someone",
          "Civil lawsuits in superior court."),
    Topic("traffic", "Traffic tickets", "/traffic",
          "Paying, fixing, or contesting a traffic ticket; traffic school; fine reduction."),
    Topic("wills-estates", "Wills, estates, and probate", "/wills-estates-probate",
          "Wills, advance care planning, conservatorships, and probate."),
    Topic("guardianship", "Guardianship", "/guardianship",
          "Guardianship of a child's person or estate."),
    Topic("conservatorship", "Conservatorship", "/conservatorship-index",
          "General and limited conservatorships."),
    Topic("parentage", "Parentage (paternity)", "/parentage",
          "Establishing or contesting legal parentage."),
    Topic("emancipation", "Emancipation", "/emancipation",
          "Emancipation of a minor."),
    Topic("adoption", "Stepparent adoption", "/stepparent-adoption",
          "Stepparent adoption proceedings."),
    Topic("court-basics", "Court basics", "/court-basics",
          "Preparing for court, getting an interpreter, fee waivers, finding forms."),
    Topic("self-help-center", "Self-help centers", "/self-help-center",
          "Finding your local court self-help center."),
    Topic("fee-waiver", "Fee waivers", "/fee-waiver",
          "Asking the court to waive filing fees."),
    Topic("interpreter", "Court interpreters", "/interpreter",
          "Requesting an interpreter for your court hearing."),
    Topic("remote-hearing", "Remote hearings", "/remote-hearing",
          "Preparing for a remote (video/phone) court hearing."),
    Topic("find-form", "Find court forms", "/find-court-form",
          "Search and download Judicial Council forms."),
    Topic("find-courthouse", "Find a courthouse", "/find-courthouse",
          "Find court locations, hours, and contact information."),
    Topic("disability-access", "Disability access", "/disability-access",
          "Requesting disability accommodations in court."),
    Topic("getting-legal-help", "Get a lawyer", "/getting-legal-help",
          "Free and low-cost legal help options."),
    Topic("jury-duty", "Jury duty", "/jury-duty",
          "What to expect when called for jury service."),
)

TOPICS_BY_SLUG: dict[str, Topic] = {t.slug: t for t in TOPICS}
