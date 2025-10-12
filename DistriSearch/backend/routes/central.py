from fastapi import APIRouter, Body, HTTPException
import os
from fastapi.responses import FileResponse
from typing import Optional
from services import central_service
from services import replication_service
from fastapi import Depends, Request
from security import require_api_key

router = APIRouter(
    prefix="/central",
    tags=["central"],
    responses={404: {"description": "Not found"}},
)

@router.post("/scan")
async def central_scan(folder: Optional[str] = Body(default=None, embed=True)):
    """Escanea e indexa la carpeta central.

    Body JSON opcional: {"folder": "ruta"}
    Si no se especifica usa variable de entorno CENTRAL_SHARED_FOLDER o ./central_shared
    """
    return central_service.index_central_folder(folder)

@router.get("/mode")
async def central_mode():
    """Retorna información sobre el estado actual de los modos centralizado/distribuido."""
    return central_service.get_mode()

@router.get("/file/{file_id}")
async def get_central_file(file_id: str):
    """Sirve un archivo almacenado en el repositorio central.

    Útil para descargas cuando el nodo central actúa como fuente.
    """
    path = central_service.resolve_central_file_path(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en modo centralizado")
    return FileResponse(path, filename=path.split(os.sep)[-1])

@router.post("/replication/run")
async def run_replication(batch: int = 25, _: None = Depends(require_api_key)):
    """Ejecuta una pasada de replicación para archivos de nodos OFFLINE hacia el central."""
    return replication_service.replicate_missing_files(batch=batch)
