from fastapi import APIRouter, HTTPException

from core.client_resolver import list_clients, get_client

router = APIRouter()


@router.get("/clients")
def get_clients():
    clients = list_clients()
    # Prepend the default workspace
    default = {"id": None, "display_name": "Default workspace", "owner_name": "Me", "active_workflows": []}
    return [default] + clients


@router.get("/clients/{client_id}")
def get_client_by_id(client_id: str):
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    return client
