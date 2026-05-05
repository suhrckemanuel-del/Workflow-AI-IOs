"""
WORKFLOW: VC Lead Finder
------------------------
INPUT:   Project context + target VC profile
PROCESS: Exa finds public VC candidates, optional Hunter enriches public emails,
         Claude ranks and structures the leads.
OUTPUT:  CSV-ready lead list saved to knowledge_base/outreach/
"""

import concurrent.futures
import csv
import html
import io
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))
from core.engine import call_claude_structured, save_output


ASIF_DEFAULT_CONTEXT = """ASIF Ventures project context:
AMSA is supporting ASIF Ventures with a portfolio assessment and fund performance review.
The project focuses on portfolio company assessment, fund performance metrics, pattern recognition, and benchmarking.
Relevant outreach target: VC funds or student-run investment funds that can share benchmarking practices, portfolio monitoring approaches, reporting templates, KPI methods, or lessons from early-stage fund management.
Final deliverables include a dashboard, clean CSV master database, summary presentation, and methodology documentation."""

CSV_COLUMNS = [
    "priority_rank",
    "fund_name",
    "website",
    "geography",
    "fund_type",
    "fit_score",
    "route_quality",
    "contact_name",
    "contact_role",
    "contact_confidence",
    "linkedin_profile_url",
    "email",
    "email_status",
    "contact_method",
    "contact_url",
    "evidence_url",
    "evidence_summary",
    "outreach_angle",
    "suggested_subject",
    "first_action",
    "validation_status",
    "validation_flags",
    "is_student_run",
]

APOLLO_CSV_COLUMNS = [
    "apollo_status",
    "apollo_person_name",
    "apollo_title",
    "apollo_email",
    "apollo_email_confidence",
    "apollo_person_linkedin",
]

DROPCONTACT_CSV_COLUMNS = [
    "dropcontact_attempted",
    "dropcontact_response_code",
]

SECONDARY_SOURCE_TERMS = (
    "blog",
    "database",
    "directory",
    "newsletter",
    "report",
    "research",
    "media",
    "list of",
    "ranked",
    "ranking",
    "profiles",
)

CONTACT_PATHS = (
    "/team",
    "/people",
    "/about",
    "/about-us",
    "/contact",
    "/contact-us",
    "/get-in-touch",
    "/funds",
    "/portfolio",
)
CONTACT_ROUTE_PATHS = ("/contact", "/contact-us", "/get-in-touch")
WEBSITE_ROUTE_PATHS = ("/team", "/people", "/about-us", "/about", "/funds", "/portfolio")
EMAIL_PATTERN = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
ROLE_LABELS = (
    ("managing partner", "Partner"),
    ("investment manager", "Investment"),
    ("investment director", "Investment"),
    ("fund director", "Fund Team"),
    ("partner", "Partner"),
    ("principal", "Investment"),
    ("associate", "Investment"),
    ("portfolio", "Portfolio"),
    ("platform", "Platform"),
    ("operations", "Operations"),
    ("finance", "Finance"),
    ("board", "Fund Team"),
)
GENERIC_CONTACT_NAMES = {"fund team", "fund board", "investment team", "fund manager", "team"}
CONTACT_CONFIDENCE_VALUES = {"high", "medium", "low"}
MAX_GEOGRAPHY_BUCKET = 3
STUDENT_FUND_TERMS = (
    "student-run",
    "student run",
    "student-led",
    "student led",
    "student vc",
    "student venture",
    "student investment",
    "student fund",
    "campus",
    "university",
    "academic",
    "inter-university",
    "university-linked",
)
PROFESSIONAL_FUND_TERMS = (
    "micro vc",
    "micro-fund",
    "seed vc",
    "early-stage vc",
    "early stage vc",
    "early-stage venture",
    "early stage venture",
    "fund-of-funds",
    "professional",
)
CANONICAL_WEBSITE_OVERRIDES = {
    "dutchstudentinvestmentfund.nl": "https://www.dsif.nl/",
}
GENERIC_EMAIL_PREFIXES = {"hello", "hi", "info", "contact", "team", "office", "admin", "general", "enquiries", "support"}
PERSON_FIRST_NAME_HINTS = {
    # English / International
    "alex", "alexander", "alexandre", "anna", "ben", "benjamin",
    "chris", "christian", "david", "elena", "eva", "felix", "florian",
    "james", "jessica", "johan", "john", "julia", "juri", "kilian",
    "laura", "lena", "lisa", "marc", "marie", "mark", "martin",
    "max", "maxime", "michael", "nicolas", "ophelia", "paul", "philipp",
    "ross", "sara", "sarah", "simon", "sophie", "thomas", "tom",
    # French
    "adrien", "antoine", "camille", "charles", "charlotte", "clement",
    "emilie", "etienne", "florent", "francois", "gabriel", "guillaume",
    "hugo", "juliette", "lea", "louis", "lucas", "manon", "margot",
    "mathieu", "nicolas", "romain", "theo", "thibault", "victor",
    # Dutch / Belgian
    "bart", "esther", "floor", "joris", "joren", "kees", "lars",
    "lennart", "luuk", "maarten", "noor", "pieter", "roel", "ruben",
    "sander", "stijn", "tim", "timo", "wouter", "yorick",
    # German / Austrian / Swiss
    "christoph", "dominik", "fabian", "hannes", "jan", "jonas",
    "julian", "kilian", "lukas", "moritz", "niklas", "pascal",
    "patrick", "stefan", "stephan", "tobias",
    # Nordic (Danish / Swedish / Norwegian / Finnish)
    "anders", "astrid", "bjorn", "einar", "erik", "gunnar", "hannah",
    "jakob", "jesper", "johanna", "kaj", "lasse", "maja", "mats",
    "mikael", "nils", "oscar", "sigrid", "sven", "tuomas",
    # Southern European
    "alba", "adriana", "carlos", "elena", "fernando", "ines",
    "jorge", "luca", "marco", "marta", "matteo", "pablo", "sergio",
}
_FETCH_CACHE: dict[str, tuple[str, str]] = {}
_HUNTER_CACHE: dict[str, tuple[list[str], str]] = {}
_DROPCONTACT_CACHE: dict[str, tuple[str, str]] = {}
APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
DROPCONTACT_ENRICH_URL = "https://api.dropcontact.com/v1/enrich/all"
APOLLO_PEOPLE_MATCH_URL = "https://api.apollo.io/api/v1/people/match"
APOLLO_TARGET_TITLES = (
    "portfolio",
    "portfolio operations",
    "platform",
    "operations",
    "finance",
    "investment",
    "investor",
    "partner",
    "principal",
    "associate",
    "founder",
    "managing director",
)
APOLLO_TARGET_SENIORITIES = ("owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager", "senior")
MEDIA_DOMAINS = (
    "bebeez.",
    "tech.eu",
    "startbase.",
    "visible.vc",
    "eu-startups.",
    "goldeneggcheck.",
    "privateequityinternational.",
    "euroquity.",
    "openvc.",
    "lusha.",
    "bouncewatch.",
    "substack.",
    "linkedin.",
)

CURATED_VC_TARGETS = [
    {
        "fund_name": "Dutch Student Investment Fund (DSIF)",
        "website": "https://www.dsif.nl/",
        "geography": "Netherlands",
        "fund_type": "Student-run VC",
        "relevance_score": 92,
        "likely_contact_person": "Fund Board",
        "contact_person_confidence": "Medium",
        "contact_role": "Portfolio",
        "outreach_angle": "DSIF is a close student-run VC peer for benchmarking portfolio monitoring and fund KPI practices.",
        "thesis_fit_reason": "European student-run VC with a structured investment process and direct peer relevance to ASIF.",
    },
    {
        "fund_name": "The Hague Student Investment Fund (HSiF)",
        "website": "https://hsif.nl/",
        "geography": "Netherlands",
        "fund_type": "Student-run VC",
        "relevance_score": 87,
        "likely_contact_person": "Fund Board",
        "contact_person_confidence": "Medium",
        "contact_role": "Fund Team",
        "outreach_angle": "HSiF is a fellow Dutch student fund with useful peer practices for ASIF benchmarking.",
        "thesis_fit_reason": "Dutch student-run fund with board and coaching structures relevant to early-stage fund reporting.",
    },
    {
        "fund_name": "S2S Ventures",
        "website": "https://s2s.vc/",
        "geography": "Switzerland",
        "fund_type": "Student-run VC",
        "relevance_score": 86,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Fund Team",
        "outreach_angle": "S2S can share how a student-led Swiss VC manages early-stage portfolio reporting.",
        "thesis_fit_reason": "Student-led Swiss VC with structured deal flow and investor reporting relevance.",
    },
    {
        "fund_name": "Amsterdam Academic Ventures (AAV)",
        "website": "https://aav.nl/",
        "geography": "Netherlands",
        "fund_type": "Academic seed fund operator",
        "relevance_score": 45,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Portfolio",
        "outreach_angle": "AAV operates multiple academic funds and can benchmark multi-fund reporting practices.",
        "thesis_fit_reason": "Amsterdam academic fund operator with multiple early-stage vehicles and formal portfolio processes.",
    },
    {
        "fund_name": "Utrecht Holdings Seed Fund (UHSF)",
        "website": "https://uhsf.nl/",
        "geography": "Netherlands",
        "fund_type": "University-linked seed fund",
        "relevance_score": 83,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Portfolio",
        "outreach_angle": "UHSF has a public contact route and structured academic seed-fund review process for KPI benchmarking.",
        "thesis_fit_reason": "University-linked seed fund with a clear contact route and structured investment review process.",
    },
    {
        "fund_name": "UNIIQ",
        "website": "https://uniiq.nl/en/",
        "geography": "Netherlands",
        "fund_type": "Early-stage university-linked seed fund",
        "relevance_score": 77,
        "likely_contact_person": "Investment Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Investment",
        "outreach_angle": "UNIIQ's formal guidance model can inform ASIF's portfolio monitoring and reporting templates.",
        "thesis_fit_reason": "Professionally managed Dutch early-phase fund with relevant portfolio guidance and KPI practices.",
    },
    {
        "fund_name": "Qbic Fund",
        "website": "https://qbic.be/",
        "geography": "Belgium",
        "fund_type": "Inter-university seed VC",
        "relevance_score": 75,
        "likely_contact_person": "Investment Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Investment",
        "outreach_angle": "Qbic's multi-fund history gives ASIF a mature benchmark for fund reporting and portfolio tracking.",
        "thesis_fit_reason": "Belgian inter-university seed fund with mature multi-fund portfolio monitoring experience.",
    },
    {
        "fund_name": "Tiny Supercomputer Investment Company (TSIC)",
        "website": "https://tinysupercomputerinvestmentcompany.com/",
        "geography": "Europe",
        "fund_type": "Micro VC",
        "relevance_score": 43,
        "likely_contact_person": "Operations or Fundraising Partner",
        "contact_person_confidence": "Medium",
        "contact_role": "Operations",
        "outreach_angle": "TSIC's large micro-VC portfolio makes it useful for benchmarking scalable portfolio monitoring.",
        "thesis_fit_reason": "European micro VC with a large portfolio and likely mature fund KPI practices.",
    },
    {
        "fund_name": "Graduate Ventures",
        "website": "http://www.graduate.nl/",
        "geography": "Netherlands",
        "fund_type": "Early-stage VC",
        "relevance_score": 71,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Fund Team",
        "outreach_angle": "Graduate Ventures is a local Dutch early-stage peer for portfolio monitoring comparisons.",
        "thesis_fit_reason": "Dutch early-stage investor in the same ecosystem with relevant support and reporting practices.",
    },
    {
        "fund_name": "Nordhavn",
        "website": "https://nordhavnfund.com/",
        "geography": "DACH and Nordics",
        "fund_type": "Student-led investment fund",
        "relevance_score": 80,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Investment",
        "outreach_angle": "Nordhavn's student-led investment research process is relevant for ASIF's benchmarking scope.",
        "thesis_fit_reason": "Student-led fund with investment research and portfolio practice relevance across DACH and Nordics.",
    },
    {
        "fund_name": "G. Ventures",
        "website": "https://www.gventures.co/",
        "geography": "France",
        "fund_type": "Student-run VC",
        "relevance_score": 74,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Medium",
        "contact_role": "Fund Team",
        "outreach_angle": "G. Ventures is a French student VC peer for comparing early-stage fund reporting approaches.",
        "thesis_fit_reason": "French student-run VC with direct peer relevance to ASIF's student fund benchmarking.",
    },
    {
        "fund_name": "Campus Fund",
        "website": "https://campus-fund.com/",
        "geography": "France",
        "fund_type": "Student-run VC",
        "relevance_score": 79,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Campus Fund is a French student-run fund peer for comparing portfolio monitoring and student-fund reporting practices.",
        "thesis_fit_reason": "French student entrepreneur investment fund with formal fund structure and direct relevance to ASIF's student-fund benchmarking.",
    },
    {
        "fund_name": "Oxford Seed Fund",
        "website": "https://www.sbs.ox.ac.uk/research/centres-and-initiatives/oxford-said-entrepreneurship-centre/oxford-seed-fund",
        "geography": "United Kingdom",
        "fund_type": "Student-run seed fund",
        "relevance_score": 78,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Oxford Seed Fund is a student-run seed fund peer for comparing investment committee process, portfolio follow-up, and reporting templates.",
        "thesis_fit_reason": "University student-run seed fund with a formal investment process and strong fit for ASIF benchmarking.",
    },
    {
        "fund_name": "The Creator Fund",
        "website": "https://www.thecreatorfund.com/",
        "geography": "United Kingdom",
        "fund_type": "University-focused VC",
        "relevance_score": 73,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "The Creator Fund's university-focused model is useful for ASIF benchmarking against student and academic venture ecosystems.",
        "thesis_fit_reason": "UK university-focused investor with relevant academic-founder sourcing and portfolio support practices.",
    },
    {
        "fund_name": "Seedcamp",
        "website": "https://seedcamp.com/",
        "geography": "United Kingdom / Europe",
        "fund_type": "Seed VC",
        "relevance_score": 60,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Seedcamp can provide a mature European seed-fund benchmark for portfolio support and KPI tracking.",
        "thesis_fit_reason": "Established European seed fund with mature portfolio support and reporting practices.",
    },
    {
        "fund_name": "Point Nine",
        "website": "https://www.pointnine.com/",
        "geography": "Germany",
        "fund_type": "Early-stage VC",
        "relevance_score": 59,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Point Nine offers a DACH benchmark for early-stage fund portfolio support and reporting.",
        "thesis_fit_reason": "Berlin-based early-stage VC with established portfolio operations practices relevant to benchmarking.",
    },
    {
        "fund_name": "Cherry Ventures",
        "website": "https://www.cherry.vc/",
        "geography": "Germany",
        "fund_type": "Early-stage VC",
        "relevance_score": 50,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Cherry Ventures gives ASIF a DACH early-stage fund benchmark for founder support and portfolio tracking.",
        "thesis_fit_reason": "Established Berlin-based early-stage VC with portfolio support relevance.",
    },
    {
        "fund_name": "byFounders",
        "website": "https://byfounders.vc/",
        "geography": "Nordics / Baltics",
        "fund_type": "Early-stage VC",
        "relevance_score": 49,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "byFounders provides a Nordic/Baltic benchmark for founder-led portfolio support and fund reporting.",
        "thesis_fit_reason": "Nordic/Baltic early-stage VC with relevant portfolio support and benchmarking practices.",
    },
    {
        "fund_name": "Inventure",
        "website": "https://www.inventure.vc/",
        "geography": "Nordics",
        "fund_type": "Early-stage VC",
        "relevance_score": 70,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Inventure can provide a Nordic benchmark for early-stage portfolio monitoring and fund KPI practices.",
        "thesis_fit_reason": "Nordic early-stage VC with established fund and portfolio support experience.",
    },
    {
        "fund_name": "Isomer Capital",
        "website": "https://isomercapital.com/",
        "geography": "United Kingdom / Europe",
        "fund_type": "VC fund-of-funds",
        "relevance_score": 67,
        "likely_contact_person": "Fund Team",
        "contact_person_confidence": "Low",
        "contact_role": "Fund Team",
        "outreach_angle": "Isomer Capital has fund-of-funds visibility that can benchmark fund KPI and reporting practices across Europe.",
        "thesis_fit_reason": "European VC fund-of-funds with broad visibility into fund performance and portfolio reporting practices.",
    },
]


class LeadCandidate(BaseModel):
    priority_rank: int = 0
    fund_name: str
    website: str = ""
    geography: str = ""
    fund_type: str = ""
    relevance_score: int = Field(ge=0, le=100)
    fit_score: int = 0
    thesis_fit_reason: str
    likely_contact_person: str = ""
    contact_name: str = ""
    contact_person_confidence: str = ""
    contact_confidence: str = ""
    contact_person_source_url: str = ""
    contact_role: str = ""
    apollo_status: str = "not_configured"
    apollo_person_name: str = ""
    apollo_title: str = ""
    apollo_email: str = ""
    apollo_email_confidence: str = ""
    apollo_person_linkedin: str = ""
    public_email: str = ""
    email_confidence: str = ""
    hunter_attempted: bool = False
    hunter_response_code: str = "not_called"
    dropcontact_attempted: bool = False
    dropcontact_response_code: str = "not_called"
    email_source_snippet: str = ""
    email: str = ""
    email_status: str = ""
    contact_method: str = ""
    linkedin_profile_url: str = ""
    linkedin_or_contact_url: str = ""
    contact_url: str = ""
    source_url: str = ""
    evidence_url: str = ""
    evidence_summary: str = ""
    fetch_status: str = "not_attempted"
    fetch_verified: bool = False
    validation_note: str = ""
    route_quality: str = ""
    suggested_subject: str = ""
    first_action: str = ""
    validation_status: str = ""
    validation_flags: str = ""
    outreach_angle: str
    confidence: str
    is_student_run: bool = True


class LeadList(BaseModel):
    search_strategy: str
    leads: list[LeadCandidate]
    missing_data_notes: str
    validation_notes: list[str] = []
    secondary_sources: list[dict] = []


def _exa_search(query: str, num_results: int = 10) -> list[dict]:
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return [{"title": "Exa not configured", "url": "", "text": "Add EXA_API_KEY to .env to enable live research."}]

    try:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": num_results,
                "contents": {"text": {"maxCharacters": 1000}},
            },
            timeout=15,
        )
        response.raise_for_status()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "text": r.get("text", ""),
            }
            for r in response.json().get("results", [])
        ]
    except Exception as e:
        return [{"title": "Search error", "url": "", "text": str(e)}]


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().removeprefix("www.")
        return host
    except Exception:
        return ""


def _canonical_website(url: str) -> str:
    domain = _domain_from_url(url)
    return CANONICAL_WEBSITE_OVERRIDES.get(domain, url)


def _is_linkedin_url(url: str) -> bool:
    return "linkedin.com" in (url or "").lower()


def _is_official_page(url: str, lead: LeadCandidate) -> bool:
    if not url or _is_linkedin_url(url):
        return False
    lead_domain = _domain_from_url(lead.website)
    url_domain = _domain_from_url(url)
    return bool(url_domain and (not lead_domain or url_domain == lead_domain or url_domain.endswith(f".{lead_domain}")))


def _is_secondary_source(source: dict) -> bool:
    url = (source.get("url") or "").lower()
    text = f"{source.get('title', '')} {source.get('text', '')}".lower()
    if _is_linkedin_url(url):
        return True
    if any(domain in url for domain in MEDIA_DOMAINS):
        return True
    path = urlparse(url).path.lower() if url else ""
    if re.search(r"/20\d{2}/|/news/|/blog/|/directory/|/investor-lists/", path):
        return True
    return any(term in f"{url} {text}" for term in SECONDARY_SOURCE_TERMS)


def _is_official_domain_url(url: str) -> bool:
    if not url or _is_linkedin_url(url):
        return False
    return not _is_secondary_source({"url": url})


def _fetch_page_text(url: str) -> tuple[str, str]:
    if not url or _is_linkedin_url(url):
        return "", "not_attempted"
    normalized_url = url if "://" in url else f"https://{url}"
    if normalized_url in _FETCH_CACHE:
        return _FETCH_CACHE[normalized_url]
    try:
        candidate_urls = [normalized_url]
        parsed = urlparse(normalized_url)
        if parsed.path and not parsed.path.endswith("/") and "." not in parsed.path.rsplit("/", 1)[-1]:
            candidate_urls.append(f"{normalized_url}/")

        response = None
        for candidate_url in candidate_urls:
            try:
                response = requests.get(
                    candidate_url,
                    headers={"User-Agent": "AI-OS lead validation bot; contact via site owner"},
                    timeout=8,
                )
                response.raise_for_status()
                break
            except Exception:
                response = None
        if response is None:
            raise RuntimeError("page fetch failed")

        raw_html = response.text
        mailto_values = [
            unquote(html.unescape(match)).split("?", 1)[0].strip()
            for match in re.findall(r"mailto:([^\"'<>#\s]+)", raw_html, flags=re.I)
        ]
        raw_emails = re.findall(EMAIL_PATTERN, raw_html)
        hidden_emails = " ".join(sorted(set(mailto_values + raw_emails)))
        text = re.sub(r"<(script|style).*?</\1>", " ", raw_html, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(f"{text} {hidden_emails}")
        text = re.sub(r"\s+", " ", text)
        result = (text[:30000], "fetched")
    except Exception:
        result = ("", "failed")
    _FETCH_CACHE[normalized_url] = result
    return result


def _site_root(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url.rstrip("/")


def _add_unique_url(urls: list[str], url: str) -> None:
    if url and url not in urls:
        urls.append(url)


def _official_page_urls(lead: LeadCandidate) -> list[str]:
    urls = []
    for url in [lead.linkedin_or_contact_url, lead.source_url, lead.website]:
        if _is_official_page(url, lead) and url not in urls:
            urls.append(url)
    if lead.website and not urls:
        urls.append(lead.website)
    site_root = _site_root(lead.website)
    for path in CONTACT_PATHS:
        if site_root:
            _add_unique_url(urls, f"{site_root}{path}")
    return urls


def _official_pages(lead: LeadCandidate) -> tuple[list[dict], str]:
    if not _is_official_domain_url(lead.website):
        return [], "not_attempted"

    urls = _official_page_urls(lead)[:12]
    statuses = []
    pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        fetch_results = list(executor.map(_fetch_page_text, urls))
    for url, (text, status) in zip(urls, fetch_results):
        statuses.append(status)
        if text:
            pages.append({"url": url, "text": text})
    if pages:
        return pages, "fetched"
    if "failed" in statuses:
        return [], "failed"
    return [], "not_attempted"


def _official_page_text(lead: LeadCandidate) -> tuple[str, str]:
    pages, status = _official_pages(lead)
    return "\n".join(page["text"] for page in pages), status


def _email_candidates(text: str) -> list[str]:
    emails = sorted(set(re.findall(EMAIL_PATTERN, text)))
    blocked = ("example.com", "domain.com", "email.com")
    return [e for e in emails if not any(e.lower().endswith(b) for b in blocked)]


def _same_domain_emails(emails: list[str], domain: str) -> list[str]:
    return [email.lower() for email in emails if domain and email.lower().endswith(domain)]


def _name_confirmed(lead: LeadCandidate, text: str) -> bool:
    haystack = text.lower()
    compact_haystack = re.sub(r"[^a-z0-9]+", "", haystack)
    names = {lead.fund_name.lower()}
    names.update(part.strip().lower() for part in re.split(r"[()/|]", lead.fund_name) if len(part.strip()) >= 3)
    domain_root = _domain_from_url(lead.website).split(".")[0]
    if len(domain_root) >= 3:
        names.add(domain_root)
    compact_names = {re.sub(r"[^a-z0-9]+", "", name) for name in names if name}
    return any(name and name in haystack for name in names) or any(name and name in compact_haystack for name in compact_names)


def _purpose_confirmed(text: str) -> bool:
    haystack = text.lower()
    purpose_terms = ("venture", "vc", "fund", "invest", "seed", "startup", "portfolio", "founder")
    return any(term in haystack for term in purpose_terms)


def _person_confirmed(lead: LeadCandidate, text: str) -> bool:
    person = re.sub(r"\([^)]*\)", "", lead.likely_contact_person).strip()
    if not person or person.lower() in GENERIC_CONTACT_NAMES:
        return False
    first_token = person.split()[0].lower()
    last_token = person.split()[-1].lower()
    haystack = text.lower()
    return len(first_token) > 2 and len(last_token) > 2 and first_token in haystack and last_token in haystack


def _looks_like_person_name(name: str, lead: LeadCandidate) -> bool:
    clean = re.sub(r"\s+", " ", name).strip(" .,-")
    tokens = clean.split()
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    connectors = {"van", "von", "de", "del", "der", "den", "du", "la", "le", "da"}
    if tokens[0].lower().strip(".,") in connectors:
        return False
    lower = clean.lower()
    blocked_terms = {
        "about us",
        "contact us",
        "privacy policy",
        "cookie policy",
        "investment team",
        "portfolio companies",
        "student investment",
        "venture capital",
        "read more",
        "learn more",
        "sign up",
        "follow us",
    }
    if lower in blocked_terms or lower in GENERIC_CONTACT_NAMES:
        return False
    fund_words = {word for word in re.findall(r"[a-z]{3,}", lead.fund_name.lower())}
    name_words = {word.lower().strip(".,") for word in tokens}
    if name_words & fund_words:
        return False
    bad_tokens = {
        "ambassadors",
        "amsterdam",
        "apply",
        "advisory",
        "analyst",
        "analysts",
        "boards",
        "belgium",
        "berlin",
        "dutch",
        "europe",
        "european",
        "fund",
        "funds",
        "founder",
        "founders",
        "france",
        "germany",
        "gallen",
        "venture",
        "ventures",
        "capital",
        "investment",
        "investments",
        "portfolio",
        "contact",
        "do",
        "download",
        "down-open",
        "email",
        "financial",
        "forgis",
        "linkedin",
        "loans",
        "privacy",
        "cookies",
        "student",
        "students",
        "team",
        "board",
        "chair",
        "director",
        "expert",
        "experts",
        "home",
        "investing",
        "leadership",
        "london",
        "marketing",
        "manager",
        "managing",
        "meet",
        "menu",
        "mentors",
        "model",
        "more",
        "netherlands",
        "network",
        "opportunities",
        "our",
        "partner",
        "partners",
        "port",
        "principal",
        "associate",
        "platform",
        "operations",
        "finance",
        "role",
        "search",
        "she",
        "shareholders",
        "st",
        "stay",
        "swiss",
        "switzerland",
        "tech",
        "testimonials",
        "the",
        "uk",
        "united",
        "use",
        "we",
        "why",
        "zurich",
    }
    if any(token.lower().strip(".,") in bad_tokens for token in tokens):
        return False
    roman_tokens = {"i", "ii", "iii", "iv", "v", "vi"}
    if any(token.lower().strip(".,") in roman_tokens for token in tokens):
        return False
    name_tokens = [token for token in tokens if token.lower().strip(".,") not in connectors]
    if len([token for token in name_tokens if len(token.strip(".,'-")) >= 3]) < 2:
        return False
    first_name = name_tokens[0].lower().strip(".,'-")
    all_caps_name = all(token.isupper() and len(token.strip(".,'-")) > 2 for token in name_tokens)
    if first_name not in PERSON_FIRST_NAME_HINTS and not all_caps_name:
        return False
    return all(re.match(r"^[A-Z][A-Za-z'.-]+$", token) or token.lower() in connectors for token in tokens)


def _extract_names(window: str, lead: LeadCandidate) -> list[str]:
    pattern = r"\b([A-Z][A-Za-z'.-]{1,}(?:\s+(?:[A-Z][A-Za-z'.-]{1,}|van|von|de|del|der|den|du|la|le|da)){1,3})\b"
    names = []
    for match in re.finditer(pattern, window):
        tokens = re.sub(r"\s+", " ", match.group(1)).strip().split()
        candidates = []
        for size in (2, 3):
            for start in range(0, max(0, len(tokens) - size + 1)):
                candidates.append(" ".join(tokens[start:start + size]))
        if len(tokens) <= 3:
            candidates.append(" ".join(tokens))
        for name in candidates:
            if _looks_like_person_name(name, lead) and name not in names:
                names.append(name)
    return names


def _page_role_weight(url: str) -> int:
    path = urlparse(url).path.lower()
    if any(token in path for token in ("/team", "/people")):
        return 30
    if any(token in path for token in ("/about", "/funds", "/portfolio")):
        return 15
    return 0


_LINKEDIN_PROFILE_PATTERN = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([A-Za-z0-9_%-]{3,})", re.I)


def _extract_linkedin_profile(window: str) -> str:
    match = _LINKEDIN_PROFILE_PATTERN.search(window)
    return match.group(0) if match else ""


def _extract_official_contact_person(lead: LeadCandidate, pages: list[dict]) -> dict:
    best: dict = {}
    for page in pages:
        text = page.get("text", "")
        url = page.get("url", "")
        for role_term, role_label in ROLE_LABELS:
            for role_match in re.finditer(re.escape(role_term), text, flags=re.I):
                start = max(0, role_match.start() - 150)
                end = min(len(text), role_match.end() + 300)
                window = text[start:end]
                role_center = role_match.start() - start
                for name in _extract_names(window, lead):
                    name_index = window.find(name)
                    if name_index == -1:
                        continue
                    distance = abs(name_index - role_center)
                    score = 160 - min(distance, 160) + _page_role_weight(url)
                    if score <= best.get("score", -1):
                        continue
                    best = {
                        "name": name,
                        "role": role_label,
                        "url": url,
                        "confidence": "High" if score >= 120 and any(token in urlparse(url).path.lower() for token in ("/team", "/people")) else "Medium",
                        "score": score,
                        "linkedin_profile_url": _extract_linkedin_profile(window),
                    }
    return best


def _normalize_contact_person(lead: LeadCandidate, pages: list[dict]) -> None:
    extracted = _extract_official_contact_person(lead, pages)
    if extracted:
        lead.likely_contact_person = extracted["name"]
        lead.contact_person_confidence = extracted["confidence"]
        lead.contact_person_source_url = extracted["url"]
        lead.contact_role = extracted["role"]
        if extracted.get("linkedin_profile_url"):
            lead.linkedin_profile_url = extracted["linkedin_profile_url"]
        return
    if lead.likely_contact_person and lead.likely_contact_person.lower() not in GENERIC_CONTACT_NAMES:
        # Claude or enrichment supplied a named contact; page NER missed it — preserve the name
        lead.contact_person_confidence = "Low"
        lead.contact_person_source_url = ""
        return
    lead.likely_contact_person = "Fund Team"
    lead.contact_person_confidence = "Low"
    lead.contact_person_source_url = ""


def _email_source_snippet(text: str, email: str) -> str:
    if not text or not email:
        return ""
    lower = text.lower()
    index = lower.find(email.lower())
    if index == -1:
        return ""
    start = max(0, index - 35)
    end = min(len(text), index + len(email) + 35)
    snippet = html.unescape(text[start:end]).strip()
    return snippet[:80]


def _hunter_domain_search(domain: str) -> tuple[list[str], str]:
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        return [], "not_configured"
    if not domain:
        return [], "not_called"
    if domain in _HUNTER_CACHE:
        return _HUNTER_CACHE[domain]

    try:
        response = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 5},
            timeout=8,
        )
        status = f"http_{response.status_code}"
        if response.status_code >= 400:
            result = ([], f"{status}_error")
        else:
            data = response.json().get("data", {})
            verified_emails = set()
            low_confidence_count = 0
            for item in data.get("emails", []):
                email = item.get("value", "").strip().lower()
                if not email:
                    continue
                try:
                    confidence = float(item.get("confidence", 0) or 0)
                except (TypeError, ValueError):
                    confidence = 0
                if confidence >= 70:
                    verified_emails.add(email)
                else:
                    low_confidence_count += 1
            emails = sorted(verified_emails)
            if emails:
                result = (emails, f"{status}_email_returned")
            elif low_confidence_count:
                result = ([], f"{status}_low_confidence")
            else:
                result = ([], f"{status}_no_email_returned")
    except requests.Timeout:
        result = ([], "timeout")
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        if response is not None:
            result = ([], f"http_{response.status_code}_error")
        else:
            result = ([], "request_error")
    except Exception:
        result = ([], "parse_error")
    _HUNTER_CACHE[domain] = result
    return result


def _hunter_attemptable(domain: str) -> bool:
    return bool(os.getenv("HUNTER_API_KEY") and domain)


def _hunter_email_returned(status: str) -> bool:
    return "email_returned" in (status or "")


def _hunter_no_email_returned(status: str) -> bool:
    return "no_email_returned" in (status or "")


def _dropcontact_api_key() -> str:
    return (
        os.getenv("DROPCONTACT_API_KEY", "").strip()
        or os.getenv("DROP_CONTACT_API_KEY", "").strip()
    )


def _dropcontact_attemptable(lead: LeadCandidate, domain: str) -> bool:
    person = (lead.likely_contact_person or "").strip()
    return bool(
        _dropcontact_api_key()
        and domain
        and person
        and person.lower() not in GENERIC_CONTACT_NAMES
        and _looks_like_person_name(person, lead)
    )


def _person_name_parts(person: str) -> tuple[str, str]:
    tokens = [
        token.strip(".,'-")
        for token in re.findall(r"[A-Za-z'.-]{2,}", person or "")
        if token.lower() not in {"van", "von", "de", "del", "der", "den", "du", "la", "le", "da"}
    ]
    if len(tokens) < 2:
        return "", ""
    return tokens[0], tokens[-1]


def _same_domain_email_from_text(value: str, domain: str) -> str:
    for email in re.findall(EMAIL_PATTERN, value or ""):
        email = email.strip().lower()
        if domain and email.endswith(domain):
            return email
    return ""


def _extract_dropcontact_email(payload, domain: str) -> str:
    if isinstance(payload, dict):
        preferred_keys = ("email", "email_address", "work_email", "professional_email")
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, str):
                email = _same_domain_email_from_text(value, domain)
                if email:
                    return email
        for value in payload.values():
            email = _extract_dropcontact_email(value, domain)
            if email:
                return email
    elif isinstance(payload, list):
        for item in payload:
            email = _extract_dropcontact_email(item, domain)
            if email:
                return email
    elif isinstance(payload, str):
        return _same_domain_email_from_text(payload, domain)
    return ""


def _dropcontact_email_search(lead: LeadCandidate, domain: str) -> tuple[str, str]:
    api_key = _dropcontact_api_key()
    if not api_key:
        return "", "not_configured"
    if not domain:
        return "", "not_called"
    if not _dropcontact_attemptable(lead, domain):
        return "", "missing_named_contact"

    cache_key = f"{lead.likely_contact_person.lower()}|{domain}"
    if cache_key in _DROPCONTACT_CACHE:
        return _DROPCONTACT_CACHE[cache_key]

    first_name, last_name = _person_name_parts(lead.likely_contact_person)
    if not first_name or not last_name:
        result = ("", "missing_named_contact")
        _DROPCONTACT_CACHE[cache_key] = result
        return result

    contact = {
        "first_name": first_name,
        "last_name": last_name,
        "company": lead.fund_name,
        "website": domain,
    }
    headers = {"Content-Type": "application/json", "X-Access-Token": api_key}
    try:
        response = requests.post(
            DROPCONTACT_ENRICH_URL,
            json={"data": [contact], "language": "en"},
            headers=headers,
            timeout=12,
        )
        post_status = f"http_{response.status_code}"
        if response.status_code >= 400:
            result = ("", f"{post_status}_error")
            _DROPCONTACT_CACHE[cache_key] = result
            return result
        request_id = response.json().get("request_id", "")
        if not request_id:
            result = ("", f"{post_status}_missing_request_id")
            _DROPCONTACT_CACHE[cache_key] = result
            return result

        for attempt in range(4):
            if attempt:
                time.sleep(10)
            poll = requests.get(f"{DROPCONTACT_ENRICH_URL}/{request_id}", headers={"X-Access-Token": api_key}, timeout=12)
            poll_status = f"http_{poll.status_code}"
            if poll.status_code >= 400:
                result = ("", f"{poll_status}_error")
                _DROPCONTACT_CACHE[cache_key] = result
                return result
            data = poll.json()
            if not data.get("success") and "not ready" in str(data.get("reason", "")).lower():
                continue
            email = _extract_dropcontact_email(data, domain)
            result = (email, f"{poll_status}_email_returned" if email else f"{poll_status}_no_email_returned")
            _DROPCONTACT_CACHE[cache_key] = result
            return result
        result = ("", "poll_timeout")
    except requests.Timeout:
        result = ("", "timeout")
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        result = ("", f"http_{response.status_code}_error" if response is not None else "request_error")
    except Exception:
        result = ("", "parse_error")
    _DROPCONTACT_CACHE[cache_key] = result
    return result


def _apollo_headers() -> dict[str, str]:
    api_key = os.getenv("APOLLO_API_KEY", "").strip()
    if not api_key:
        return {}
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Api-Key": api_key,
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _apollo_email_enrichment_enabled() -> bool:
    return os.getenv("APOLLO_ENABLE_EMAIL_ENRICHMENT", "").strip().lower() in {"1", "true", "yes", "on"}


def _apollo_people_search_enabled() -> bool:
    return os.getenv("APOLLO_ENABLE_PEOPLE_SEARCH", "").strip().lower() in {"1", "true", "yes", "on"}


def _apollo_role_score(title: str) -> int:
    text = (title or "").lower()
    score = 0
    weights = [
        ("portfolio", 60),
        ("platform", 45),
        ("operations", 45),
        ("finance", 35),
        ("investment", 35),
        ("investor", 30),
        ("partner", 30),
        ("principal", 25),
        ("founder", 20),
        ("managing director", 20),
        ("associate", 10),
    ]
    for token, weight in weights:
        if token in text:
            score += weight
    return score


def _apollo_person_email(person: dict) -> tuple[str, str]:
    for key in ("email", "email_address"):
        email = (person.get(key) or "").strip().lower()
        if email and "@" in email and not email.endswith("@email-not-found.apollo.io"):
            confidence = (person.get("email_status") or person.get("email_confidence") or "apollo_returned").strip()
            return email, confidence
    return "", ""


def _apollo_search_people(domain: str) -> tuple[list[dict], str]:
    headers = _apollo_headers()
    if not _apollo_people_search_enabled() or not headers or not domain:
        return [], "not_configured"

    params: list[tuple[str, str | int | bool]] = [
        ("q_organization_domains_list[]", domain),
        ("include_similar_titles", True),
        ("page", 1),
        ("per_page", 8),
    ]
    params.extend(("person_titles[]", title) for title in APOLLO_TARGET_TITLES)
    params.extend(("person_seniorities[]", seniority) for seniority in APOLLO_TARGET_SENIORITIES)

    try:
        response = requests.post(APOLLO_PEOPLE_SEARCH_URL, headers=headers, params=params, timeout=18)
        if response.status_code == 403:
            return [], "search_http_403_need_master_api_key"
        if response.status_code >= 400:
            return [], f"search_http_{response.status_code}"
        data = response.json()
    except Exception:
        return [], "search_failed"

    people = data.get("people") or data.get("contacts") or []
    if not isinstance(people, list):
        return [], "search_unexpected_response"
    return people, "search_ok" if people else "search_no_match"


def _apollo_enrich_person(person: dict, domain: str) -> tuple[dict, str]:
    if not _apollo_email_enrichment_enabled():
        return person, "email_enrichment_disabled"

    headers = _apollo_headers()
    person_id = person.get("id") or person.get("person_id")
    params = {
        "domain": domain,
        "reveal_personal_emails": False,
    }
    if person_id:
        params["id"] = person_id
    elif person.get("linkedin_url"):
        params["linkedin_url"] = person.get("linkedin_url")
    elif person.get("name"):
        params["name"] = person.get("name")
    else:
        return person, "enrichment_skipped_no_identifier"

    try:
        response = requests.post(APOLLO_PEOPLE_MATCH_URL, headers=headers, params=params, timeout=18)
        if response.status_code == 403:
            return person, "enrichment_http_403_need_master_api_key"
        if response.status_code >= 400:
            return person, f"enrichment_http_{response.status_code}"
        data = response.json()
    except Exception:
        return person, "enrichment_failed"

    enriched = data.get("person") or data.get("contact") or data
    if not isinstance(enriched, dict):
        return person, "enrichment_unexpected_response"
    merged = {**person, **enriched}
    return merged, "enriched"


def _apply_apollo_enrichment(lead: LeadCandidate, domain: str) -> None:
    lead.apollo_status = "not_configured"
    lead.apollo_person_name = ""
    lead.apollo_title = ""
    lead.apollo_email = ""
    lead.apollo_email_confidence = ""
    lead.apollo_person_linkedin = ""
    if not domain or not lead.fetch_verified:
        lead.apollo_status = "skipped_unverified_domain"
        return

    people, status = _apollo_search_people(domain)
    lead.apollo_status = status
    if not people:
        return

    best = sorted(
        people,
        key=lambda person: (
            _apollo_role_score(person.get("title") or person.get("headline") or ""),
            1 if person.get("linkedin_url") else 0,
            1 if person.get("name") else 0,
        ),
        reverse=True,
    )[0]
    best, enrichment_status = _apollo_enrich_person(best, domain)
    lead.apollo_status = enrichment_status if enrichment_status != "email_enrichment_disabled" else "matched_email_enrichment_disabled"
    lead.apollo_person_name = (best.get("name") or "").strip()
    lead.apollo_title = (best.get("title") or best.get("headline") or "").strip()
    lead.apollo_person_linkedin = (best.get("linkedin_url") or "").strip()
    lead.apollo_email, lead.apollo_email_confidence = _apollo_person_email(best)

    if lead.apollo_title:
        role_probe = LeadCandidate(
            fund_name=lead.fund_name,
            website=lead.website,
            relevance_score=lead.relevance_score,
            thesis_fit_reason=lead.thesis_fit_reason,
            likely_contact_person=lead.apollo_title,
            outreach_angle=lead.outreach_angle,
            confidence=lead.confidence,
        )
        inferred_role = _infer_contact_role(role_probe)
        if inferred_role:
            lead.contact_role = inferred_role
    # Apollo is optional enrichment only. Named-contact confidence is reserved
    # for people found on the fund's official website.


def _source_for_lead(lead: LeadCandidate, sources: list[dict]) -> str:
    if lead.source_url and _is_official_page(lead.source_url, lead) and _is_official_domain_url(lead.source_url):
        return lead.source_url

    lead_domains = {
        _domain_from_url(lead.website),
        _domain_from_url(lead.linkedin_or_contact_url),
    }
    lead_domains.discard("")
    lead_name = lead.fund_name.lower()

    for source in sources:
        url = source.get("url", "")
        if _is_linkedin_url(url):
            continue
        text = f"{source.get('title', '')} {source.get('text', '')}".lower()
        source_domain = _domain_from_url(url)
        if source_domain and source_domain in lead_domains:
            return url
        if lead_name and lead_name in text and not _is_secondary_source(source):
            return url
    for source in sources:
        url = source.get("url", "")
        if url and not _is_linkedin_url(url) and not _is_secondary_source(source):
            return url
    return lead.website if _is_official_domain_url(lead.website) else ""


def _is_contact_route_url(url: str) -> bool:
    return _path_matches_route(url, CONTACT_ROUTE_PATHS)


def _path_matches_route(url: str, route_paths: tuple[str, ...]) -> bool:
    path = urlparse(url or "").path.lower().rstrip("/")
    if not path:
        return False
    for route_path in route_paths:
        route = route_path.lower().rstrip("/")
        if path == route or path.startswith(f"{route}/"):
            return True
    return False


def _is_website_route_url(url: str) -> bool:
    return _path_matches_route(url, WEBSITE_ROUTE_PATHS)


def _preferred_website_route(pages: list[dict]) -> str:
    for route_path in WEBSITE_ROUTE_PATHS:
        for page in pages:
            url = page.get("url", "")
            path = urlparse(url or "").path.lower().rstrip("/")
            route = route_path.rstrip("/")
            if path == route or path.startswith(f"{route}/"):
                return url
    return ""


def _preferred_contact_route(lead: LeadCandidate, pages: list[dict]) -> tuple[str, str]:
    for page in pages:
        url = page.get("url", "")
        if _is_contact_route_url(url):
            return url, "contact_form"
    if lead.linkedin_or_contact_url and _is_official_page(lead.linkedin_or_contact_url, lead):
        if _is_contact_route_url(lead.linkedin_or_contact_url):
            return lead.linkedin_or_contact_url, "contact_form"
        if _is_website_route_url(lead.linkedin_or_contact_url):
            return lead.linkedin_or_contact_url, "website"
    website_route = _preferred_website_route(pages)
    if website_route:
        return website_route, "website"
    if lead.website and not _is_linkedin_url(lead.website):
        return lead.website, "website"
    return "", "warm_intro_needed"


def _enrich_one_lead(lead: LeadCandidate, sources: list[dict]) -> None:
    lead.website = _canonical_website(lead.website)
    if not _is_official_domain_url(lead.website):
        lead.website = ""
    domain = _domain_from_url(lead.website)
    lead.source_url = _source_for_lead(lead, sources)
    if domain and _domain_from_url(lead.source_url) != domain:
        lead.source_url = lead.website
    lead.contact_role = _infer_contact_role(lead)
    lead.hunter_attempted = False
    lead.hunter_response_code = "not_called"
    lead.dropcontact_attempted = False
    lead.dropcontact_response_code = "not_called"
    lead.email_source_snippet = ""
    lead.validation_note = ""
    pages, fetch_status = _official_pages(lead)
    official_text = "\n".join(page.get("text", "") for page in pages)
    lead.fetch_status = fetch_status
    lead.fetch_verified = bool(official_text and _name_confirmed(lead, official_text) and _purpose_confirmed(official_text))
    lead.validation_note = (
        f"Official source verified on {lead.source_url or lead.website}."
        if lead.fetch_verified
        else f"Official source not fully verified on fetched page for {lead.fund_name}."
    )
    contact_route, contact_method = _preferred_contact_route(lead, pages)
    lead.linkedin_or_contact_url = contact_route
    lead.contact_method = contact_method
    _normalize_contact_person(lead, pages)
    if not lead.contact_role:
        lead.contact_role = _infer_contact_role(lead) or "Fund Team"
    official_emails = _same_domain_emails(_email_candidates(official_text), domain)
    hunter_emails, hunter_status = _hunter_domain_search(domain)
    lead.hunter_attempted = _hunter_attemptable(domain)
    lead.hunter_response_code = hunter_status
    _apply_apollo_enrichment(lead, domain)

    if lead.public_email:
        email = lead.public_email.lower()
        if email in official_emails:
            lead.email_confidence = "hunter_verified" if email in hunter_emails else "publicly_listed"
            lead.public_email = email
            lead.email_source_snippet = _email_source_snippet(official_text, email)
            if lead.email_confidence == "hunter_verified":
                lead.validation_note = f"Email found verbatim on official page and confirmed by Hunter for {lead.fund_name}: {email}."
            else:
                lead.validation_note = f"Email found verbatim on official page for {lead.fund_name}: {email}."
            lead.contact_method = "email_direct"
            return
        if domain and email.endswith(domain):
            lead.public_email = ""
            lead.email_confidence = "inferred"
            lead.validation_note = f"Model-supplied email for {lead.fund_name} was same-domain but not found on official pages or verified by Hunter; blocked from outreach use."
        lead.public_email = ""

    if official_emails:
        lead.public_email = official_emails[0]
        lead.email_confidence = "hunter_verified" if lead.public_email in hunter_emails else "publicly_listed"
        lead.email_source_snippet = _email_source_snippet(official_text, lead.public_email)
        if lead.email_confidence == "hunter_verified":
            lead.validation_note = f"Email found verbatim on official page and confirmed by Hunter for {lead.fund_name}: {lead.public_email}."
        else:
            lead.validation_note = f"Email found verbatim on official page for {lead.fund_name}: {lead.public_email}."
        lead.contact_method = "email_direct"
        return

    if hunter_emails:
        lead.public_email = hunter_emails[0]
        lead.email_confidence = "hunter_verified"
        lead.validation_note = f"Email returned by Hunter domain search for {domain}: {lead.public_email}."
        lead.contact_method = "email_direct"
        return

    dropcontact_email, dropcontact_status = _dropcontact_email_search(lead, domain)
    lead.dropcontact_attempted = _dropcontact_attemptable(lead, domain)
    lead.dropcontact_response_code = dropcontact_status
    if dropcontact_email:
        lead.public_email = dropcontact_email
        lead.email_confidence = "dropcontact_verified"
        lead.validation_note = f"Email returned by Dropcontact enrichment for {lead.likely_contact_person} at {domain}: {lead.public_email}."
        lead.contact_method = "email_direct"
        return

    if lead.email_confidence != "inferred":
        if "low_confidence" in (hunter_status or "") or "low_confidence" in (dropcontact_status or ""):
            lead.email_confidence = "low_confidence"
        elif _provider_unavailable_status(hunter_status) or _provider_unavailable_status(dropcontact_status):
            lead.email_confidence = "provider_unavailable"
        else:
            lead.email_confidence = "not_found"
    lead.contact_method = _contact_method(lead)
    if lead.dropcontact_attempted:
        lead.validation_note = f"Official pages and Hunter checked; Dropcontact attempted for {domain} and returned {lead.dropcontact_response_code}."
    elif lead.email_confidence == "inferred":
        lead.validation_note = f"Inferred email blocked; official pages and Hunter did not verify a usable public email for {domain}."
    elif "low_confidence" in (lead.hunter_response_code or ""):
        lead.validation_note = f"Hunter returned only low-confidence email candidates for {domain}; no email is usable without manual verification."
    elif lead.hunter_attempted and _hunter_no_email_returned(lead.hunter_response_code):
        lead.validation_note = f"Official pages checked and Hunter domain search returned no public email for {domain}."
    elif lead.hunter_attempted:
        lead.validation_note = f"Official pages checked; Hunter domain search was attempted for {domain} but returned {lead.hunter_response_code}."
    elif lead.fetch_verified:
        lead.validation_note = f"Official pages checked; no public same-domain email found for {lead.fund_name}."


def _enrich_contacts(leads: list[LeadCandidate], search_text: str, sources: list[dict]) -> list[LeadCandidate]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda lead: _enrich_one_lead(lead, sources), leads))
    return leads


def _infer_contact_role(lead: LeadCandidate) -> str:
    person = lead.likely_contact_person.lower()
    if "fund team" in person or "fund board" in person or "team" == person.strip():
        return "Fund Team"
    text = f"{lead.likely_contact_person} {lead.thesis_fit_reason} {lead.outreach_angle}".lower()
    role_map = [
        ("managing partner", "Partner"),
        ("investment director", "Investment"),
        ("investment manager", "Investment"),
        ("fund director", "Fund Team"),
        ("portfolio", "Portfolio"),
        ("platform", "Platform"),
        ("operations", "Operations"),
        ("finance", "Finance"),
        ("fundraising", "Fundraising"),
        ("partner", "Partner"),
        ("investment", "Investment"),
        ("principal", "Investment"),
        ("associate", "Investment"),
        ("board", "Fund Team"),
        ("team", "Fund Team"),
    ]
    for token, label in role_map:
        if token in text:
            return label
    return ""


def _contact_method(lead: LeadCandidate) -> str:
    route = f"{lead.linkedin_or_contact_url} {lead.website}".lower()
    if lead.public_email:
        return "email_direct"
    if lead.linkedin_or_contact_url and _is_contact_route_url(lead.linkedin_or_contact_url):
        return "contact_form"
    if lead.website and not _is_linkedin_url(lead.website):
        return "website"
    if "linkedin.com" in route:
        return "linkedin_dm"
    return "warm_intro_needed"


def _is_external_fund_lead(lead: LeadCandidate) -> bool:
    name = lead.fund_name.lower()
    fund_type = lead.fund_type.lower()
    combined = f"{name} {fund_type} {lead.website}".lower()
    if lead.website and not _is_official_domain_url(lead.website):
        return False
    if "asif" in combined:
        return False
    if _is_linkedin_url(lead.source_url):
        return False
    if (
        lead.contact_person_confidence.lower() == "low"
        and lead.email_confidence == "not_found"
        and lead.contact_method in {"linkedin_dm", "warm_intro_needed"}
    ):
        return False
    blocked = ("database", "blog", "newsletter", "report", "research", "media", "directory")
    return not any(term in combined for term in blocked)


def _is_validated_lead(lead: LeadCandidate) -> bool:
    if not _is_external_fund_lead(lead):
        return False
    if not lead.fetch_verified:
        return False
    if not lead.website or not lead.source_url:
        return False
    if _domain_from_url(lead.source_url) != _domain_from_url(lead.website):
        return False
    if lead.email_confidence == "hunter_verified" and not lead.public_email:
        return False
    return True


def _strict_student_fund_requested(project_context: str, target_profile: str, geography: str) -> bool:
    text = f"{project_context} {target_profile} {geography}".lower()
    return "asif" in text or "student-run" in text or "student run" in text or "student-led" in text or "student led" in text


def _student_or_university_fit(lead: LeadCandidate) -> bool:
    text = f"{lead.fund_name} {lead.fund_type} {lead.geography} {lead.thesis_fit_reason} {lead.outreach_angle}".lower()
    return any(term in text for term in STUDENT_FUND_TERMS)


def _professional_filler(lead: LeadCandidate) -> bool:
    text = f"{lead.fund_name} {lead.fund_type} {lead.geography} {lead.thesis_fit_reason} {lead.outreach_angle}".lower()
    if _student_or_university_fit(lead):
        return False
    if "tiny supercomputer" in text or "tiny.vc" in lead.website.lower():
        return True
    return any(term in text for term in PROFESSIONAL_FUND_TERMS)


def _strict_student_fit_score(lead: LeadCandidate) -> int:
    text = f"{lead.fund_name} {lead.fund_type} {lead.geography} {lead.thesis_fit_reason} {lead.outreach_angle}".lower()
    score = lead.relevance_score
    if any(term in text for term in ("student-run", "student run", "student-led", "student led", "student vc", "student venture")):
        score += 35
    if any(term in text for term in ("student", "campus")):
        score += 12
    if any(term in text for term in ("university", "academic", "inter-university", "university-linked")):
        score += 18
    if any(term in text for term in ("portfolio monitoring", "fund kpi", "moic", "dpi", "tvpi", "valuation", "reporting")):
        score += 8
    if lead.public_email:
        score += 5
    if lead.likely_contact_person.lower() not in GENERIC_CONTACT_NAMES:
        score += 5
    if _professional_filler(lead):
        score -= 45
    if any(term in text for term in ("accelerator only", "corporate vc", "us-only", "database", "directory", "newsletter")):
        score -= 100
    return score


def _dedupe_leads(leads: list[LeadCandidate]) -> list[LeadCandidate]:
    seen = set()
    unique = []
    for lead in leads:
        domain_key = _domain_from_url(lead.website)
        name_key = re.sub(r"\([^)]*\)", "", lead.fund_name.lower())
        name_key = re.sub(r"[^a-z0-9]+", "", name_key)
        keys = {key for key in (domain_key, name_key) if key}
        if not keys or seen.intersection(keys):
            continue
        seen.update(keys)
        unique.append(lead)
    return unique


def _geo_bucket(lead: LeadCandidate) -> str:
    text = f"{lead.geography} {lead.fund_name} {lead.website}".lower()
    if "netherlands" in text or "dutch" in text:
        return "Netherlands"
    if "united kingdom" in text or " uk" in f" {text}" or "london" in text:
        return "United Kingdom"
    if "switzerland" in text or "swiss" in text:
        return "Switzerland"
    if "belgium" in text or "belgian" in text:
        return "Belgium"
    if "france" in text or "french" in text:
        return "France"
    if any(term in text for term in ("nordic", "nordics", "denmark", "sweden", "norway", "finland", "baltic")):
        return "Nordics"
    if any(term in text for term in ("dach", "germany", "german", "austria", "austrian")):
        return "DACH"
    return lead.geography.split("/")[0].split("(")[0].strip() or "Europe"


def _should_rebalance_geography(project_context: str, target_profile: str, geography: str) -> bool:
    text = f"{project_context} {target_profile} {geography}".lower()
    return "europe" in text or "asif" in text


def _rebalance_geography(leads: list[LeadCandidate], count: int) -> list[LeadCandidate]:
    selected: list[LeadCandidate] = []
    overflow: list[LeadCandidate] = []
    bucket_counts: Counter[str] = Counter()
    for lead in leads:
        bucket = _geo_bucket(lead)
        if bucket_counts[bucket] < MAX_GEOGRAPHY_BUCKET:
            selected.append(lead)
            bucket_counts[bucket] += 1
        else:
            overflow.append(lead)
    if len(selected) < count:
        selected.extend(overflow[: count - len(selected)])
    return selected[:count]


def _over_geography_cap(leads: list[LeadCandidate]) -> bool:
    return any(total > MAX_GEOGRAPHY_BUCKET for total in Counter(_geo_bucket(lead) for lead in leads).values())


def _select_final_leads(
    leads: list[LeadCandidate],
    count: int,
    project_context: str,
    target_profile: str,
    geography: str,
) -> list[LeadCandidate]:
    strict_student = _strict_student_fund_requested(project_context, target_profile, geography)
    if strict_student:
        preferred = [lead for lead in leads if not _professional_filler(lead)]
        rank_pool = preferred if len(preferred) >= count else leads
        ranked = _finalize_outreach_rows(rank_pool, strict_student=True)
    else:
        ranked = _finalize_outreach_rows(leads, strict_student=False)
    if _should_rebalance_geography(project_context, target_profile, geography):
        return _rebalance_geography(ranked, count)
    return ranked[:count]


def _secondary_sources(sources: list[dict]) -> list[dict]:
    seen = set()
    secondary = []
    for source in sources:
        url = source.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        if _is_secondary_source(source):
            secondary.append(source)
    return secondary[:12]


def _has_apollo_data(leads: list[LeadCandidate]) -> bool:
    return any(
        lead.apollo_person_name
        or lead.apollo_title
        or lead.apollo_email
        or lead.apollo_person_linkedin
        for lead in leads
    )


def _has_dropcontact_data(leads: list[LeadCandidate]) -> bool:
    return any(
        lead.email_confidence == "dropcontact_verified"
        for lead in leads
    )


def _csv_columns(leads: list[LeadCandidate]) -> list[str]:
    return list(CSV_COLUMNS)


def _has_hunter_verified_email(lead: LeadCandidate) -> bool:
    return bool(lead.public_email and lead.hunter_attempted and _hunter_email_returned(lead.hunter_response_code))


def _has_dropcontact_verified_email(lead: LeadCandidate) -> bool:
    return bool(
        lead.public_email
        and lead.dropcontact_attempted
        and "email_returned" in (lead.dropcontact_response_code or "")
    )


def _apollo_status_has_data(lead: LeadCandidate) -> bool:
    return bool(lead.apollo_person_name or lead.apollo_title or lead.apollo_email or lead.apollo_person_linkedin)


def _email_matches_contact_person(email: str, person: str) -> bool:
    if not email or not person or person.lower() in GENERIC_CONTACT_NAMES:
        return True
    local = email.split("@", 1)[0].lower()
    if local in GENERIC_EMAIL_PREFIXES:
        return True
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z]{3,}", person)
        if token.lower() not in {"the", "and"}
    ]
    if not tokens:
        return True
    return any(token in local for token in tokens)


def _is_generic_public_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    return email.split("@", 1)[0].lower() in GENERIC_EMAIL_PREFIXES


def _provider_unavailable_status(status: str) -> bool:
    normalized = (status or "").lower()
    if normalized in {"", "not_called", "no_email_returned", "http_200_no_email_returned", "missing_named_contact"}:
        return False
    if normalized == "not_configured":
        return True
    if "low_confidence" in normalized or "email_returned" in normalized or "no_email_returned" in normalized:
        return False
    return any(token in normalized for token in ("timeout", "error", "request", "parse", "poll_timeout", "missing_request_id"))


def _provider_status_flags(lead: LeadCandidate) -> list[str]:
    flags = []
    provider_statuses = [
        ("hunter", lead.hunter_response_code, lead.hunter_attempted or lead.hunter_response_code == "not_configured"),
        ("dropcontact", lead.dropcontact_response_code, lead.dropcontact_attempted),
    ]
    for provider, status, attempted in provider_statuses:
        if not attempted:
            continue
        normalized = (status or "").lower()
        if not normalized or normalized in {"not_called", "no_email_returned", "missing_named_contact"}:
            continue
        if "low_confidence" in normalized:
            flags.append(f"{provider}_low_confidence:{status}")
        elif _provider_unavailable_status(status):
            flags.append(f"{provider}_provider_unavailable:{status}")
    return flags


def _derive_email_status(lead: LeadCandidate) -> str:
    if (
        lead.public_email
        and (
            lead.email_confidence == "publicly_listed"
            or (lead.email_confidence == "hunter_verified" and _has_hunter_verified_email(lead))
            or (lead.email_confidence == "dropcontact_verified" and _has_dropcontact_verified_email(lead))
        )
    ):
        return "verified"
    if lead.email_confidence in {"inferred", "low_confidence"} or (lead.public_email and lead.email_confidence):
        return "low_confidence"
    if lead.email_confidence == "blocked":
        return "blocked"
    if lead.email_confidence == "provider_unavailable" or _provider_status_flags(lead):
        return "provider_unavailable"
    return "unavailable"


def _primary_evidence_url(lead: LeadCandidate) -> str:
    for url in [lead.source_url, lead.contact_person_source_url, lead.linkedin_or_contact_url, lead.website]:
        if _is_official_page(url, lead) and _is_official_domain_url(url):
            return url
    return lead.website if _is_official_domain_url(lead.website) else ""


def _evidence_quality_score(lead: LeadCandidate) -> int:
    evidence_url = _primary_evidence_url(lead)
    if not evidence_url or _is_linkedin_url(evidence_url) or _is_secondary_source({"url": evidence_url}):
        return 0
    if lead.fetch_verified and _is_website_route_url(evidence_url):
        return 3
    if lead.fetch_verified:
        return 2
    return 1


def _derive_fit_score(lead: LeadCandidate, strict_student: bool = False) -> int:
    score = _strict_student_fit_score(lead) if strict_student else lead.relevance_score
    if strict_student and _professional_filler(lead):
        score = min(score, 55)
    return max(0, min(100, int(score)))


def _derive_route_quality(lead: LeadCandidate) -> str:
    evidence_score = _evidence_quality_score(lead)
    email_status = _derive_email_status(lead)
    contact_url = lead.linkedin_or_contact_url or lead.website
    if evidence_score == 0 or not lead.website:
        return "D"
    if email_status == "verified" and lead.public_email:
        return "A" if lead.fetch_verified else "B"
    if lead.contact_method == "contact_form" and contact_url and _is_official_page(contact_url, lead):
        return "B" if lead.fetch_verified else "C"
    if lead.contact_method == "website" and contact_url and _is_official_page(contact_url, lead):
        return "C" if lead.fetch_verified else "D"
    return "D"


def _route_quality_score(route_quality: str) -> int:
    return {"A": 3, "B": 2, "C": 1, "D": 0}.get(route_quality or "", 0)


def _derive_evidence_summary(lead: LeadCandidate) -> str:
    if _evidence_quality_score(lead) == 0:
        return "No acceptable primary evidence URL; use discovery sources only for research."
    if lead.fetch_verified:
        fund_type = (lead.fund_type or "fund").lower()
        fit_note = (lead.thesis_fit_reason or "").rstrip(".").strip()
        fit_note = fit_note[:120] if fit_note else ""
        base = f"{lead.fund_name} confirmed as {fund_type} via official site."
        return f"{base} {fit_note}." if fit_note else base
    if lead.fetch_status == "failed":
        return "Official URL identified, but page fetch failed; manually verify before outreach."
    return "Official URL identified, but page text was not confirmed."


def _derive_validation_flags(lead: LeadCandidate, fit_score: int, route_quality: str, email_status: str) -> str:
    flags = []
    if email_status != "verified":
        flags.append("no_verified_email")
    if email_status == "low_confidence":
        flags.append("email_low_confidence")
    if email_status == "provider_unavailable":
        flags.append("provider_unavailable")
    if email_status == "blocked":
        flags.append("email_blocked")
    flags.extend(_provider_status_flags(lead))
    if not lead.is_student_run:
        flags.append("not_student_run")
    if _evidence_quality_score(lead) == 0:
        flags.append("weak_or_missing_primary_evidence")
    if not lead.fetch_verified:
        flags.append("official_page_unverified")
    contact_url = lead.linkedin_or_contact_url or lead.website
    if route_quality in {"C", "D"}:
        flags.append("weak_contact_route")
    if (
        lead.contact_method == "website"
        and contact_url
        and lead.website
        and contact_url.rstrip("/") == lead.website.rstrip("/")
    ):
        flags.append("homepage_only_route")
    if lead.contact_person_confidence.lower() != "high":
        flags.append("contact_person_unverified")
    if fit_score < 60:
        flags.append("low_fit_score")
    unique_flags = list(dict.fromkeys(flags))
    return "; ".join(unique_flags) if unique_flags else "none"


def _derive_validation_status(lead: LeadCandidate, fit_score: int, route_quality: str, email_status: str) -> str:
    if route_quality == "D" or fit_score < 50 or _evidence_quality_score(lead) == 0 or email_status == "blocked":
        return "blocked"
    if any("provider_unavailable" in flag for flag in _provider_status_flags(lead)):
        return "needs_review"
    if route_quality == "A" and fit_score >= 70 and email_status == "verified" and lead.fetch_verified:
        return "usable"
    return "needs_review"


def _derive_first_action(lead: LeadCandidate, validation_status: str, email_status: str) -> str:
    if validation_status == "blocked":
        return "Do not outreach yet; replace the lead or manually verify primary evidence and contact route."
    if email_status == "verified" and lead.public_email:
        return f"Review the evidence, then draft a manual email to {lead.public_email}."
    if lead.contact_method == "contact_form":
        return "Open the official contact page, confirm the right recipient, then draft manually."
    if email_status == "provider_unavailable":
        return "Retry email lookup later or use only an official contact route after manual review."
    return "Find a stronger named contact or warm intro before drafting outreach."


def _derive_suggested_subject(lead: LeadCandidate) -> str:
    text = f"{lead.fund_name} {lead.fund_type} {lead.thesis_fit_reason} {lead.outreach_angle}".lower()
    person = lead.likely_contact_person or ""
    is_generic = not person or person.lower() in GENERIC_CONTACT_NAMES
    first_name = person.split()[0].title() if not is_generic else ""
    is_student = "student" in text or "student" in (lead.fund_type or "").lower()

    if "asif" in text:
        if first_name:
            return f"{first_name} — ASIF portfolio benchmarking question"
        if is_student:
            return f"{lead.fund_name} x ASIF — student fund benchmarking"
        return f"{lead.fund_name} — ASIF portfolio benchmarking question"
    if any(term in text for term in ("ai-os", "workflow", "automation", "vertical ai")):
        if first_name:
            return f"{first_name} — quick workflow automation question"
        return f"{lead.fund_name} — AI workflow automation"
    if is_student:
        if first_name:
            return f"{first_name} — student fund benchmarking question"
        return f"{lead.fund_name} — student fund benchmarking"
    if first_name:
        return f"{first_name} — portfolio benchmarking question"
    return f"{lead.fund_name} — portfolio benchmarking question"


def _apply_outreach_review_fields(lead: LeadCandidate, strict_student: bool, priority_rank: int = 0) -> None:
    fit_score = _derive_fit_score(lead, strict_student)
    email_status = _derive_email_status(lead)
    route_quality = _derive_route_quality(lead)
    validation_status = _derive_validation_status(lead, fit_score, route_quality, email_status)

    # No named recipient + generic inbox → cap at B (email works but no direct human target)
    contact_name_lower = (lead.likely_contact_person or "").lower()
    if (
        route_quality == "A"
        and contact_name_lower in GENERIC_CONTACT_NAMES
        and lead.public_email
        and _is_generic_public_email(lead.public_email)
    ):
        route_quality = "B"

    lead.priority_rank = priority_rank
    lead.fit_score = fit_score
    lead.route_quality = route_quality
    lead.contact_name = lead.likely_contact_person or "Fund Team"
    lead.contact_confidence = lead.contact_person_confidence or "Low"
    if not lead.linkedin_profile_url and lead.apollo_person_linkedin:
        lead.linkedin_profile_url = lead.apollo_person_linkedin
    lead.email = lead.public_email if email_status == "verified" else ""
    lead.email_status = email_status
    lead.contact_url = lead.linkedin_or_contact_url or lead.website
    lead.evidence_url = _primary_evidence_url(lead)
    lead.evidence_summary = _derive_evidence_summary(lead)
    lead.suggested_subject = _derive_suggested_subject(lead)
    lead.validation_status = validation_status
    lead.validation_flags = _derive_validation_flags(lead, fit_score, route_quality, email_status)
    lead.first_action = _derive_first_action(lead, validation_status, email_status)


def _priority_score(lead: LeadCandidate) -> int:
    fit_score = lead.fit_score or _derive_fit_score(lead)
    route_quality = lead.route_quality or _derive_route_quality(lead)
    email_status = lead.email_status or _derive_email_status(lead)
    validation_status = lead.validation_status or _derive_validation_status(lead, fit_score, route_quality, email_status)
    score = (fit_score * 10) + (_evidence_quality_score(lead) * 35) + (_route_quality_score(route_quality) * 25)
    if email_status == "verified":
        score += 20
    if validation_status == "blocked":
        score -= 500
    return score


def _finalize_outreach_rows(leads: list[LeadCandidate], strict_student: bool = False) -> list[LeadCandidate]:
    for lead in leads:
        _apply_outreach_review_fields(lead, strict_student)
    ranked = sorted(
        _dedupe_leads(leads),
        key=lambda lead: (-_priority_score(lead), lead.fund_name.lower()),
    )
    for index, lead in enumerate(ranked, start=1):
        _apply_outreach_review_fields(lead, strict_student, index)
    return ranked


def _sanitize_lead_for_output(lead: LeadCandidate) -> None:
    if _is_linkedin_url(lead.source_url):
        lead.source_url = lead.website if _is_official_domain_url(lead.website) else ""
    if lead.source_url and lead.website and _domain_from_url(lead.source_url) != _domain_from_url(lead.website):
        lead.source_url = lead.website
    if not lead.likely_contact_person:
        lead.likely_contact_person = "Fund Team"
    confidence = (lead.contact_person_confidence or "").lower()
    if confidence not in CONTACT_CONFIDENCE_VALUES:
        lead.contact_person_confidence = "Low"
        confidence = "low"
    named_contact = lead.likely_contact_person.lower() not in GENERIC_CONTACT_NAMES
    source_is_official = _is_official_page(lead.contact_person_source_url, lead)
    plausible_person = _looks_like_person_name(lead.likely_contact_person, lead)
    if confidence in {"high", "medium"} and (not named_contact or not source_is_official or not plausible_person):
        lead.contact_person_confidence = "Low"
        lead.contact_person_source_url = ""
        if not named_contact or not plausible_person:
            lead.likely_contact_person = "Fund Team"
    if lead.contact_person_confidence.lower() == "high" and not any(token in urlparse(lead.contact_person_source_url).path.lower() for token in ("/team", "/people")):
        lead.contact_person_confidence = "Medium"
    if lead.public_email and lead.contact_person_confidence.lower() in {"high", "medium"} and not _email_matches_contact_person(lead.public_email, lead.likely_contact_person):
        lead.likely_contact_person = "Fund Team"
        lead.contact_person_confidence = "Low"
        lead.contact_person_source_url = ""
        lead.contact_role = "Fund Team"
    if lead.public_email and _is_generic_public_email(lead.public_email) and lead.contact_person_confidence.lower() == "high":
        lead.contact_person_confidence = "Medium"
    if lead.email_confidence == "hunter_verified" and not (
        _has_hunter_verified_email(lead)
    ):
        lead.public_email = ""
        lead.email_confidence = "inferred"
    if lead.email_confidence == "inferred":
        lead.public_email = ""
    if not _apollo_status_has_data(lead):
        lead.apollo_status = "not_configured"
        lead.apollo_person_name = ""
        lead.apollo_title = ""
        lead.apollo_email = ""
        lead.apollo_email_confidence = ""
        lead.apollo_person_linkedin = ""
    if not lead.contact_role:
        lead.contact_role = _infer_contact_role(lead) or "Fund Team"
    if not lead.linkedin_or_contact_url and lead.website and not _is_linkedin_url(lead.website):
        lead.linkedin_or_contact_url = lead.website
    lead.contact_method = _contact_method(lead)


def _sanitize_leads_for_output(leads: list[LeadCandidate]) -> list[LeadCandidate]:
    for lead in leads:
        _sanitize_lead_for_output(lead)
    return leads


def _validation_notes(leads: list[LeadCandidate], requested_count: int, strict_student: bool = False) -> list[str]:
    notes = []
    if len(leads) == requested_count:
        notes.append(f"PASS: Returned exactly {requested_count} lead rows.")
    else:
        notes.append(f"WARN: Returned {len(leads)} lead rows for requested count {requested_count}; usable candidates may have been filtered out.")
    if all(not _is_linkedin_url(lead.evidence_url or lead.source_url) for lead in leads):
        notes.append("PASS: No LinkedIn URLs used as primary evidence_url.")
    weak_evidence = [
        lead.fund_name for lead in leads
        if _evidence_quality_score(lead) == 0
        or _is_secondary_source({"url": lead.evidence_url or lead.source_url})
    ]
    if weak_evidence:
        notes.append(f"WARN: Weak or missing primary evidence_url: {', '.join(weak_evidence)}.")
    else:
        notes.append("PASS: Primary evidence URLs are official fund pages, not discovery-only sources.")
    if all("asif" not in f"{lead.fund_name} {lead.website}".lower() for lead in leads):
        notes.append("PASS: No ASIF self-reference in lead rows.")
    usable = [lead for lead in leads if lead.validation_status == "usable"]
    needs_review = [lead for lead in leads if lead.validation_status == "needs_review"]
    blocked = [lead for lead in leads if lead.validation_status == "blocked"]
    if blocked:
        notes.append(f"WARN: {len(blocked)} row(s) are blocked and should not be used for outreach: {', '.join(lead.fund_name for lead in blocked)}.")
    if needs_review:
        notes.append(f"WARN: {len(needs_review)} row(s) need manual review before outreach.")
    if usable:
        notes.append(f"PASS: {len(usable)} row(s) have verified email, strong route quality, and confirmed official evidence.")
    else:
        notes.append("WARN: No row is marked usable; every row needs manual review or replacement before outreach.")
    unsafe_email_rows = [
        lead.fund_name for lead in leads
        if (lead.email_status != "verified" and (lead.email or lead.public_email))
    ]
    if unsafe_email_rows:
        notes.append(f"WARN: Non-verified email values remain in rows: {', '.join(unsafe_email_rows)}.")
    else:
        notes.append("PASS: Non-verified or inferred emails are not exported as usable email values.")
    provider_flags = [lead.fund_name for lead in leads if "provider_unavailable" in lead.validation_flags]
    low_confidence = [lead.fund_name for lead in leads if "low_confidence" in lead.validation_flags]
    if provider_flags:
        notes.append(f"WARN: Email provider unavailable or failed for {len(provider_flags)} row(s): {', '.join(provider_flags)}.")
    if low_confidence:
        notes.append(f"WARN: Low-confidence email candidates were blocked for {len(low_confidence)} row(s): {', '.join(low_confidence)}.")
    if all(lead.route_quality in {"A", "B", "C", "D"} for lead in leads):
        notes.append("PASS: route_quality is assigned for every row.")
    if all(lead.first_action and lead.validation_status and lead.validation_flags for lead in leads):
        notes.append("PASS: Row-level first_action, validation_status, and validation_flags are present.")
    unverified_email_routes = [lead.fund_name for lead in leads if lead.email_status != "verified"]
    if unverified_email_routes:
        notes.append(f"WARN: {len(unverified_email_routes)} row(s) have no verified email; use first_action instead of direct outreach.")
    if _has_dropcontact_data(leads):
        dropcontact_hits = sum(1 for lead in leads if lead.email_confidence == "dropcontact_verified")
        notes.append(f"INFO: Dropcontact fallback returned verified emails for {dropcontact_hits} rows.")
    website_homepage_rows = [
        lead.fund_name for lead in leads
        if lead.contact_method == "website"
        and lead.linkedin_or_contact_url
        and lead.website
        and lead.linkedin_or_contact_url.rstrip("/") == lead.website.rstrip("/")
    ]
    if website_homepage_rows:
        notes.append(f"INFO: Homepage fallback remains where no specific fetched route was available: {', '.join(website_homepage_rows)}.")
    if _has_apollo_data(leads):
        matched = sum(1 for lead in leads if lead.apollo_person_name)
        notes.append(f"INFO: Apollo enrichment found named contact data for {matched}/{len(leads)} validated leads.")
    if strict_student:
        professional_rows = [lead.fund_name for lead in leads if _professional_filler(lead)]
        if professional_rows:
            notes.append(f"INFO: Professional micro-VC/fund-of-funds rows kept only because validated alternatives were limited: {', '.join(professional_rows)}.")
        else:
            notes.append("PASS: Strict student-fund replacement removed professional micro-VC filler rows.")
    return notes


def _curated_backfill(existing: list[LeadCandidate], count: int) -> list[LeadCandidate]:
    leads = list(existing)
    seen = {_domain_from_url(lead.website) or lead.fund_name.lower() for lead in leads}
    for target in sorted(CURATED_VC_TARGETS, key=lambda item: item["relevance_score"], reverse=True):
        if len(leads) >= count:
            break
        key = _domain_from_url(target["website"]) or target["fund_name"].lower()
        if key in seen:
            continue
        seen.add(key)
        leads.append(LeadCandidate(
            fund_name=target["fund_name"],
            website=target["website"],
            geography=target["geography"],
            fund_type=target["fund_type"],
            relevance_score=target["relevance_score"],
            likely_contact_person=target["likely_contact_person"],
            contact_person_confidence=target["contact_person_confidence"],
            contact_person_source_url="",
            contact_role=target["contact_role"],
            public_email="",
            email_confidence="not_found",
            hunter_attempted=False,
            hunter_response_code="not_called",
            email_source_snippet="",
            contact_method="contact_form",
            linkedin_or_contact_url=target["website"],
            source_url=target["website"],
            fetch_status="not_attempted",
            fetch_verified=False,
            validation_note="",
            outreach_angle=target["outreach_angle"],
            thesis_fit_reason=target["thesis_fit_reason"],
            confidence="Medium",
        ))
    return sorted(leads, key=lambda lead: lead.relevance_score, reverse=True)[:count]


def _missing_data_notes(leads: list[LeadCandidate], requested_count: int) -> str:
    notes = []
    not_found = [lead.fund_name for lead in leads if lead.email_status in {"unavailable", "provider_unavailable", "low_confidence"}]
    provider_unavailable = [lead.fund_name for lead in leads if lead.email_status == "provider_unavailable"]
    low_confidence = [lead.fund_name for lead in leads if lead.email_status == "low_confidence"]
    failed = [lead.fund_name for lead in leads if lead.fetch_status == "failed"]
    if not_found:
        notes.append(f"No verified email is exported for {len(not_found)} lead(s); use first_action and manual review instead of direct email outreach.")
    if provider_unavailable:
        notes.append(f"Email provider was unavailable, not configured, rate-limited, or failed for {len(provider_unavailable)} lead(s); see validation_flags for provider status.")
    if low_confidence:
        notes.append(f"Low-confidence or inferred email candidates were blocked for {len(low_confidence)} lead(s).")
    if failed:
        notes.append(f"Official-page fetch failed for {len(failed)} leads; verify those contact routes manually before outreach.")
    if len(leads) < requested_count:
        notes.append(f"Only {len(leads)} validated leads were returned after filtering weak or unsafe candidates.")
    notes.append("Blogs, directories, LinkedIn pages, newsletters, and search-result pages are treated as discovery sources, not primary evidence URLs.")
    return " ".join(f"{index + 1}. {note}" for index, note in enumerate(notes))


def _self_check(
    leads: list[LeadCandidate],
    requested_count: int,
    candidate_count: int,
    csv_text: str,
    missing_data_notes: str,
) -> list[str]:
    notes = []
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    header = rows[0].keys() if rows else next(csv.reader(io.StringIO(csv_text)), [])
    missing_columns = [column for column in CSV_COLUMNS if column not in header]
    if not missing_columns:
        notes.append("PASS: Required CSV columns are present.")
    else:
        notes.append(f"WARN: Required CSV columns missing: {', '.join(missing_columns)}.")
    if len(leads) == requested_count:
        notes.append(f"PASS: Final output has exactly {requested_count} lead rows.")
    elif candidate_count >= requested_count:
        notes.append(f"WARN: {candidate_count} validated candidates existed but final output has {len(leads)} rows.")
    else:
        notes.append(f"WARN: Only {candidate_count} validated candidates were available for {requested_count} requested rows.")
    if all("asif" not in f"{lead.fund_name} {lead.website} {lead.evidence_url}".lower() for lead in leads):
        notes.append("PASS: Self-reference check found no ASIF lead rows.")
    else:
        notes.append("WARN: ASIF self-reference found in lead rows.")
    if all(not _is_linkedin_url(lead.evidence_url or lead.source_url) for lead in leads):
        notes.append("PASS: evidence_url contains no LinkedIn URLs.")
    else:
        notes.append("WARN: LinkedIn URL found in evidence_url.")
    weak_primary = [
        lead.fund_name for lead in leads
        if _evidence_quality_score(lead) == 0
        or _is_secondary_source({"url": lead.evidence_url or lead.source_url})
    ]
    if weak_primary:
        notes.append(f"WARN: Weak primary evidence URL in CSV: {', '.join(weak_primary)}.")
    else:
        notes.append("PASS: evidence_url uses official or high-quality primary sources.")
    unsafe_emails = [row.get("fund_name", "") for row in rows if row.get("email") and row.get("email_status") != "verified"]
    if unsafe_emails:
        notes.append(f"WARN: Non-verified email exported as usable: {', '.join(unsafe_emails)}.")
    else:
        notes.append("PASS: Inferred or low-confidence emails are not exported in the email column.")
    inferred_usable = [
        row.get("fund_name", "") for row in rows
        if row.get("email_status") in {"low_confidence", "provider_unavailable", "unavailable", "blocked"}
        and row.get("validation_status") == "usable"
    ]
    if inferred_usable:
        notes.append(f"WARN: Non-verified email route marked usable: {', '.join(inferred_usable)}.")
    else:
        notes.append("PASS: validation_status=usable requires verified email and strong evidence.")
    missing_row_validation = [
        row.get("fund_name", "") for row in rows
        if not row.get("route_quality") or not row.get("first_action") or not row.get("validation_status") or not row.get("validation_flags")
    ]
    if missing_row_validation:
        notes.append(f"WARN: Row-level validation fields missing: {', '.join(missing_row_validation)}.")
    else:
        notes.append("PASS: Every row has route_quality, first_action, validation_status, and validation_flags.")
    try:
        ranks = [int(row.get("priority_rank", "0")) for row in rows]
    except ValueError:
        ranks = []
    if ranks and ranks == sorted(ranks) and ranks == list(range(1, len(rows) + 1)):
        notes.append("PASS: priority_rank is deterministic and sorted.")
    else:
        notes.append("WARN: priority_rank is missing or not sorted.")
    route_gaps = [
        lead.fund_name for lead in leads
        if lead.email_status != "verified"
        and not (
            (lead.contact_method == "contact_form" and lead.linkedin_or_contact_url)
            or (lead.contact_method == "website" and (lead.linkedin_or_contact_url or lead.website))
            or lead.contact_method == "warm_intro_needed"
        )
    ]
    if route_gaps:
        notes.append(f"WARN: Missing public route or explicit warm intro: {', '.join(route_gaps)}.")
    else:
        notes.append("PASS: Every lead has email, contact form, website route, or warm_intro_needed.")
    duplicate_keys = Counter(_domain_from_url(lead.website) or lead.fund_name.lower() for lead in leads)
    duplicates = [key for key, total in duplicate_keys.items() if key and total > 1]
    if duplicates:
        notes.append(f"WARN: Duplicate fund rows remain after merge: {', '.join(duplicates)}.")
    else:
        notes.append("PASS: Duplicate fund rows are merged by domain/name before ranking.")
    missing_lower = missing_data_notes.lower()
    contradictions = []
    if all(lead.email_status == "verified" for lead in leads) and "no verified email" in missing_lower:
        contradictions.append("email note says missing emails although every row has an email")
    if len(leads) >= requested_count and "only " in missing_lower and "validated leads were returned" in missing_lower:
        contradictions.append("row-count note says fewer leads although requested count was met")
    if contradictions:
        notes.append(f"WARN: Missing Data Notes contradiction: {'; '.join(contradictions)}.")
    else:
        notes.append("PASS: Missing Data Notes match the table.")
    return notes


def _clean_csv_value(value):
    if not isinstance(value, str):
        return value
    cleaned = html.unescape(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _to_csv(leads: list[LeadCandidate]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    columns = _csv_columns(leads)
    writer.writerow(columns)
    for index, lead in enumerate(leads, start=1):
        if not lead.validation_status or not lead.validation_flags:
            _apply_outreach_review_fields(lead, strict_student=False, priority_rank=lead.priority_rank or index)
        row = {
            "priority_rank": lead.priority_rank,
            "fund_name": lead.fund_name,
            "website": lead.website,
            "geography": lead.geography,
            "fund_type": lead.fund_type,
            "fit_score": lead.fit_score or _derive_fit_score(lead),
            "route_quality": lead.route_quality or _derive_route_quality(lead),
            "contact_name": lead.contact_name or lead.likely_contact_person or "Fund Team",
            "contact_role": lead.contact_role,
            "contact_confidence": lead.contact_confidence or lead.contact_person_confidence or "Low",
            "linkedin_profile_url": lead.linkedin_profile_url or "",
            "email": lead.email if (lead.email_status or _derive_email_status(lead)) == "verified" else "",
            "email_status": lead.email_status or _derive_email_status(lead),
            "contact_method": lead.contact_method,
            "contact_url": lead.contact_url or lead.linkedin_or_contact_url or lead.website,
            "evidence_url": lead.evidence_url or _primary_evidence_url(lead),
            "evidence_summary": lead.evidence_summary or _derive_evidence_summary(lead),
            "outreach_angle": lead.outreach_angle,
            "suggested_subject": lead.suggested_subject or _derive_suggested_subject(lead),
            "first_action": lead.first_action or _derive_first_action(
                lead,
                lead.validation_status or _derive_validation_status(
                    lead,
                    lead.fit_score or _derive_fit_score(lead),
                    lead.route_quality or _derive_route_quality(lead),
                    lead.email_status or _derive_email_status(lead),
                ),
                lead.email_status or _derive_email_status(lead),
            ),
            "validation_status": lead.validation_status,
            "validation_flags": lead.validation_flags,
            "is_student_run": lead.is_student_run,
        }
        writer.writerow([_clean_csv_value(row[column]) for column in columns])
    return buffer.getvalue().strip()


def _render_markdown(result: LeadList, csv_text: str, sources: list[dict], project_context: str) -> str:
    date_str = datetime.now().strftime("%d %B %Y")
    rows = []
    for lead in result.leads:
        rows.append("| " + " | ".join([
            str(lead.priority_rank),
            str(lead.fit_score),
            lead.route_quality,
            lead.validation_status,
            lead.fund_name,
            lead.geography,
            lead.contact_name or "Fund Team",
            lead.contact_role or "Fund Team",
            lead.email or "Not verified",
            lead.email_status,
            lead.contact_method,
            lead.first_action,
            lead.outreach_angle,
        ]) + " |")
    table = "\n".join(rows)
    primary_evidence = "\n".join(
        f"- {lead.priority_rank}. [{lead.fund_name}]({lead.evidence_url}) - {lead.evidence_summary}"
        for lead in result.leads
        if lead.evidence_url
    ) or "- No primary evidence URLs passed validation."
    seen_sources = set()
    source_lines_list = []
    for source in sources:
        url = source.get("url")
        if not url or url in seen_sources:
            continue
        seen_sources.add(url)
        source_lines_list.append(f"- [{source.get('title') or url}]({url})")
    source_lines = "\n".join(source_lines_list)
    validation_lines = "\n".join(f"- {note}" for note in result.validation_notes) or "- No validation notes generated."
    secondary_lines = "\n".join(
        f"- [{source.get('title') or source.get('url')}]({source.get('url')})"
        for source in result.secondary_sources
        if source.get("url")
    ) or "- No secondary sources separated."

    table_header = "| Rank | Fit | Route | Validation | Fund | Geography | Contact | Role | Email | Email status | Method | First action | Outreach angle |"
    table_divider = "|---:|---:|:---:|---|---|---|---|---|---|---|---|---|---|"

    return f"""# VC Lead Finder - {date_str}

## Project Context
{project_context}

## Search Strategy
{result.search_strategy}

## Ranked Leads
{table_header}
{table_divider}
{table}

## Primary Evidence
{primary_evidence}

## CSV
```csv
{csv_text}
```

## Validation Notes
{validation_lines}

## Missing Data Notes
{result.missing_data_notes}

## Secondary Sources
{secondary_lines}

## Discovery Sources
{source_lines or "No source URLs returned."}

---
Generated by AI-OS on {date_str}
"""


def _rank_leads(
    system: str,
    user: str,
    schema: type[LeadList],
    count: int,
    search_text: str,
) -> LeadList:
    compact_instruction = """

Output format rules — every row must pass all of these:
- thesis_fit_reason: 1 sentence max. Must name something concrete (investment count, fund vintage, named portfolio company, sector focus, or fund structure). Reject: "European student-run VC with structured process." Accept: "LP-backed student VC with 28 investments and formal IC — directly comparable to ASIF's structure."
- outreach_angle: 1 sentence max. Must contain at least one verifiable specific: founding year, named portfolio company, investment count, fund size, named program, LP type, or named team member. Reject: "Student-run peer for benchmarking." Accept: "DSIF, founded 2016 with a dedicated Portfolio Director, is the closest Dutch peer for KPI benchmarking."
- If you cannot write a specific outreach_angle, set relevance_score below 60 and note the gap in missing_data_notes instead of writing a generic angle.
- missing_data_notes: max 4 short notes, each under 15 words.
- source_url: must be a fund website, team page, portfolio page, or thesis page. Never a LinkedIn URL, blog, directory, newsletter, or search results page.
- public_email: leave empty unless the exact address appears verbatim in the evidence. Never infer from name + domain.
- contact_person_confidence: High = named person on official fund team/people page. Medium = named person referenced in evidence only. Low = no named person found. No other values.
- contact_method: exactly one of email_direct, contact_form, website, linkedin_dm, warm_intro_needed. Use linkedin_dm only when no fund website or contact form exists at all.
- fetch_status: always not_attempted (overwritten downstream).
- is_student_run: false for university-managed endowments, professionally run academic funds, or alumni funds with no active student decision-making role.
- Return distinct external organizations only. Never include the client itself.
- Return exactly the requested count when sufficient evidence exists.
"""
    try:
        return call_claude_structured(
            system,
            user + compact_instruction,
            schema=schema,
            max_tokens=8000,
        )
    except ValueError:
        fallback_count = min(count, 10)
        short_evidence = search_text[:9000]
        fallback_user = f"""{user.split("Search evidence:")[0]}
Return up to {fallback_count} leads.

Search evidence:
{short_evidence}

Critical retry rules:
- Return shorter JSON.
- Do not include markdown.
- Every field must close cleanly.
- Keep all long text fields under 180 characters."""
        return call_claude_structured(
            system,
            fallback_user + compact_instruction,
            schema=schema,
            max_tokens=6000,
        )


def vc_lead_scraper(
    project_context: str,
    target_profile: str,
    lead_count: str = "20",
    geography: str = "",
    must_include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict:
    try:
        parsed_count = int(lead_count or "20")
    except (TypeError, ValueError):
        parsed_count = 20
    count = max(5, min(parsed_count, 30))
    model_count = count
    include_text = ", ".join(must_include or [])
    exclude_text = ", ".join(exclude or [])
    context = project_context.strip() or ASIF_DEFAULT_CONTEXT
    strict_student = _strict_student_fund_requested(context, target_profile, geography)

    if strict_student:
        queries = [
            f"{target_profile} {geography} student-run venture capital fund contact",
            f"{target_profile} {geography} venture capital fund team contact",
            f"{geography} student investment fund venture capital contact email",
            f"{geography} university venture capital fund contact portfolio",
            f"{geography} student-led VC fund portfolio monitoring benchmarking",
            f"{geography} campus fund student investors contact email",
            "Europe student run VC fund contact email",
            "Netherlands UK Germany Switzerland Nordics student VC fund",
            f"{geography} academic seed fund student founders contact",
        ]
    else:
        queries = [
            f"{target_profile} {geography} VC fund contact thesis portfolio",
            f"{target_profile} {geography} venture capital fund team contact",
            f"{geography} seed Series A VC B2B SaaS AI automation thesis contact",
            f"{geography} vertical AI workflow software venture capital contact",
            f"{geography} productivity tooling operational software VC portfolio contact",
            f"{geography} B2B SaaS AI infrastructure venture capital fund contact",
            "Europe seed Series A VC AI automation B2B SaaS contact",
            "UK Benelux B2B SaaS AI venture capital fund thesis contact",
        ]
    num_results = max(8, count // 2)
    raw_results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for batch in executor.map(lambda q: _exa_search(q, num_results), queries):
            raw_results.extend(batch)

    search_text = "\n\n".join(
        f"Title: {r.get('title')}\nURL: {r.get('url')}\nText: {r.get('text')}"
        for r in raw_results
    )

    system = """You are a senior BD analyst preparing a lead list that will be reviewed by a skeptical partner before any outreach is sent. Every row you return must be defensible. If you cannot defend a lead's fit, contact route, or outreach angle with specific evidence from the provided search results, do not include it.

Lead quality rules:
- Only include real VC funds, investment funds, student-run funds, or relevant fund operators with a verifiable web presence.
- Never include the project client or subject itself as a lead.
- Never include databases, blogs, directories, newsletters, or media outlets as leads — they may appear in missing_data_notes only.
- Rank by specific fit for the stated project, not by fund size or name recognition.
- A lead with a named, reachable contact beats a famous fund with only a generic inbox every time.

Contact route rules:
- Never invent or infer email addresses. If no exact public email appears in the evidence, leave public_email empty.
- Prefer named individuals (Partner, Investment Director, Portfolio Manager) over "Fund Team" or generic inboxes whenever evidence supports it.
- contact_person_confidence must be High (named person found on official team/people page), Medium (named person referenced in evidence but not on official page), or Low (no named person found).
- contact_method must be exactly one of: email_direct, contact_form, website, linkedin_dm, warm_intro_needed.
- Use linkedin_dm only when no fund website or contact form exists at all.
- email_confidence in model output must be publicly_listed (exact email visible in evidence) or not_found. Do not use any other value — downstream provider checks handle enrichment.
- Never use a LinkedIn URL as source_url. Use fund websites, team pages, portfolio pages, or thesis pages only.

Outreach angle rules — this is the most important field:
- Every outreach_angle must contain at least one specific, verifiable fact about this fund: founding year, named portfolio company, investment count, fund size, named program, LP structure, or named team member.
- BAD: "Student-run VC peer for benchmarking." (generic, interchangeable with any student fund)
- BAD: "Early-stage European fund with relevant portfolio." (could describe 200 funds)
- GOOD: "DSIF, founded 2016 with a dedicated Portfolio Director role, is the closest Dutch student-fund peer for ASIF's KPI benchmarking scope."
- GOOD: "G. Ventures has backed 100+ student founders since 2016 — their reporting templates are directly comparable to ASIF's early-stage portfolio."
- If you cannot write a specific angle, lower the relevance_score below 60 and note it in missing_data_notes.

thesis_fit_reason rules:
- Must reference something concrete: fund vintage, investment count, sector focus, named portfolio company, or fund structure.
- BAD: "European student-run VC with structured investment process." (every student fund could claim this)
- GOOD: "LP-backed student VC with 28 investments and a formal IC process — directly comparable to ASIF's fund structure and reporting needs."

Scoring rules:
- Leads with a named contact + verified or publicly listed email score highest.
- Leads where the only route is warm_intro_needed score lowest — include only if fit is exceptional (relevance_score ≥ 80).
- Deprioritize leads where the only evidence is a LinkedIn page or a directory listing."""

    user = f"""Build a ranked lead list for this project.

Project context:
{context}

Target VC profile:
{target_profile}

Geography:
{geography or "Any relevant geography"}

Must include / filters:
{include_text or "None"}

Exclude:
{exclude_text or "None"}

Return exactly {model_count} leads when enough evidence exists. Deterministic validation will backfill weak rows if needed.

Search evidence:
{search_text}"""

    lead_list = _rank_leads(system, user, LeadList, model_count, search_text)
    lead_list.leads = _dedupe_leads([
        lead for lead in sorted(lead_list.leads, key=lambda lead: lead.relevance_score, reverse=True)
        if _is_external_fund_lead(lead)
    ])
    lead_list.leads = _enrich_contacts(lead_list.leads, search_text, raw_results)
    lead_list.leads = [
        lead for lead in lead_list.leads
        if _is_external_fund_lead(lead)
    ]
    if len(lead_list.leads) < count and strict_student:
        backfilled = _curated_backfill(lead_list.leads, count)
        lead_list.leads = _enrich_contacts(backfilled, search_text, raw_results)
    validated_candidates = [
        lead for lead in _dedupe_leads(sorted(lead_list.leads, key=lambda lead: lead.relevance_score, reverse=True))
        if _is_validated_lead(lead)
    ]
    lead_list.leads = _select_final_leads(validated_candidates, count, context, target_profile, geography)
    needs_diverse_backfill = (
        _should_rebalance_geography(context, target_profile, geography)
        and _over_geography_cap(lead_list.leads)
    )
    needs_student_backfill = (
        _strict_student_fund_requested(context, target_profile, geography)
        and any(_professional_filler(lead) for lead in lead_list.leads)
    )
    if strict_student and (len(lead_list.leads) < count or needs_diverse_backfill or needs_student_backfill):
        backfilled = _curated_backfill(validated_candidates, count + 10)
        backfilled = _enrich_contacts(backfilled, search_text, raw_results)
        validated_candidates = [
            lead for lead in _dedupe_leads(sorted(backfilled, key=lambda lead: lead.relevance_score, reverse=True))
            if _is_validated_lead(lead)
        ]
        lead_list.leads = _select_final_leads(validated_candidates, count, context, target_profile, geography)
    lead_list.leads = _sanitize_leads_for_output(lead_list.leads)
    lead_list.leads = _finalize_outreach_rows(lead_list.leads, strict_student)
    lead_list.validation_notes = _validation_notes(lead_list.leads, count, strict_student)
    lead_list.secondary_sources = _secondary_sources(raw_results)
    lead_list.missing_data_notes = _missing_data_notes(lead_list.leads, count)

    csv_text = _to_csv(lead_list.leads)
    lead_list.validation_notes.extend(_self_check(
        lead_list.leads,
        count,
        len(validated_candidates),
        csv_text,
        lead_list.missing_data_notes,
    ))
    md = _render_markdown(lead_list, csv_text, raw_results, context)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vc_leads_{timestamp}.md"
    csv_filename = f"vc_leads_{timestamp}.csv"
    file_path = save_output(md, "outreach", filename)
    csv_file_path = save_output(csv_text + "\n", "outreach", csv_filename)

    return {
        "brief": md,
        "csv": csv_text,
        "leads_found": len(lead_list.leads),
        "file_path": str(file_path),
        "csv_file_path": str(csv_file_path),
        "sources": list(dict.fromkeys(r.get("url", "") for r in raw_results if r.get("url"))),
    }
