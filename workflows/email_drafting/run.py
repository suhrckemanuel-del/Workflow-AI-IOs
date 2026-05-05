"""
WORKFLOW: Email Drafting
------------------------
INPUT:   Email type + recipient context + key points
CONTEXT: Email style guide from knowledge base
PROCESS: Claude drafts a personalised email in the sender's voice — structured output
OUTPUT:  Draft saved to knowledge_base/meetings/

EMAIL TYPES:
  intro_outreach | follow_up | investor_update | meeting_request | deck_request | custom
"""

import sys
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

sys.path.append(str(Path(__file__).parent.parent.parent))
from core.engine import call_claude_structured, load_context, save_output


# ── Pydantic schema ────────────────────────────────────────────────────────────

class EmailDraft(BaseModel):
    subject: str
    body: str


# ── Email type hints ───────────────────────────────────────────────────────────

EMAIL_CONTEXTS = {
    "intro_outreach":   "First contact. Goal: spark interest, get a reply. Keep it short and specific.",
    "follow_up":        "Follows a previous interaction. Reference what was discussed. Move one step forward.",
    "investor_update":  "Requests an update from a portfolio company. Be direct about what data you need and by when.",
    "meeting_request":  "Requests a meeting. Be clear about why it's worth their time. Propose a specific time.",
    "deck_request":     "Asks a founder to share their pitch deck. Warm but direct. Explain your interest briefly.",
    "custom":           "Write the best possible email for the context provided.",
}


# ── Main workflow ──────────────────────────────────────────────────────────────

def draft_email(
    email_type: str,
    recipient_name: str,
    recipient_company: str = "",
    context: str = "",
    key_points: list[str] = None,
    sender_name: str = "Alex",
) -> dict:
    """
    Draft a personalised email.
    Returns dict with subject, body, full_draft, file_path.
    """

    # STEP 1: CONTEXT
    style_guide = load_context("templates", "email_style_guide.md")
    email_type  = email_type if email_type in EMAIL_CONTEXTS else "custom"
    type_hint   = EMAIL_CONTEXTS[email_type]

    # STEP 2: INPUT
    points_text = ""
    if key_points:
        points_text = "Key points to cover:\n" + "\n".join(f"- {p}" for p in key_points)

    # STEP 3: PROCESS
    system = f"""You are an email drafting assistant for {sender_name}, a VC investor and adviser.
Write emails that are:
- Short (under 150 words for body unless specified)
- Specific — reference real details, not generic phrases
- Human — no "I hope this email finds you well", no "synergies", no "leverage"
- Clear on the ask — one clear next step per email
- Written in first person as {sender_name}

{f"Style guide:{chr(10)}{style_guide}" if style_guide else ""}

Email type context: {type_hint}

Return a JSON object with exactly two fields: "subject" (the subject line) and "body" (the email body, no sign-off needed)."""

    user = f"""Draft an email with these details:

Type: {email_type}
Recipient: {recipient_name}{f" at {recipient_company}" if recipient_company else ""}
Context: {context}
{points_text}

Draft now."""

    draft = call_claude_structured(system, user, schema=EmailDraft, max_tokens=600)

    # STEP 4: OUTPUT
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name   = recipient_name.lower().replace(" ", "_")
    filename    = f"email_{email_type}_{safe_name}_{timestamp}.md"
    full_draft  = (
        f"# Email Draft — {recipient_name} ({email_type})\n"
        f"**Date:** {datetime.now().strftime('%d %B %Y')}\n"
        f"**To:** {recipient_name}{f', {recipient_company}' if recipient_company else ''}\n\n"
        f"**Subject:** {draft.subject}\n\n---\n\n{draft.body}"
    )
    file_path = save_output(full_draft, "meetings", filename)

    return {
        "subject":    draft.subject,
        "body":       draft.body,
        "recipient":  f"{recipient_name}{f' at {recipient_company}' if recipient_company else ''}",
        "email_type": email_type,
        "file_path":  str(file_path),
        "full_draft": full_draft,
    }
