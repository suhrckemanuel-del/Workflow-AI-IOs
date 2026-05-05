"""
WORKFLOW: VC Outreach Drafts
----------------------------
INPUT:   Reviewed VC Lead Finder CSV rows + campaign context
PROCESS: Claude-written, evidence-aware drafts for email and LinkedIn channels
OUTPUT:  Markdown brief and review queue CSV saved to knowledge_base/outreach/drafts/

Channels produced per lead:
  • Email first touch  — unique hook + 3-bullet body
  • Email follow-up    — sent if no reply after 5 days
  • LinkedIn connect   — blank request (no message)
  • LinkedIn DM        — sent after connection accepted

No sending, no enrichment, no browser. Manual-review drafts only.
"""

import csv
import html
import io
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))
from core.engine import call_claude_structured, save_output


MAX_DRAFTS = 5
REVIEW_QUEUE_COLUMNS = [
    "review_status",
    "fund_name",
    "contact_name",
    "contact_method",
    "email",
    "email_status",
    "evidence_url",
    "missing_evidence",
    "email_subject",
    "email_first_touch",
    "email_follow_up",
    "linkedin_connect_note",
    "linkedin_dm",
    "personalization_rationale",
    "manual_send_checklist",
]
WEAK_EVIDENCE_MARKERS = (
    "linkedin.com",
    "openvc.app",
    "lusha.com",
    "parsers.vc",
    "goldeneggcheck.com",
    "privateequityinternational.com",
    "/blog/",
    "/directory/",
)
BLOCKING_FLAGS = (
    "weak_or_missing_primary_evidence",
    "email_blocked",
)
REVIEW_FLAGS = (
    "no_verified_email",
    "provider_unavailable",
    "email_low_confidence",
    "weak_contact_route",
    "homepage_only_route",
    "contact_person_unverified",
)


# ---------------------------------------------------------------------------
# Pydantic schema for Claude output
# ---------------------------------------------------------------------------

class OutreachDraftResult(BaseModel):
    email_subject: str = Field(description="Email subject line. Direct and specific, no clickbait.")
    email_first_touch: str = Field(
        description=(
            "Full email body for the first touch. "
            "Structure: greeting → 1-sentence unique hook specific to this fund → exactly 3 tight bullet points → CTA. "
            "No fluff. Under 150 words total."
        )
    )
    email_follow_up: str = Field(
        description=(
            "Short follow-up email sent if no reply after 5 days. "
            "3 lines max. Reference the specific fund. Soft CTA. Under 60 words."
        )
    )
    linkedin_connect_note: str = Field(
        description="ALWAYS return an empty string. The connection request is sent with no message.",
        default="",
    )
    linkedin_dm: str = Field(
        description=(
            "Short LinkedIn DM sent after the connection is accepted. "
            "2-3 sentences. Casual, not salesy. Reference one specific thing about the fund."
        )
    )
    personalization_rationale: str = Field(
        description="1-2 sentences explaining what specific evidence drove the hook and angle chosen."
    )
    bullet_angle_tags: list[str] = Field(
        description="List of exactly 3 short tags (3-5 words each) summarising the angle of each bullet. Used to avoid repetition across leads.",
        default_factory=list,
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _strip_code_fence(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_lead_rows(lead_data: str) -> list[dict[str, str]]:
    text = _strip_code_fence(lead_data)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        normalized = {
            (key or "").strip(): html.unescape(str(value or "")).strip()
            for key, value in row.items()
            if key
        }
        if normalized.get("fund_name"):
            rows.append(normalized)
    return rows


def _parse_max_drafts(value: str) -> int:
    try:
        parsed = int(value or MAX_DRAFTS)
    except (TypeError, ValueError):
        parsed = MAX_DRAFTS
    return max(1, min(parsed, MAX_DRAFTS))


def _is_weak_evidence(url: str) -> bool:
    lower = (url or "").lower()
    if not lower:
        return True
    return any(marker in lower for marker in WEAK_EVIDENCE_MARKERS)


def _split_flags(row: dict[str, str]) -> list[str]:
    flags = row.get("validation_flags", "")
    if not flags or flags.lower() == "none":
        return []
    return [flag.strip() for flag in flags.split(";") if flag.strip()]


def _missing_evidence(row: dict[str, str]) -> list[str]:
    missing = []
    if _is_weak_evidence(row.get("evidence_url", "")):
        missing.append("strong_primary_evidence_url")
    if not row.get("evidence_summary"):
        missing.append("evidence_summary")
    if row.get("email_status") != "verified" and not row.get("contact_url"):
        missing.append("contact_route")
    return missing


def _review_status(row: dict[str, str]) -> tuple[str, list[str]]:
    flags = _split_flags(row)
    missing = _missing_evidence(row)
    validation_status = row.get("validation_status", "").lower()
    route_quality = row.get("route_quality", "").upper()

    is_blocked = (
        validation_status == "blocked"
        or route_quality == "D"
        or any(any(marker in flag for marker in BLOCKING_FLAGS) for flag in flags)
        or bool(missing)
    )
    if is_blocked:
        return "blocked", missing

    has_review_flags = any(any(marker in flag for marker in REVIEW_FLAGS) for flag in flags)
    if validation_status != "usable" or has_review_flags:
        return "needs_review", missing

    return "ready", missing


def _shorten(value: str, limit: int = 150) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_first_name(row: dict[str, str]) -> str:
    name = row.get("contact_name") or row.get("likely_contact_person") or ""
    if name.lower() in {"fund team", "investment team", "team", ""}:
        return "there"
    return name.split()[0]


def _manual_checklist(row: dict[str, str], review_status: str, missing: list[str]) -> list[str]:
    checklist = [
        "Open evidence_url and confirm the fund thesis still matches.",
        "Confirm recipient is correct before sending.",
        "Read the email aloud — remove any sentence that feels generic or copied.",
    ]
    if row.get("email_status") != "verified":
        checklist.append("Verify email address before sending.")
    if missing:
        checklist.append(f"Resolve missing evidence: {', '.join(missing)}.")
    if review_status == "blocked":
        checklist.append("DO NOT send — blocked until evidence/contact issues are fixed.")
    elif review_status == "needs_review":
        checklist.append("Send only after final human review.")
    else:
        checklist.append("Ready — send after a final read-through.")
    return checklist


def _with_compat_fields(draft: dict, row: dict[str, str]) -> dict:
    """Expose stable aliases used by the frontend and regression tests."""
    subject = draft.get("email_subject") or row.get("suggested_subject", "")
    fallback_subject = f"{draft.get('fund_name') or row.get('fund_name') or 'VC fund'} follow-up"
    draft["subject_lines"] = [subject, fallback_subject] if subject else ["", fallback_subject]
    draft["first_touch_email"] = draft.get("email_first_touch", "")
    draft["follow_up"] = draft.get("email_follow_up", "")
    return draft


# ---------------------------------------------------------------------------
# Claude draft generation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a concise, evidence-driven outreach copywriter for B2B campaigns.

Given a specific fund/contact and campaign brief, produce personalised outreach drafts for two independent channels: email and LinkedIn. The two channels must NOT reference each other.

Rules:
- Email first touch: Hi [name], → 1-sentence unique hook → exactly 3 tight bullet points → CTA → sign-off. HARD LIMIT: 130 words maximum. Count words before returning. If over 130, cut adjectives, trim bullets to one clause each, shorten the hook.
- Email follow-up: 3 lines max. Casual. Fund name once. Soft CTA. HARD LIMIT: 50 words maximum.
- LinkedIn connect note: ALWAYS empty string "". Do not generate any message for the connection request.
- LinkedIn DM (after accepted): 2-3 sentences. Casual. HARD LIMIT: 50 words maximum.
- Subject line: short, specific, uses the contact name or fund name. No questions, no "quick".
- Never fabricate fund facts. Only use the evidence provided.
- Never mention tools, systems, or software unless specified in the campaign context.
- Adapt sender tone and framing entirely from the sender_context field.

HOOK SPECIFICITY GATE — the opening hook sentence MUST reference a fact that is unique to this specific fund and not generic to all funds. Disqualified hooks contain ONLY these generic phrases without an additional differentiator: "student-run VC", "pre-seed fund", "peer fund", "fellow fund", "early-stage fund". A good hook adds: founding year, investment count, geographic specificity, named role, org structure detail, LP structure, or named program. If evidence is thin, use the fund's country and specific stage focus as the differentiator.

BULLET UNIQUENESS — each lead in a batch must use different bullet angles. The prior_bullet_angles field lists angles already used. Do NOT repeat them. Choose 3 angles not in that list."""


def _count_words(text: str) -> int:
    return len((text or "").split())


def _trim_to_limit(text: str, word_limit: int, field_name: str, fund_name: str) -> str:
    if _count_words(text) <= word_limit:
        return text
    try:
        from core.engine import call_claude
        trimmed = call_claude(
            system="You are a copyeditor. Shorten the following text to fit within the word limit. Preserve the meaning and tone exactly. Return only the shortened text, no explanation.",
            user=f"Shorten to under {word_limit} words:\n\n{text}",
            max_tokens=400,
        )
        return trimmed.strip()
    except Exception:
        words = text.split()
        return " ".join(words[:word_limit])


def _compose_draft_with_claude(
    row: dict[str, str],
    campaign_context: str,
    sender_name: str,
    sender_context: str,
    outreach_goal: str,
    call_to_action: str,
    used_bullet_angles: list[str] | None = None,
) -> OutreachDraftResult:
    first_name = _safe_first_name(row)
    fund_name = row.get("fund_name", "the fund")
    evidence_summary = _shorten(row.get("evidence_summary", ""), 300)
    outreach_angle = _shorten(row.get("outreach_angle", ""), 300)
    geography = row.get("geography", "")
    fund_type = row.get("fund_type", "")

    prior_angles_text = ""
    if used_bullet_angles:
        prior_angles_text = f"\nPRIOR BULLET ANGLES (already used — do NOT repeat): {'; '.join(used_bullet_angles)}\n"

    user_prompt = f"""FUND: {fund_name}
CONTACT FIRST NAME: {first_name}
FUND TYPE: {fund_type}
GEOGRAPHY: {geography}
EVIDENCE SUMMARY: {evidence_summary}
OUTREACH ANGLE: {outreach_angle}

SENDER NAME: {sender_name}
SENDER CONTEXT: {_shorten(sender_context, 200)}
CAMPAIGN CONTEXT: {_shorten(campaign_context, 250)}
OUTREACH GOAL: {_shorten(outreach_goal, 200)}
CALL TO ACTION: {call_to_action}
{prior_angles_text}
Write the outreach drafts now."""

    result = call_claude_structured(
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        schema=OutreachDraftResult,
        max_tokens=1400,
    )

    # Enforce word count limits — trim if over
    if _count_words(result.email_first_touch) > 150:
        result.email_first_touch = _trim_to_limit(
            result.email_first_touch, 150, "email_first_touch", fund_name
        )
    if _count_words(result.email_follow_up) > 60:
        result.email_follow_up = _trim_to_limit(
            result.email_follow_up, 60, "email_follow_up", fund_name
        )
    if _count_words(result.linkedin_dm) > 60:
        result.linkedin_dm = _trim_to_limit(
            result.linkedin_dm, 60, "linkedin_dm", fund_name
        )

    return result


def _compose_draft(
    row: dict[str, str],
    campaign_context: str,
    sender_name: str,
    sender_context: str,
    outreach_goal: str,
    call_to_action: str,
    review_status: str,
    missing: list[str],
    used_bullet_angles: list[str] | None = None,
) -> tuple[dict, list[str]]:
    fund_name = row.get("fund_name", "the fund")
    checklist = _manual_checklist(row, review_status, missing)
    evidence_url = row.get("evidence_url", "")

    if review_status == "blocked":
        draft = {
            "fund_name": fund_name,
            "review_status": review_status,
            "email_subject": row.get("suggested_subject", ""),
            "email_first_touch": "",
            "email_follow_up": "",
            "linkedin_connect_note": "",
            "linkedin_dm": "",
            "personalization_rationale": _shorten(row.get("outreach_angle", ""), 300),
            "evidence_used": [evidence_url] if evidence_url else [],
            "missing_evidence": missing,
            "manual_send_checklist": checklist,
        }
        return _with_compat_fields(draft, row), used_bullet_angles or []

    try:
        result = _compose_draft_with_claude(
            row=row,
            campaign_context=campaign_context,
            sender_name=sender_name,
            sender_context=sender_context,
            outreach_goal=outreach_goal,
            call_to_action=call_to_action,
            used_bullet_angles=used_bullet_angles,
        )
        new_angles = (used_bullet_angles or []) + (result.bullet_angle_tags or [])
        draft = {
            "fund_name": fund_name,
            "review_status": review_status,
            "email_subject": result.email_subject,
            "email_first_touch": result.email_first_touch,
            "email_follow_up": result.email_follow_up,
            "linkedin_connect_note": "",
            "linkedin_dm": result.linkedin_dm,
            "personalization_rationale": result.personalization_rationale,
            "evidence_used": [evidence_url] if evidence_url else [],
            "missing_evidence": missing,
            "manual_send_checklist": checklist,
        }
        return _with_compat_fields(draft, row), new_angles
    except Exception as exc:
        draft = {
            "fund_name": fund_name,
            "review_status": "needs_review",
            "email_subject": row.get("suggested_subject", ""),
            "email_first_touch": f"[Draft generation failed: {exc}]",
            "email_follow_up": "",
            "linkedin_connect_note": "",
            "linkedin_dm": "",
            "personalization_rationale": "",
            "evidence_used": [evidence_url] if evidence_url else [],
            "missing_evidence": missing,
            "manual_send_checklist": checklist,
        }
        return _with_compat_fields(draft, row), used_bullet_angles or []


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _to_review_queue_csv(drafts: list[dict], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(REVIEW_QUEUE_COLUMNS)
    for draft, row in zip(drafts, rows):
        writer.writerow([
            draft.get("review_status", ""),
            draft.get("fund_name", ""),
            row.get("contact_name", ""),
            row.get("contact_method", ""),
            row.get("email", ""),
            row.get("email_status", ""),
            row.get("evidence_url", ""),
            "; ".join(draft.get("missing_evidence", [])),
            draft.get("email_subject", ""),
            draft.get("email_first_touch", ""),
            draft.get("email_follow_up", ""),
            draft.get("linkedin_connect_note", ""),
            draft.get("linkedin_dm", ""),
            draft.get("personalization_rationale", ""),
            " | ".join(draft.get("manual_send_checklist", [])),
        ])
    return buffer.getvalue().strip()


def _render_markdown(
    drafts: list[dict],
    rows: list[dict[str, str]],
    campaign_context: str,
    outreach_goal: str,
) -> str:
    date_str = datetime.now().strftime("%d %B %Y")
    sections = []
    for index, (draft, row) in enumerate(zip(drafts, rows), start=1):
        checklist = "\n".join(f"- {item}" for item in draft.get("manual_send_checklist", []))
        evidence = "\n".join(f"- {url}" for url in draft.get("evidence_used", [])) or "- Missing"
        missing = ", ".join(draft.get("missing_evidence", [])) or "None"
        first_touch = draft.get("email_first_touch") or "BLOCKED — no draft until evidence/contact issues are fixed."
        follow_up = draft.get("email_follow_up") or "BLOCKED — no follow-up until issues are fixed."
        linkedin_dm = draft.get("linkedin_dm") or "BLOCKED — no DM draft until issues are fixed."
        sections.append(f"""## {index}. {draft.get('fund_name')}
**Review status:** {draft.get('review_status')}
**Lead validation:** {row.get('validation_status', '')} / {row.get('validation_flags', '')}
**Evidence used:**
{evidence}
**Missing evidence:** {missing}

---

### Email Channel

**Subject:** {draft.get('email_subject', '')}

#### First Touch
{first_touch}

#### Follow-Up (send after 5 days — no reply)
{follow_up}

---

### LinkedIn Channel

#### Connection Request
*(Send blank — no message)*

#### DM (send after connection accepted)
{linkedin_dm}

---

### Personalization Rationale
{draft.get('personalization_rationale', '')}

### Manual Send Checklist
{checklist}
""")
    ready_count = sum(1 for d in drafts if d.get("review_status") == "ready")
    needs_review_count = sum(1 for d in drafts if d.get("review_status") == "needs_review")
    blocked_count = sum(1 for d in drafts if d.get("review_status") == "blocked")
    return f"""# Outreach Drafts — {date_str}

## Campaign Context
{campaign_context}

## Outreach Goal
{outreach_goal}

## Summary
- Drafts generated: {len(drafts)}
- Ready: {ready_count}
- Needs review: {needs_review_count}
- Blocked: {blocked_count}

{chr(10).join(sections)}---
Generated {date_str}
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def vc_outreach_drafts(
    lead_data: str,
    campaign_context: str,
    sender_name: str,
    sender_context: str,
    outreach_goal: str,
    call_to_action: str,
    max_drafts: str = "5",
) -> dict:
    rows = _parse_lead_rows(lead_data)[: _parse_max_drafts(max_drafts)]
    drafts = []
    used_bullet_angles: list[str] = []
    for row in rows:
        review_status, missing = _review_status(row)
        draft, used_bullet_angles = _compose_draft(
            row=row,
            campaign_context=campaign_context,
            sender_name=sender_name,
            sender_context=sender_context,
            outreach_goal=outreach_goal,
            call_to_action=call_to_action,
            review_status=review_status,
            missing=missing,
            used_bullet_angles=used_bullet_angles,
        )
        drafts.append(draft)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    markdown = _render_markdown(drafts, rows, campaign_context, outreach_goal)
    queue_csv = _to_review_queue_csv(drafts, rows)
    file_path = save_output(markdown, "outreach/drafts", f"vc_outreach_drafts_{timestamp}.md")
    review_queue_csv_path = save_output(
        queue_csv + "\n", "outreach/drafts", f"vc_outreach_review_queue_{timestamp}.csv"
    )

    ready_count = sum(1 for d in drafts if d.get("review_status") == "ready")
    needs_review_count = sum(1 for d in drafts if d.get("review_status") == "needs_review")
    blocked_count = sum(1 for d in drafts if d.get("review_status") == "blocked")

    return {
        "brief": markdown,
        "drafts": drafts,
        "review_queue_csv_path": str(review_queue_csv_path),
        "file_path": str(file_path),
        "ready_count": ready_count,
        "needs_review_count": needs_review_count,
        "blocked_count": blocked_count,
    }
