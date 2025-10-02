from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
import os
from services.central_service import CENTRAL_NODE_ID
from models import DownloadRequest
from services import node_service, index_service

router = APIRouter(
    prefix="/download",
    tags=["download"],
    responses={404: {"description": "Not found"}},
)

@router.post("/")
async def get_download_url(request: DownloadRequest, req: Request):
    """
    Obtiene la URL para descargar un archivo.
    Elige el mejor nodo disponible o usa el preferido si se especifica.
    """
    # Verificar que el archivo existe
    file_meta = index_service.get_file_by_id(request.file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    # Seleccionar el nodo para la descarga
    node_id = request.preferred_node_id or file_meta["node_id"]
    
    # Verificar que el nodo está disponible
    node = node_service.get_node(node_id)
    if not node or node["status"] != "online":
        # Si el nodo preferido no está disponible, buscar alternativas
        nodes_with_file = index_service.get_nodes_with_file(request.file_id)
        online_nodes = [n for n in nodes_with_file if n["status"] == "online"]
        
        if not online_nodes:
            raise HTTPException(
                status_code=503, 
                detail="No hay nodos disponibles para la descarga"
            )
        
        # Seleccionar el primer nodo disponible
        node = online_nodes[0]
    
    # Si el archivo pertenece al nodo central, servir vía backend
    if node['node_id'] == CENTRAL_NODE_ID:
        # Construir URL absoluta basada en request
        base = str(req.base_url).rstrip('/')
        download_url = f"{base}/central/file/{request.file_id}"
    else:
        # Construir URL de descarga directa al nodo distribuido
        download_url = f"http://{node['ip_address']}:{node['port']}/files/{request.file_id}"
    
    return {"download_url": download_url, "node": node}

@router.get("/direct/{file_id}")
async def redirect_to_download(file_id: str, req: Request):
    """
    Redirección directa a la descarga (para compatibilidad).
    Elige automáticamente el mejor nodo disponible.
    """
    download_request = DownloadRequest(file_id=file_id)
    download_info = await get_download_url(download_request, req)
    return RedirectResponse(url=download_info["download_url"])
