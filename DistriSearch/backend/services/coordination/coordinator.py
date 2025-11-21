import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
import httpx
from pymongo import MongoClient
import os
from .Lamport_Clock import LamportClock
from .PoW import ProofOfWorkElection
from .Distributed_Mutex import DistributedMutex

logger = logging.getLogger(__name__)

class DistributedCoordinator:
    """
    Coordinador principal que integra todos los mecanismos de coordinación
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DBNAME", "distrisearch")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        
        # Componentes de coordinación
        self.node_id = os.getenv("NODE_ID", "central")
        self.clock = LamportClock()
        self.pow_election = ProofOfWorkElection(difficulty=int(os.getenv("POW_DIFFICULTY", "4")))
        self.mutex = DistributedMutex(self.node_id, self.clock)
        
        # Estado
        self.election_in_progress = False
        self.last_heartbeat: Dict[str, datetime] = {}
        
        # Inicializar colección de coordinación
        self._init_coordination_db()
    
    def _init_coordination_db(self):
        """Inicializa colecciones para coordinación"""
        # Colección para estado de coordinación
        self.db.coordination_state.create_index("node_id", unique=True)
        
        # Colección para eventos de sincronización
        self.db.sync_events.create_index([("timestamp", 1)])
        
        # Colección para elecciones
        self.db.elections.create_index([("term", -1)])
    
    async def start_election(self, reason: str = "manual") -> Dict:
        """
        Inicia proceso de elección de líder mediante PoW
        """
        if self.election_in_progress:
            return {"status": "election_already_in_progress"}
        
        self.election_in_progress = True
        logger.info(f"🗳️ Iniciando elección de líder - Razón: {reason}")
        
        try:
            # Generar desafío
            challenge = self.pow_election.generate_challenge()
            
            # Registrar elección en DB
            election_doc = {
                "term": self.pow_election.leader_term + 1,
                "challenge": challenge,
                "started_at": datetime.utcnow(),
                "started_by": self.node_id,
                "reason": reason,
                "status": "in_progress"
            }
            self.db.elections.insert_one(election_doc)
            
            # Notificar a todos los nodos del desafío
            online_nodes = list(self.db.nodes.find({"status": "online"}))
            
            broadcast_tasks = []
            for node in online_nodes:
                if node['node_id'] != self.node_id:
                    broadcast_tasks.append(
                        self._notify_election_start(node, challenge)
                    )
            
            await asyncio.gather(*broadcast_tasks, return_exceptions=True)
            
            # Intentar resolver el desafío localmente
            logger.info(f"💻 Resolviendo desafío PoW (dificultad: {self.pow_election.difficulty})...")
            nonce = await self.pow_election.solve_challenge(challenge, self.node_id)
            
            if nonce is not None:
                # Solución encontrada - intentar reclamar liderazgo
                success = await self._claim_leadership(challenge, nonce)
                
                if success:
                    return {
                        "status": "elected",
                        "leader": self.node_id,
                        "term": self.pow_election.leader_term,
                        "nonce": nonce
                    }
            
            # Esperar resultado de otros nodos
            await asyncio.sleep(5)  # Timeout para recibir soluciones
            
            # Verificar quién ganó
            current_election = self.db.elections.find_one(
                {"term": self.pow_election.leader_term + 1},
                sort=[("completed_at", -1)]
            )
            
            if current_election and current_election.get("winner"):
                return {
                    "status": "completed",
                    "leader": current_election["winner"],
                    "term": current_election["term"]
                }
            
            return {"status": "no_solution_found"}
            
        finally:
            self.election_in_progress = False
    
    async def _notify_election_start(self, node: Dict, challenge: str):
        """Notifica a un nodo sobre inicio de elección"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"http://{node['ip_address']}:{node['port']}/coordination/election"
                await client.post(url, json={
                    "challenge": challenge,
                    "term": self.pow_election.leader_term + 1,
                    "started_by": self.node_id
                })
        except Exception as e:
            logger.error(f"Error notificando elección a {node['node_id']}: {e}")
    
    async def _claim_leadership(self, challenge: str, nonce: int) -> bool:
        """
        Reclama liderazgo después de resolver PoW
        Usa consenso distribuido para validar
        """
        # Verificar que la solución es válida
        if not self.pow_election.verify_proof(challenge, nonce, self.node_id):
            logger.error("❌ Solución inválida")
            return False
        
        timestamp = await self.clock.increment()
        
        # Intentar actualizar en DB atómicamente
        result = self.db.elections.update_one(
            {
                "challenge": challenge,
                "status": "in_progress",
                "winner": {"$exists": False}
            },
            {
                "$set": {
                    "winner": self.node_id,
                    "nonce": nonce,
                    "completed_at": datetime.utcnow(),
                    "status": "completed",
                    "lamport_timestamp": timestamp
                }
            }
        )
        
        if result.modified_count > 0:
            # Ganamos la elección
            self.pow_election.set_leader(self.node_id, nonce, challenge)
            
            # Notificar a todos los nodos
            await self._broadcast_new_leader(self.node_id, self.pow_election.leader_term)
            
            logger.info(f"👑 Liderazgo reclamado exitosamente - Término: {self.pow_election.leader_term}")
            return True
        
        return False
    
    async def _broadcast_new_leader(self, leader_id: str, term: int):
        """Notifica a todos los nodos sobre nuevo líder"""
        online_nodes = list(self.db.nodes.find({"status": "online"}))
        
        for node in online_nodes:
            if node['node_id'] != self.node_id:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        url = f"http://{node['ip_address']}:{node['port']}/coordination/leader"
                        await client.post(url, json={
                            "leader": leader_id,
                            "term": term
                        })
                except Exception as e:
                    logger.error(f"Error notificando líder a {node['node_id']}: {e}")
    
    async def acquire_lock(self, resource_id: str) -> bool:
        """
        Adquiere bloqueo distribuido sobre un recurso
        """
        online_nodes = [n['node_id'] for n in self.db.nodes.find({"status": "online"})]
        
        logger.info(f"🔒 Solicitando bloqueo para recurso: {resource_id}")
        success = await self.mutex.request_access(resource_id, online_nodes)
        
        if success:
            # Registrar adquisición
            await self.clock.increment()
            self.db.mutex_events.insert_one({
                "node_id": self.node_id,
                "resource_id": resource_id,
                "action": "acquire",
                "timestamp": datetime.utcnow(),
                "lamport_time": self.clock.get_time()
            })
        
        return success
    
    async def release_lock(self, resource_id: str):
        """
        Libera bloqueo distribuido sobre un recurso
        """
        logger.info(f"🔓 Liberando bloqueo para recurso: {resource_id}")
        
        deferred_nodes = await self.mutex.release_access(resource_id)
        
        # Enviar confirmaciones diferidas
        for node_id in deferred_nodes:
            node = self.db.nodes.find_one({"node_id": node_id})
            if node:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        url = f"http://{node['ip_address']}:{node['port']}/coordination/mutex_reply"
                        await client.post(url, json={
                            "resource_id": resource_id,
                            "from_node": self.node_id
                        })
                except Exception as e:
                    logger.error(f"Error enviando confirmación a {node_id}: {e}")
        
        # Registrar liberación
        await self.clock.increment()
        self.db.mutex_events.insert_one({
            "node_id": self.node_id,
            "resource_id": resource_id,
            "action": "release",
            "timestamp": datetime.utcnow(),
            "lamport_time": self.clock.get_time()
        })
    
    def get_current_leader(self) -> Optional[str]:
        """Retorna el líder actual"""
        return self.pow_election.current_leader
    
    def get_coordination_status(self) -> Dict:
        """Retorna estado actual de coordinación"""
        return {
            "node_id": self.node_id,
            "current_leader": self.pow_election.current_leader,
            "leader_term": self.pow_election.leader_term,
            "lamport_time": self.clock.get_time(),
            "election_in_progress": self.election_in_progress,
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton global
_coordinator = None

def get_coordinator() -> DistributedCoordinator:
    """Obtiene instancia singleton del coordinador"""
    global _coordinator
    if _coordinator is None:
        _coordinator = DistributedCoordinator()
    return _coordinator