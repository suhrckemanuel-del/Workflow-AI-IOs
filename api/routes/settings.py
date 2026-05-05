import os

from fastapi import APIRouter, HTTPException

from core.db import get_setting, save_setting
from scripts.health_check import run_health_check

router = APIRouter()


CREDENTIALS = [
    {
        "id": "anthropic",
        "label": "Anthropic (Claude)",
        "env": ["ANTHROPIC_API_KEY"],
        "category": "model",
        "required_for": ["All Claude workflows", "Architect", "Eval judge"],
        "risk": "Core generation stops without this key.",
    },
    {
        "id": "exa",
        "label": "Exa",
        "env": ["EXA_API_KEY"],
        "category": "research",
        "required_for": ["Company Research", "Portfolio Monitor", "VC Lead Finder"],
        "risk": "Live research falls back or weakens without this key.",
    },
    {
        "id": "tavily",
        "label": "Tavily",
        "env": ["TAVILY_API_KEY"],
        "category": "research",
        "required_for": ["Optional web search"],
        "risk": "Only needed when a workflow explicitly uses Tavily.",
    },
    {
        "id": "groq",
        "label": "Groq",
        "env": ["GROQ_API_KEY"],
        "category": "model",
        "required_for": ["Optional fast inference"],
        "risk": "Optional until a workflow selects Groq.",
    },
    {
        "id": "hunter",
        "label": "Hunter",
        "env": ["HUNTER_API_KEY"],
        "category": "outreach",
        "required_for": ["Email finding", "Lead validation"],
        "risk": "Outreach can still run, but email confidence is weaker.",
    },
    {
        "id": "gmail",
        "label": "Gmail",
        "env": ["GMAIL_SENDER", "GMAIL_APP_PASSWORD"],
        "category": "outreach",
        "required_for": ["Draft/send email workflows"],
        "risk": "Keep disabled until human-review sending flow is ready.",
    },
    {
        "id": "twitter",
        "label": "Twitter / X",
        "env": ["TWITTER_BEARER_TOKEN"],
        "category": "signals",
        "required_for": ["Optional social signal workflows"],
        "risk": "Only needed for X/Twitter signal collection.",
    },
]


@router.get("/health")
def health():
    return run_health_check()


@router.get("/settings")
def get_settings():
    credential_health = [_credential_status(item) for item in CREDENTIALS]
    return {
        "sender_name": get_setting("sender_name", ""),
        "api_status": {item["id"]: item["configured"] for item in credential_health},
        "credential_health": credential_health,
    }


@router.put("/settings")
def update_setting(body: dict):
    key = body.get("key")
    value = body.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    save_setting(key, value)
    return {"ok": True, "key": key}


def _credential_status(item: dict) -> dict:
    configured_keys = [key for key in item["env"] if bool(os.getenv(key))]
    missing_keys = [key for key in item["env"] if not os.getenv(key)]
    configured = len(missing_keys) == 0
    if configured:
        status = "connected"
    elif configured_keys:
        status = "partial"
    else:
        status = "missing"
    return {
        "id": item["id"],
        "label": item["label"],
        "category": item["category"],
        "configured": configured,
        "status": status,
        "required_for": item["required_for"],
        "risk": item["risk"],
        "missing_env": missing_keys,
    }
