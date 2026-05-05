"""
Resolves the knowledge base root for a given client.
The API layer calls get_client_kb_root() and injects the result via _client_kb_root
context var before running a workflow, so workflow code never needs to change.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLIENT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _safe_client_id(client_id: str) -> str:
    if not CLIENT_ID_RE.fullmatch(client_id):
        raise ValueError("Invalid client id")
    return client_id


def get_client_kb_root(client_id: str | None) -> Path:
    if not client_id:
        return ROOT / "knowledge_base"
    return ROOT / "clients" / _safe_client_id(client_id) / "knowledge_base"


def list_clients() -> list[dict]:
    clients_dir = ROOT / "clients"
    if not clients_dir.exists():
        return []
    clients = []
    for d in sorted(clients_dir.iterdir()):
        if d.is_dir():
            config = d / "client.json"
            if config.exists():
                try:
                    clients.append(json.loads(config.read_text(encoding="utf-8")))
                except Exception:
                    pass
    return clients


def get_client(client_id: str) -> dict | None:
    try:
        safe_id = _safe_client_id(client_id)
    except ValueError:
        return None
    config = ROOT / "clients" / safe_id / "client.json"
    if not config.exists():
        return None
    try:
        return json.loads(config.read_text(encoding="utf-8"))
    except Exception:
        return None
