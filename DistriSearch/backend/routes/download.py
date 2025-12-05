from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, Response
import os
import socket
from typing import Optional
import httpx
import database
from models import DownloadRequest
from services import node_service, index_service
from auth import get_current_active_user

router = APIRouter(
    prefix="/download",
    tags=["download"],
    responses={404: {"description": "Not found"}},
)

def get_public_base_url(request: Request) -> str:
    """Obtiene la URL base pública del backend."""
    public_url = os.getenv("PUBLIC_URL") or os.getenv("DISTRISEARCH_BACKEND_PUBLIC_URL")
    if public_url:
        return public_url.rstrip('/')
    
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    
    base_url = str(request.base_url).rstrip('/')
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(base_url)
    
    internal_hosts = {"localhost", "127.0.0.1", "backend", "backend.local", "0.0.0.0"}
    
    if parsed.hostname in internal_hosts:
        external_ip = os.getenv("EXTERNAL_IP")
        if not external_ip:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                external_ip = s.getsockname()[0]
                s.close()
            except Exception:
                external_ip = "localhost"
        
        protocol = "https" if os.getenv("ENABLE_SSL", "false").lower() in {"true", "1", "yes"} else "http"
        port = parsed.port or (443 if protocol == "https" else 8000)
        netloc = f"{external_ip}:{port}" if port not in {80, 443} else external_ip
        
        base_url = urlunparse((protocol, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    
    return base_url

def _select_node_for_file(file_id: str, preferred_node_id: Optional[str] = None):
    """Selecciona un nodo online que tenga el archivo."""
    # Buscar en MongoDB
    file_meta = database._db.files.find_one({"file_id": file_id})
    if not file_meta:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    candidate_node_id = preferred_node_id or file_meta["node_id"]
    node = node_service.get_node(candidate_node_id)

    if not node or node["status"] != "online":
        # Buscar otros nodos con el archivo
        other_files = list(database._db.files.find({"file_id": file_id}))
        online_nodes = []
        for f in other_files:
            n = database.get_node(f["node_id"])
            if n and n["status"] == "online":
                online_nodes.append(n)
        
        if not online_nodes:
            raise HTTPException(status_code=503, detail="No hay nodos disponibles para la descarga")
        node = online_nodes[0]
    
    return node, file_meta

@router.post("/")
async def get_download_url(
    request: DownloadRequest, 
    req: Request, 
    current_user: dict = Depends(get_current_active_user)
):
    """Obtiene una URL de descarga del archivo desde un nodo distribuido."""
    database.log_activity(current_user["_id"], "download_request", f"File ID: {request.file_id}")

    node, _ = _select_node_for_file(request.file_id, request.preferred_node_id)

    base = get_public_base_url(req)
    backend_proxy_url = f"{base}/download/file/{request.file_id}"

    node_protocol = "https" if os.getenv("AGENT_SSL_ENABLED", "false").lower() in {"true", "1", "yes"} else "http"
    direct_node_url = f"{node_protocol}://{node['ip_address']}:{node['port']}/files/{request.file_id}"

    return {
        "download_url": backend_proxy_url,
        "direct_node_url": direct_node_url,
        "node": node
    }

@router.get("/file/{file_id}")
async def download_file(file_id: str, preferred_node_id: Optional[str] = None):
    """Descarga el archivo desde un nodo distribuido (proxy HTTP)."""
    node, file_meta = _select_node_for_file(file_id, preferred_node_id)

    url = f"http://{node['ip_address']}:{node['port']}/files/{file_id}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Error al contactar nodo: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="El nodo no pudo servir el archivo")

    headers = {}
    cd = resp.headers.get("content-disposition")
    if cd:
        headers["Content-Disposition"] = cd
    content_type = resp.headers.get("content-type", "application/octet-stream")
    return Response(content=resp.content, media_type=content_type, headers=headers)

@router.get("/direct/{file_id}")
async def redirect_to_download(file_id: str, req: Request):
    """Redirección directa a la descarga."""
    download_request = DownloadRequest(file_id=file_id)
    # Necesitamos un usuario para el log, usar sistema
    download_info = await get_download_url(download_request, req, {"_id": "system", "username": "system"})
    return RedirectResponse(url=download_info["download_url"])
