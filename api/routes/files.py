from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.client_resolver import get_client_kb_root

router = APIRouter()

ALLOWED_SUFFIXES = {".csv", ".md", ".txt", ".json"}

# Absolute root that all workflow-generated files must live under
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # ai-os/


def _kb(client: str | None) -> Path:
    try:
        return get_client_kb_root(client)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client id")


def _safe_path(kb: Path, relative: str) -> Path:
    target = (kb / relative).resolve()
    try:
        target.relative_to(kb.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return target


def _is_allowed_generated_file(target: Path) -> bool:
    roots = [PROJECT_ROOT / "knowledge_base"]
    clients_root = PROJECT_ROOT / "clients"
    if clients_root.exists():
        roots.extend(path / "knowledge_base" for path in clients_root.iterdir() if path.is_dir())

    for root in roots:
        try:
            target.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


@router.get("/files/list")
def list_files(client: str | None = Query(default=None)):
    kb = _kb(client)
    if not kb.exists():
        return []
    results = []
    for path in sorted(kb.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            continue
        relative = path.relative_to(kb)
        parts = relative.parts
        folder = str(parts[0]) if len(parts) > 1 else ""
        stat = path.stat()
        size_kb = round(stat.st_size / 1024, 1)
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        file_type = suffix.lstrip(".")
        results.append({
            "path": relative.as_posix(),
            "name": path.name,
            "folder": folder,
            "size_kb": size_kb,
            "modified_at": modified_at,
            "type": file_type,
        })
    return results


@router.get("/files/download")
def download_file(path: str = Query(...), client: str | None = Query(default=None)):
    kb = _kb(client)
    target = _safe_path(kb, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if target.suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=403, detail="File type not allowed")
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


@router.get("/files/download-abs")
def download_file_abs(path: str = Query(...)):
    """Download a generated output file by absolute path."""
    target = Path(path).resolve()
    if not _is_allowed_generated_file(target):
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if target.suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=403, detail="File type not allowed")
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )
