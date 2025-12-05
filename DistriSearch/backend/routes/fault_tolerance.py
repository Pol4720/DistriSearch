"""
Endpoints para monitoreo de tolerancia a fallos
"""
from fastapi import APIRouter, HTTPException, Depends
from security import require_api_key
from services.checkpoint_service import get_checkpoint_service
from services.reliability_metrics import get_reliability_metrics
from services.dynamic_replication import get_replication_service

router = APIRouter(
    prefix="/fault_tolerance",
    tags=["fault_tolerance"],
)

@router.post("/checkpoint/create")
async def create_checkpoint(_: None = Depends(require_api_key)):
    """Crea checkpoint coordinado manualmente"""
    checkpoint_service = get_checkpoint_service()
    result = await checkpoint_service.create_coordinated_checkpoint()
    return result

@router.post("/checkpoint/restore/{checkpoint_id}")
async def restore_checkpoint(checkpoint_id: str, _: None = Depends(require_api_key)):
    """Restaura sistema desde checkpoint"""
    checkpoint_service = get_checkpoint_service()
    result = await checkpoint_service.restore_from_checkpoint(checkpoint_id)
    return result

@router.get("/metrics/node/{node_id}")
async def get_node_metrics(node_id: str):
    """Obtiene métricas de confiabilidad de un nodo"""
    reliability = get_reliability_metrics()
    metrics = reliability.calculate_metrics(node_id)
    return metrics

@router.get("/metrics/system")
async def get_system_metrics():
    """Obtiene métricas del sistema completo"""
    reliability = get_reliability_metrics()
    metrics = reliability.get_system_reliability()
    return metrics

@router.get("/replication/status")
async def get_replication_status():
    """Obtiene estado de replicación"""
    repl_service = get_replication_service()
    return repl_service.get_replication_status()