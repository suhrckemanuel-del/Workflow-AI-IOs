from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from api.models import KBDirectory, KBFile
from core.client_resolver import get_client_kb_root

router = APIRouter()


def _kb(client: str | None) -> Path:
    try:
        return get_client_kb_root(client)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client id")


def _safe_kb_file(client: str | None, folder: str, filename: str) -> Path:
    kb = _kb(client).resolve()
    path = (kb / folder / filename).resolve()
    try:
        path.relative_to(kb)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if path.suffix.lower() != ".md":
        raise HTTPException(status_code=403, detail="Only markdown files are allowed")
    return path


@router.get("/kb", response_model=KBDirectory)
def list_kb(client: str | None = Query(default=None)):
    kb = _kb(client)
    if not kb.exists():
        return KBDirectory(folders={})
    folders: dict[str, list[str]] = {}
    for folder in sorted(kb.iterdir()):
        if folder.is_dir() and not folder.name.startswith("."):
            files = sorted(f.name for f in folder.glob("*.md"))
            if files:
                folders[folder.name] = files
    return KBDirectory(folders=folders)


@router.get("/kb/{folder}/{filename}", response_model=KBFile)
def get_kb_file(folder: str, filename: str, client: str | None = Query(default=None)):
    path = _safe_kb_file(client, folder, filename)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{folder}/{filename}' not found")
    content = path.read_text(encoding="utf-8")
    modified_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    return KBFile(folder=folder, filename=filename, content=content, modified_at=modified_at)


@router.delete("/kb/{folder}/{filename}")
def delete_kb_file(folder: str, filename: str, client: str | None = Query(default=None)):
    path = _safe_kb_file(client, folder, filename)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{folder}/{filename}' not found")
    path.unlink()
    return {"ok": True, "deleted": f"{folder}/{filename}"}
