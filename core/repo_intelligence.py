"""
Repo Intelligence
-----------------
Finds open-source precedent for an automation project and turns it into
compact, implementation-oriented repo findings.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import requests
from pydantic import BaseModel, Field

from core.engine import call_claude_structured


class RepoFinding(BaseModel):
    url: str
    name: str
    description: str = ""
    fit_score: int = Field(ge=0, le=100)
    recommendation: str
    setup_clarity: str = ""
    reusable_patterns: list[str] = []
    useful_files: list[str] = []
    risks: list[str] = []
    notes: str = ""


class RepoFindingList(BaseModel):
    findings: list[RepoFinding]


def discover_repo_candidates(project: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    limit = max(3, min(limit, 10))
    queries = _build_queries(project)
    github_candidates = _github_search(queries, limit=limit)
    if not github_candidates:
        return []

    evidence = _exa_evidence(project, github_candidates[: min(len(github_candidates), 6)])
    analyzed = [] if project.get("_skip_llm") else _analyze_with_claude(project, github_candidates, evidence, limit)
    if not analyzed:
        analyzed = [_heuristic_finding(repo, project) for repo in github_candidates[:limit]]

    by_url = {_normalize_url(repo["html_url"]): repo for repo in github_candidates if repo.get("html_url")}
    rows = []
    policy_adjusted = [
        _apply_repo_policy(finding, by_url.get(_normalize_url(finding.url)), project)
        for finding in analyzed
    ]
    for idx, finding in enumerate(sorted(policy_adjusted, key=lambda item: item.fit_score, reverse=True)[:limit], start=1):
        repo = by_url.get(_normalize_url(finding.url))
        if not repo:
            continue
        analysis = {
            "name": finding.name,
            "description": finding.description,
            "setup_clarity": finding.setup_clarity,
            "reusable_patterns": finding.reusable_patterns[:6],
            "useful_files": finding.useful_files[:6],
            "risks": finding.risks[:6],
            "notes": finding.notes,
            "source": "github+web",
        }
        rows.append({
            "url": repo.get("html_url", finding.url),
            "notes": _compact_notes(finding),
            "rank": idx,
            "fit_score": finding.fit_score,
            "recommendation": _recommendation_for_score(finding.fit_score, finding.recommendation),
            "license": _license_name(repo),
            "stars": repo.get("stargazers_count"),
            "last_updated": repo.get("updated_at", ""),
            "language": repo.get("language") or "",
            "analysis_json": analysis,
        })
    if not rows and analyzed:
        fallback_project = {**project, "_skip_llm": True}
        return discover_repo_candidates(fallback_project, limit=limit)
    return rows


def _build_queries(project: dict[str, Any]) -> list[str]:
    goal = project.get("goal", "")
    tools = project.get("required_tools", "")
    process = project.get("current_process", "")
    base = " ".join([goal, tools, process])
    terms = _keywords(base)
    core = " ".join(terms[:8]) or goal or project.get("name", "automation")
    queries: list[str] = []
    lower = base.lower()
    if any(term in lower for term in ("lead", "leads", "contact", "contacts", "email", "emails", "outreach")):
        queries.extend([
            "python email finder contact page scraper csv",
            "website email extractor csv python",
            "hunter api email finder python",
            "lead enrichment csv python email",
            "company website contact scraper email",
        ])
    if any(term in lower for term in ("vc", "venture", "investor", "fund")):
        queries.extend([
            "investor database csv scraper python",
            "startup investor search api python",
            "venture capital data scraper python",
        ])
    queries.extend([
        f"{core} automation",
        f"{core} open source",
        f"{core} agent workflow",
    ])
    deduped = []
    for query in queries:
        if query not in deduped:
            deduped.append(query)
    return deduped


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "automation",
        "automations", "client", "clients", "should", "would", "could", "need",
    }
    ranked: dict[str, int] = {}
    for word in words:
        if word not in stop:
            ranked[word] = ranked.get(word, 0) + 1
    return [word for word, _ in sorted(ranked.items(), key=lambda item: (-item[1], item[0]))]


def _github_search(queries: list[str], limit: int) -> list[dict[str, Any]]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-os-repo-intelligence",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen: set[str] = set()
    repos: list[dict[str, Any]] = []
    for query in queries:
        q = quote_plus(f"{query} in:name,description,readme stars:>5 fork:false archived:false")
        try:
            response = requests.get(
                f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}",
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
        except Exception:
            continue
        for repo in response.json().get("items", []):
            url = repo.get("html_url")
            if not url or url in seen:
                continue
            if _should_skip_repo(repo):
                continue
            seen.add(url)
            repos.append(repo)
            if len(repos) >= limit * 2:
                return repos
    return repos


def _exa_evidence(project: dict[str, Any], repos: list[dict[str, Any]]) -> str:
    api_key = os.getenv("EXA_API_KEY")
    if not api_key or not repos:
        return ""

    names = ", ".join(repo.get("full_name", "") for repo in repos[:5])
    query = f"{project.get('goal', '')} open source implementation examples GitHub {names}"
    try:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": query, "numResults": 5, "contents": {"text": {"maxCharacters": 700}}},
            timeout=20,
        )
        response.raise_for_status()
    except Exception:
        return ""

    lines = []
    for result in response.json().get("results", []):
        lines.append(
            f"Title: {result.get('title', '')}\n"
            f"URL: {result.get('url', '')}\n"
            f"Text: {result.get('text', '')[:700]}"
        )
    return "\n\n".join(lines)


def _analyze_with_claude(
    project: dict[str, Any],
    repos: list[dict[str, Any]],
    evidence: str,
    limit: int,
) -> list[RepoFinding]:
    repo_lines = []
    for repo in repos[: limit * 2]:
        repo_lines.append(
            "\n".join([
                f"URL: {repo.get('html_url', '')}",
                f"Name: {repo.get('full_name', '')}",
                f"Description: {repo.get('description') or ''}",
                f"Stars: {repo.get('stargazers_count', 0)}",
                f"Language: {repo.get('language') or ''}",
                f"License: {_license_name(repo)}",
                f"Updated: {repo.get('updated_at', '')}",
            ])
        )

    system = """You analyze open-source repos for automation builders.
Return compact JSON only. Do not over-explain.
Score fit for the user's automation, not repo fame.
Recommendations must be one of: use_as_reference, adapt_patterns, fork_candidate, avoid.
Prefer reusable patterns/snippets over direct forking.
Never claim tests/setup work unless the evidence supports it."""

    user = f"""Project:
Name: {project.get('name', '')}
Goal: {project.get('goal', '')}
Current process: {project.get('current_process', '')}
Working definition: {project.get('working_definition', '')}
Required tools/data: {project.get('required_tools', '')}
Input examples: {project.get('input_examples', '')[:1000]}
Expected output examples: {project.get('output_examples', '')[:1000]}

Selection policy:
- Prefer runnable repos with implementation code, setup instructions, and reusable patterns.
- Penalize generic awesome lists, paper lists, newsletters, topic pages, and tool catalogs.
- If the project warns against LinkedIn scraping, do not rank LinkedIn session/cookie scrapers as usable references.
- Prefer official web/contact-page crawling, API integrations, CSV validation, and email-confidence handling over account scraping.

Candidate repos:
{"\n\n".join(repo_lines)}

Extra web evidence:
{evidence[:3000]}

Return up to {limit} findings. Keep each list to 3-5 short items."""

    try:
        result = call_claude_structured(system, user, schema=RepoFindingList, max_tokens=2200)
    except Exception:
        return []
    return result.findings


def _heuristic_finding(repo: dict[str, Any], project: dict[str, Any]) -> RepoFinding:
    text = " ".join([
        repo.get("full_name", ""),
        repo.get("description") or "",
        project.get("goal", ""),
        project.get("required_tools", ""),
    ]).lower()
    keyword_hits = sum(1 for word in _keywords(project.get("goal", ""))[:8] if word in text)
    stars = int(repo.get("stargazers_count") or 0)
    updated = repo.get("updated_at", "")
    year = _year(updated)
    score = min(95, 45 + keyword_hits * 6 + min(stars, 5000) // 250 + (10 if year >= 2025 else 4 if year >= 2023 else 0))
    if _is_reference_list(repo):
        score = min(score, 55)
    if _is_linkedin_scraper(repo) and _avoid_linkedin(project):
        score = min(score, 35)
    recommendation = "use_as_reference" if score >= 85 else "adapt_patterns" if score >= 70 else "avoid" if score < 50 else "adapt_patterns"
    risks = ["Heuristic analysis only; verify repo quality before reuse."]
    if _is_reference_list(repo):
        risks.append("Reference list rather than runnable automation code.")
    if _is_linkedin_scraper(repo):
        risks.append("LinkedIn scraping can be brittle and account-risky; do not use as the core v1 path.")
    return RepoFinding(
        url=repo.get("html_url", ""),
        name=repo.get("full_name", ""),
        description=repo.get("description") or "",
        fit_score=score,
        recommendation=recommendation,
        setup_clarity="Inspect README before relying on setup.",
        reusable_patterns=["Architecture", "Data model", "Integration approach"],
        useful_files=["README.md", "examples/", "src/"],
        risks=risks,
        notes="Ranked from GitHub metadata because LLM analysis was unavailable.",
    )


def _apply_repo_policy(finding: RepoFinding, repo: dict[str, Any] | None, project: dict[str, Any]) -> RepoFinding:
    if not repo:
        return finding

    score = finding.fit_score
    recommendation = finding.recommendation
    risks = list(finding.risks)
    notes = finding.notes

    if _is_reference_list(repo):
        score = min(score, 55)
        recommendation = "adapt_patterns" if score >= 50 else "avoid"
        _append_unique(risks, "Reference list or catalog; useful for source discovery, not implementation.")
        if not notes:
            notes = "Use only as a source map. Do not treat this as implementation precedent."

    if _is_linkedin_scraper(repo) and _avoid_linkedin(project):
        score = min(score, 35)
        recommendation = "avoid"
        _append_unique(risks, "LinkedIn session/cookie scraping conflicts with this project's reliability and account-safety constraints.")
        notes = "Avoid as a v1 implementation path; use official websites, contact pages, and APIs instead."

    if _year(repo.get("updated_at", "")) and _year(repo.get("updated_at", "")) < 2023:
        score = min(score, 65)
        _append_unique(risks, "Older repo; inspect dependency and target-site freshness before reuse.")

    return RepoFinding(
        url=finding.url,
        name=finding.name,
        description=finding.description,
        fit_score=score,
        recommendation=_recommendation_for_score(score, recommendation),
        setup_clarity=finding.setup_clarity,
        reusable_patterns=finding.reusable_patterns,
        useful_files=finding.useful_files,
        risks=risks,
        notes=notes,
    )


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _should_skip_repo(repo: dict[str, Any]) -> bool:
    return _is_reference_list(repo) or _looks_unrelated(repo)


def _is_reference_list(repo: dict[str, Any]) -> bool:
    text = _repo_text(repo)
    markers = (
        "awesome",
        "papers",
        "paper-list",
        "news-of-the-week",
        "tool-collection",
        "tool_collection",
        "collection",
        "curated list",
        "resources",
    )
    return any(marker in text for marker in markers)


def _looks_unrelated(repo: dict[str, Any]) -> bool:
    text = _repo_text(repo)
    unrelated = ("machine learning news", "event extraction papers", "awesome mcp")
    return any(marker in text for marker in unrelated)


def _is_linkedin_scraper(repo: dict[str, Any]) -> bool:
    text = _repo_text(repo)
    return "linkedin" in text and ("scrap" in text or "cookie" in text or "session" in text)


def _avoid_linkedin(project: dict[str, Any]) -> bool:
    text = " ".join(
        str(project.get(key, ""))
        for key in ("goal", "required_tools", "working_definition", "client_context", "output_examples")
    ).lower()
    return "avoid linkedin" in text or "linkedin account scraping" in text or "account-risk" in text


def _repo_text(repo: dict[str, Any]) -> str:
    return " ".join([
        repo.get("full_name", ""),
        repo.get("name", ""),
        repo.get("html_url", ""),
        repo.get("description") or "",
        repo.get("language") or "",
    ]).lower()


def _compact_notes(finding: RepoFinding) -> str:
    patterns = "; ".join(finding.reusable_patterns[:3]) or "Inspect for reusable implementation patterns."
    risks = "; ".join(finding.risks[:2]) or "No major risk identified from available evidence."
    return f"{finding.notes}\nReuse: {patterns}\nRisks: {risks}".strip()


def _license_name(repo: dict[str, Any]) -> str:
    license_obj = repo.get("license") or {}
    return license_obj.get("spdx_id") or license_obj.get("name") or ""


def _recommendation_for_score(score: int, preferred: str) -> str:
    allowed = {"use_as_reference", "adapt_patterns", "fork_candidate", "avoid"}
    if score < 50:
        return "avoid"
    if score < 70:
        return "adapt_patterns"
    if score < 85:
        return preferred if preferred in {"use_as_reference", "adapt_patterns"} else "adapt_patterns"
    return preferred if preferred in allowed and preferred != "avoid" else "use_as_reference"


def _normalize_url(url: str) -> str:
    return (url or "").strip().removesuffix("/").lower()


def _year(value: str) -> int:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except Exception:
        return 0
