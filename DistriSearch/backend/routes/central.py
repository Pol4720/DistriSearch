from fastapi import APIRouter, Body
from typing import Optional
from services import central_service

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
