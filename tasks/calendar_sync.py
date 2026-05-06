"""
AI-OS Google Calendar sync
--------------------------
Mirrors AI-OS tasks to the user's primary Google Calendar.

Calendar events are best-effort: callers must wrap calls in try/except.
The task DB is the source of truth; the calendar event is just a mirror.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
TOKEN_PATH = DATA_DIR / "google_token.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    """Return an authorized Google Calendar API service client.

    Runs the OAuth2 installed-app flow on first call (opens a browser),
    then reuses/refreshes the cached token at data/google_token.json.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Google OAuth client secrets not found at {CREDENTIALS_PATH}. "
                    "See ai-os/CALENDAR_SETUP.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _goal_title_for_task(task: dict[str, Any]) -> str:
    return task.get("goal_title") or task.get("goal_slug") or "(no goal)"


def create_calendar_event(task: dict[str, Any]) -> str:
    """Create an all-day event on task['due_date']. Returns the event id."""
    if not task.get("due_date"):
        raise ValueError("Task has no due_date; cannot create calendar event")

    service = get_calendar_service()
    start_date = task["due_date"]
    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    body = {
        "summary": task["title"],
        "description": f"AI-OS task — Goal: {_goal_title_for_task(task)}",
        "start": {"date": start_date},
        "end": {"date": end_date},
    }
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event["id"]


def update_calendar_event(event_id: str, status: str) -> None:
    """Reflect a status change on the mirrored calendar event."""
    service = get_calendar_service()
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    title = event.get("summary", "")

    if status == "done":
        if not title.startswith("✓ "):
            event["summary"] = f"✓ {title}"
    elif status == "skipped":
        if not title.startswith("→ "):
            event["summary"] = f"→ {title}"
        start = event.get("start", {})
        end = event.get("end", {})
        if "date" in start:
            new_start = (datetime.strptime(start["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            new_end = (datetime.strptime(new_start, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            event["start"] = {"date": new_start}
            event["end"] = {"date": new_end}
        elif "dateTime" in start:
            new_start = (datetime.fromisoformat(start["dateTime"]) + timedelta(days=1)).isoformat()
            new_end = (datetime.fromisoformat(end["dateTime"]) + timedelta(days=1)).isoformat()
            event["start"]["dateTime"] = new_start
            event["end"]["dateTime"] = new_end
    else:
        return

    service.events().update(calendarId="primary", eventId=event_id, body=event).execute()


def delete_calendar_event(event_id: str) -> None:
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
