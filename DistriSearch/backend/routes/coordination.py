"""
Endpoints para coordinación distribuida
"""
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional
from services.coordination.coordinator import get_coordinator
from security import require_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/coordination",
    tags=["coordination"],
    responses={404: {"description": "Not found"}},
)


class ElectionRequest(BaseModel):
    challenge: str
    term: int
    started_by: str


class LeaderAnnouncement(BaseModel):
    leader: str
    term: int


class MutexRequest(BaseModel):
    resource_id: str
    node_id: str
    timestamp: int


class MutexReply(BaseModel):
    resource_id: str
    from_node: str


@router.post("/election/start")
async def start_election(reason: str = "manual", _: None = Depends(require_api_key)):
    """Inicia proceso de elección de líder mediante PoW"""
    coordinator = get_coordinator()
    
    try:
        result = await coordinator.start_election(reason=reason)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error iniciando elección: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/election")
async def receive_election_notification(election: ElectionRequest):
    """Recibe notificación de inicio de elección desde otro nodo"""
    coordinator = get_coordinator()
    
    try:
        # Participar en la elección
        nonce = await coordinator.pow_election.solve_challenge(
            election.challenge,
            coordinator.node_id
        )
        
        if nonce is not None:
            # Intentar reclamar liderazgo
            success = await coordinator._claim_leadership(election.challenge, nonce)
            
            return {
                "status": "solved" if success else "solved_but_not_leader",
                "nonce": nonce
            }
        
        return {"status": "no_solution"}
        
    except Exception as e:
        logger.error(f"Error procesando elección: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leader")
async def receive_leader_announcement(announcement: LeaderAnnouncement):
    """Recibe anuncio de nuevo líder"""
    coordinator = get_coordinator()
    
    coordinator.pow_election.current_leader = announcement.leader
    coordinator.pow_election.leader_term = announcement.term
    
    logger.info(f"👑 Nuevo líder reconocido: {announcement.leader} (Término: {announcement.term})")
    
    return {"status": "acknowledged"}


@router.get("/status")
async def get_coordination_status():
    """Obtiene estado actual de coordinación"""
    coordinator = get_coordinator()
    return coordinator.get_coordination_status()


@router.post("/lock/acquire")
async def acquire_distributed_lock(
    resource_id: str = Body(..., embed=True),
    _: None = Depends(require_api_key)
):
    """Adquiere bloqueo distribuido sobre un recurso"""
    coordinator = get_coordinator()
    
    try:
        success = await coordinator.acquire_lock(resource_id)
        
        if success:
            return {"status": "acquired", "resource_id": resource_id}
        else:
            raise HTTPException(status_code=408, detail="Timeout adquiriendo bloqueo")
            
    except Exception as e:
        logger.error(f"Error adquiriendo bloqueo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lock/release")
async def release_distributed_lock(
    resource_id: str = Body(..., embed=True),
    _: None = Depends(require_api_key)
):
    """Libera bloqueo distribuido sobre un recurso"""
    coordinator = get_coordinator()
    
    try:
        await coordinator.release_lock(resource_id)
        return {"status": "released", "resource_id": resource_id}
        
    except Exception as e:
        logger.error(f"Error liberando bloqueo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mutex_request")
async def handle_mutex_request(request: MutexRequest):
    """Maneja solicitud de exclusión mutua de otro nodo"""
    coordinator = get_coordinator()
    
    should_reply = await coordinator.mutex.handle_request(
        request.node_id,
        request.timestamp,
        request.resource_id
    )
    
    return {"should_reply": should_reply}


@router.post("/mutex_reply")
async def handle_mutex_reply(reply: MutexReply):
    """Maneja confirmación de exclusión mutua"""
    coordinator = get_coordinator()
    
    await coordinator.mutex.receive_reply()
    
    return {"status": "acknowledged"}