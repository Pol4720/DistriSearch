from fastapi import APIRouter, HTTPException, Body
from typing import List
from models import FileMeta, NodeInfo
from services import index_service, node_service

router = APIRouter(
    prefix="/register",
    tags=["register"],
    responses={404: {"description": "Not found"}},
)

@router.post("/node")
async def register_node(node: NodeInfo = Body(...)):
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
