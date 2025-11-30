"""
Módulo de elección de líder en Raft.
Gestiona RequestVote y elecciones.
"""
import asyncio
import random
import time
import logging
from typing import Set, Dict
from consensus.raft_state import (
    NodeState, RaftMessage, RaftState, RaftConfig
)

logger = logging.getLogger(__name__)


class RaftElection:
    """Gestiona el proceso de elección de líder."""
    
    def __init__(
        self,
        node_id: int,
        all_node_ids: Set[int],
        state: RaftState,
        network,
        config: RaftConfig = None
    ):
        self.node_id = node_id
        self.all_nodes = all_node_ids
        self.state = state
        self.network = network
        self.config = config or RaftConfig()
        
        # Tiempos
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        # Tareas
        self._election_timer_task: asyncio.Task = None
    
    def _random_election_timeout(self) -> float:
        """Genera timeout aleatorio para evitar split votes."""
        return random.uniform(
            self.config.ELECTION_TIMEOUT_MIN,
            self.config.ELECTION_TIMEOUT_MAX
        )
    
    async def start_election_timer(self):
        """Inicia el timer que dispara elecciones."""
        self._election_timer_task = asyncio.create_task(self._election_timer_loop())
    
    async def stop_election_timer(self):
        """Detiene el timer de elecciones."""
        if self._election_timer_task and not self._election_timer_task.done():
            self._election_timer_task.cancel()
            try:
                await self._election_timer_task
            except asyncio.CancelledError:
                pass
    
    async def _election_timer_loop(self):
        """Loop que verifica timeouts de elección."""
        while True:
            try:
                await asyncio.sleep(0.1)
                
                if self.state.state == NodeState.LEADER:
                    continue  # Líderes no hacen elecciones
                
                elapsed = time.time() - self.last_heartbeat
                if elapsed > self.election_timeout:
                    logger.info(
                        f"Nodo {self.node_id}: Election timeout "
                        f"({elapsed:.2f}s), iniciando elección"
                    )
                    await self.start_election()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en election timer: {e}")
    
    async def start_election(self):
        """
        Inicia proceso de elección.
        
        Protocolo:
        1. Incrementar term
        2. Votar por sí mismo
        3. Enviar RequestVote a todos los nodos
        4. Esperar respuestas
        5. Si recibe mayoría de votos, convertirse en líder
        """
        # Transición a candidato
        self.state.become_candidate(self.node_id)
        
        logger.info(
            f"Nodo {self.node_id}: Candidato en term {self.state.current_term}"
        )
        
        # Resetear timeout
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        # Enviar RequestVote a todos
        request = RaftMessage(
            type="request_vote",
            term=self.state.current_term,
            sender_id=self.node_id,
            last_log_index=len(self.state.log) - 1 if self.state.log else -1,
            last_log_term=self.state.log[-1].term if self.state.log else 0
        )
        
        # Enviar en paralelo
        tasks = []
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                tasks.append(self._send_vote_request(node_id, request))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verificar si ganamos
        await self._check_election_result()
    
    async def _send_vote_request(self, target_node: int, request: RaftMessage):
        """Envía RequestVote a un nodo."""
        try:
            response = await self.network.send_message(
                self.node_id,
                target_node,
                {
                    "type": "raft_message",
                    "payload": request.__dict__
                },
                timeout=1.0
            )
            
            if response:
                await self.handle_vote_response(response.get("payload", {}))
                
        except Exception as e:
            logger.debug(f"Error enviando vote request a {target_node}: {e}")
    
    async def handle_vote_request(self, payload: Dict) -> RaftMessage:
        """
        Maneja RequestVote recibido.
        
        Args:
            payload: Datos del mensaje
            
        Returns:
            Respuesta de voto
        """
        candidate_term = payload["term"]
        candidate_id = payload["sender_id"]
        last_log_index = payload.get("last_log_index", -1)
        last_log_term = payload.get("last_log_term", 0)
        
        # Si su term es mayor, actualizamos
        if candidate_term > self.state.current_term:
            self.state.become_follower(candidate_term)
        
        # Decidir si votamos
        vote_granted = False
        
        # Condiciones para votar:
        # 1. Su term >= nuestro term
        # 2. No hemos votado por nadie más en este term
        # 3. Su log está al menos tan actualizado como el nuestro
        if candidate_term >= self.state.current_term and \
           (self.state.voted_for is None or self.state.voted_for == candidate_id):
            
            # Verificar log actualizado (Raft Safety)
            our_last_index = len(self.state.log) - 1 if self.state.log else -1
            our_last_term = self.state.log[-1].term if self.state.log else 0
            
            log_ok = (last_log_term > our_last_term) or \
                     (last_log_term == our_last_term and last_log_index >= our_last_index)
            
            if log_ok:
                vote_granted = True
                self.state.voted_for = candidate_id
                self.last_heartbeat = time.time()
                logger.info(
                    f"Nodo {self.node_id}: Votando por {candidate_id} "
                    f"en term {candidate_term}"
                )
        
        # Responder
        return RaftMessage(
            type="vote_response",
            term=self.state.current_term,
            sender_id=self.node_id,
            vote_granted=vote_granted
        )
    
    async def handle_vote_response(self, payload: Dict):
        """Maneja respuesta de voto."""
        if self.state.state != NodeState.CANDIDATE:
            return
        
        if payload.get("vote_granted"):
            voter_id = payload["sender_id"]
            self.state.votes_received.add(voter_id)
            
            logger.debug(
                f"Nodo {self.node_id}: Voto recibido de {voter_id} "
                f"({len(self.state.votes_received)} votos)"
            )
            
            await self._check_election_result()
    
    async def _check_election_result(self):
        """Verifica si se ganó la elección."""
        if self.state.state != NodeState.CANDIDATE:
            return
        
        quorum = len(self.all_nodes) // 2 + 1
        
        if len(self.state.votes_received) >= quorum:
            logger.info(
                f"Nodo {self.node_id}: ELEGIDO LÍDER en term {self.state.current_term} "
                f"({len(self.state.votes_received)}/{len(self.all_nodes)} votos)"
            )
            self.state.become_leader(self.node_id, len(self.all_nodes))
            
            # Callback para notificar que somos líder
            # (será manejado por RaftConsensus)
    
    def reset_election_timeout(self):
        """Resetea el timeout de elección (llamado al recibir heartbeat)."""
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()