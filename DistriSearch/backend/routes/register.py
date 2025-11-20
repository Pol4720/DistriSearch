from fastapi import APIRouter, HTTPException, Body
from fastapi import Depends, Request
from typing import List
from models import FileMeta, NodeInfo
from services import index_service, node_service
import database as database_viejo
import os
import mimetypes
from services.central_service import _hash_file, _categorize, _extract_text_for_central
from services.central_service import _instance_id
from datetime import datetime
from security import require_api_key

router = APIRouter(
    prefix="/register",
    tags=["register"],
    responses={404: {"description": "Not found"}},
)

@router.post("/node")
async def register_node(node: NodeInfo = Body(...), _: None = Depends(require_api_key)):
    """
    Registra un nuevo nodo en el sistema o actualiza uno existente
    """
    return node_service.register_node(node)

@router.post("/files")
async def register_files(files: List[FileMeta] = Body(...)):
    """
    Registra metadatos de archivos desde un nodo
    """
    try:
        result = index_service.register_files(files)
        return {"status": "success", "indexed_count": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/heartbeat/{node_id}")
async def node_heartbeat(node_id: str):
    """
    Actualiza el estado y timestamp de última conexión del nodo
    """
    success = node_service.update_node_heartbeat(node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "online"}

@router.delete("/node/{node_id}")
async def delete_node(node_id: str, delete_files: bool = True, _: None = Depends(require_api_key)):
    """
    Elimina un nodo del sistema.

    - delete_files=true: elimina también los archivos asociados a ese nodo del índice.
    - Si delete_files=false: conserva los metadatos de archivos (seguirán apuntando a un nodo inexistente).
    """
    existing = database_viejo.get_node(node_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Node not found")

    with database_viejo.get_connection() as conn:
        cur = conn.cursor()
        if delete_files:
            cur.execute("DELETE FROM files WHERE node_id = ?", (node_id,))
            cur.execute("DELETE FROM file_contents WHERE file_id NOT IN (SELECT file_id FROM files)")
        cur.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        conn.commit()
    return {"status": "deleted", "node_id": node_id, "deleted_files": delete_files}

@router.post("/node/{node_id}/mount")
async def set_node_folder(node_id: str, folder: str = Body(..., embed=True), _: None = Depends(require_api_key)):
    """Configura una carpeta local asociada a un nodo (simulación local de servidor independiente)."""
    if not database_viejo.get_node(node_id):
        raise HTTPException(status_code=404, detail="Node not found")
    database_viejo.set_node_mount(node_id, folder)
    # Marcar nodo simulado como ONLINE (no depende de heartbeat)
    database_viejo.update_node_status(node_id, "online")
    return {"status": "ok", "node_id": node_id, "folder": os.path.abspath(folder)}

@router.post("/node/{node_id}/scan-import")
async def import_from_node_folder(node_id: str, _: None = Depends(require_api_key)):
    """Escanea la carpeta montada del nodo y registra/actualiza sus archivos sin necesitar un agente externo.

    Útil para simulación local: el backend toma el rol del agente para ese nodo.
    """
    mount = database_viejo.get_node_mount(node_id)
    if not mount:
        raise HTTPException(status_code=400, detail="Node folder not configured. Use /node/{node_id}/mount")
    abspath = os.path.abspath(mount)
    mimetypes.init()
    count = 0
    for root, _, files in os.walk(abspath):
        for fname in files:
            full = os.path.join(root, fname)
            try:
                mime, _ = mimetypes.guess_type(full)
                if not mime:
                    mime = 'application/octet-stream'
                rel = os.path.relpath(full, abspath)
                fm = FileMeta(
                    file_id=_instance_id(node_id, rel),
                    name=fname,
                    path=rel,
                    size=os.path.getsize(full),
                    mime_type=mime,
                    type=_categorize(mime),
                    node_id=node_id,
                    last_updated=datetime.fromtimestamp(os.path.getmtime(full)),
                    content=_extract_text_for_central(full, mime),
                    content_hash=_hash_file(full)
                )
                database_viejo.register_file(fm)
                count += 1
            except Exception:
                continue
    # Nodo simulado activo
    database_viejo.update_node_status(node_id, "online")
    # Recalcular contador de archivos del nodo
    total = database_viejo.get_node_file_count(node_id)
    database_viejo.update_node_shared_files_count(node_id, total)
    return {"status": "ok", "imported": count, "folder": abspath, "node_files": total}

@router.post("/node/{node_id}/sync")
async def sync_node_folder(node_id: str, _: None = Depends(require_api_key)):
    """Sincroniza el estado completo del nodo con su carpeta montada.

    - Registra/actualiza archivos presentes (como scan-import).
    - Elimina del índice archivos que ya no existen en la carpeta del nodo.
    """
    mount = database_viejo.get_node_mount(node_id)
    if not mount:
        raise HTTPException(status_code=400, detail="Node folder not configured. Use /node/{node_id}/mount")
    abspath = os.path.abspath(mount)
    mimetypes.init()

    # Construir set de file_ids actuales en carpeta
    current_ids = set()
    imported = 0
    for root, _, files in os.walk(abspath):
        for fname in files:
            full = os.path.join(root, fname)
            try:
                mime, _ = mimetypes.guess_type(full)
                if not mime:
                    mime = 'application/octet-stream'
                rel = os.path.relpath(full, abspath)
                fid = _instance_id(node_id, rel)
                current_ids.add(fid)
                fm = FileMeta(
                    file_id=fid,
                    name=fname,
                    path=rel,
                    size=os.path.getsize(full),
                    mime_type=mime,
                    type=_categorize(mime),
                    node_id=node_id,
                    last_updated=datetime.fromtimestamp(os.path.getmtime(full)),
                    content=_extract_text_for_central(full, mime),
                    content_hash=_hash_file(full)
                )
                database_viejo.register_file(fm)
                imported += 1
            except Exception:
                continue

    # Obtener file_ids en DB para el nodo
    with database_viejo.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_id FROM files WHERE node_id = ?", (node_id,))
        existing_ids = {row[0] for row in cur.fetchall()}
        stale = list(existing_ids - current_ids)
        if stale:
            cur.execute(
                f"DELETE FROM files WHERE node_id = ? AND file_id IN ({','.join('?'*len(stale))})",
                (node_id, *stale)
            )
            # Limpiar contenidos huérfanos
            cur.execute("DELETE FROM file_contents WHERE file_id NOT IN (SELECT file_id FROM files)")
            conn.commit()
    # Nodo simulado activo
    database_viejo.update_node_status(node_id, "online")
    # Recalcular contador de archivos del nodo
    total = database_viejo.get_node_file_count(node_id)
    database_viejo.update_node_shared_files_count(node_id, total)
    return {"status": "ok", "imported": imported, "removed": len(stale), "folder": abspath, "node_files": total}


# register.py - Agregar nuevo endpoint

@router.post("/node/dynamic")
async def register_node_dynamic_endpoint(
    registration: NodeRegistration,
    request: Request
):
    """
    Registro dinámico de nodos. Los nodos pueden autoregistrarse sin configuración previa.
    
    Body JSON:
    {
        "node_id": "agent_01",
        "name": "Agente de Backup",
        "port": 8081,
        "auto_scan": true
    }
    
    El backend autodetectará la IP desde la petición si no se envía.
    """
    try:
        # Autodetectar IP desde la petición
        client_host = request.client.host if request.client else None
        
        result = node_service.register_node_dynamic(
            node_id=registration.node_id,
            name=registration.name,
            ip_address=registration.ip_address,
            port=registration.port,
            request_host=client_host,
            shared_folder=registration.shared_folder
        )
        
        return {
            "status": "success",
            "data": result,
            "config_endpoint": f"{request.base_url}register/node/{registration.node_id}/config"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en registro dinámico: {str(e)}")

@router.get("/node/{node_id}/config")
async def get_node_configuration(node_id: str):
    """
    Endpoint para que los nodos obtengan su configuración completa después de registrarse.
    """
    config = node_service.get_node_config(node_id)
    if not config:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    
    return {
        "status": "success",
        "config": config
    }