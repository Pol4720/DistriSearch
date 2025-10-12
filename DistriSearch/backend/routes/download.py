from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse, Response
import os
from typing import Optional
import httpx

from services.central_service import CENTRAL_NODE_ID, resolve_central_file_path
from models import DownloadRequest
from services import node_service, index_service

router = APIRouter(
    prefix="/download",
    tags=["download"],
    responses={404: {"description": "Not found"}},
)

def _select_node_for_file(file_id: str, preferred_node_id: Optional[str] = None):
    """Selecciona un nodo online que tenga el archivo.

    Prioriza el nodo preferido si está online; si no, el nodo original; y si tampoco, otro online.
    """
    file_meta = index_service.get_file_by_id(file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    candidate_node_id = preferred_node_id or file_meta["node_id"]
    node = node_service.get_node(candidate_node_id)

    if not node or node["status"] != "online":
        nodes_with_file = index_service.get_nodes_with_file(file_id)
        online_nodes = [n for n in nodes_with_file if n["status"] == "online"]
        if not online_nodes:
            raise HTTPException(status_code=503, detail="No hay nodos disponibles para la descarga")
        node = online_nodes[0]
    return node, file_meta

@router.post("/")
async def get_download_url(request: DownloadRequest, req: Request):
    """Obtiene una URL de descarga fiable.

    Ahora siempre devuelve una URL del propio backend que actúa como proxy (/download/file/{id})
    para evitar problemas de CORS o puertos inaccesibles cuando el nodo es remoto.

    Conservamos la semántica original retornando también `direct_node_url` cuando aplica.
    """
    node, _ = _select_node_for_file(request.file_id, request.preferred_node_id)

    base = str(req.base_url).rstrip('/')
    # URL proxy interna del backend (siempre funciona si backend puede alcanzar el nodo)
    backend_proxy_url = f"{base}/download/file/{request.file_id}"

    direct_node_url = None
    if node['node_id'] != CENTRAL_NODE_ID:
        direct_node_url = f"http://{node['ip_address']}:{node['port']}/files/{request.file_id}"
    else:
        # Mantener compatibilidad con ruta central directa
        direct_node_url = f"{base}/central/file/{request.file_id}"

    return {
        "download_url": backend_proxy_url,  # preferido por el frontend
        "direct_node_url": direct_node_url, # opcional para descargas directas
        "node": node
    }

@router.get("/file/{file_id}")
async def download_file(file_id: str, preferred_node_id: Optional[str] = None):
    """Descarga (streaming) del archivo.

    - Si el archivo está en el nodo central se sirve directamente del sistema de ficheros.
    - Si pertenece a un nodo distribuido, el backend actúa como proxy HTTP y retorna el contenido.
    """
    node, file_meta = _select_node_for_file(file_id, preferred_node_id)

    # Caso nodo central
    if node['node_id'] == CENTRAL_NODE_ID:
        path = resolve_central_file_path(file_id)
        if not path:
            raise HTTPException(status_code=404, detail="Archivo central no encontrado")
        filename = os.path.basename(path)
        return FileResponse(path, filename=filename)

    # Caso nodo distribuido: proxy HTTP
    url = f"http://{node['ip_address']}:{node['port']}/files/{file_id}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Error al contactar nodo: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="El nodo no pudo servir el archivo")

    # Propagar cabeceras relevantes
    headers = {}
    cd = resp.headers.get("content-disposition")
    if cd:
        headers["Content-Disposition"] = cd
    content_type = resp.headers.get("content-type", "application/octet-stream")
    return Response(content=resp.content, media_type=content_type, headers=headers)

@router.get("/direct/{file_id}")
async def redirect_to_download(file_id: str, req: Request):
    """
    Redirección directa a la descarga (para compatibilidad).
    Elige automáticamente el mejor nodo disponible.
    """
    download_request = DownloadRequest(file_id=file_id)
    download_info = await get_download_url(download_request, req)
    # Redirigir al proxy interno (siempre funcional)
    return RedirectResponse(url=download_info["download_url"])
