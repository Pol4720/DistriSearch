"""
Módulo de replicación de log en Raft.
Gestiona AppendEntries, heartbeats y replicación del log.
"""
import asyncio
import time
import logging
from typing import Set, Dict, List, Optional
from consensus.raft_state import (
    NodeState, RaftMessage, RaftState, LogEntry, RaftConfig
)

logger = logging.getLogger(__name__)


class RaftReplication:
    """Gestiona la replicación del log de Raft."""
    
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
        
        # Tareas
        self._heartbeat_task: asyncio.Task = None
    
    async def start_heartbeat_loop(self):
        """Inicia el loop de heartbeats (solo líderes)."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop_heartbeat_loop(self):
        """Detiene el loop de heartbeats."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
    
    async def _heartbeat_loop(self):
        """Loop que envía heartbeats periódicos."""
        while True:
            try:
                if self.state.state == NodeState.LEADER:
                    await self._send_heartbeats()
                
                await asyncio.sleep(self.config.HEARTBEAT_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en heartbeat loop: {e}")
    
    async def _send_heartbeats(self):
        """Envía heartbeats (AppendEntries vacío) a todos los followers."""
        tasks = []
        
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                tasks.append(self._send_append_entries(node_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_append_entries(
        self, 
        target_node: int, 
        entries: List[LogEntry] = None
    ):
        """
        Envía AppendEntries a un follower.
        
        Args:
            target_node: ID del nodo destino
            entries: Entradas a enviar (None = heartbeat)
        """
        if self.state.state != NodeState.LEADER:
            return
        
        # Obtener índice previo
        next_index = self.state.next_index.get(target_node, len(self.state.log))
        prev_log_index = next_index - 1
        prev_log_term = 0
        
        if prev_log_index >= 0 and prev_log_index < len(self.state.log):
            prev_log_term = self.state.log[prev_log_index].term
        
        # Preparar entradas a enviar
        entries_to_send = []
        if entries:
            entries_to_send = [
                {
                    "term": e.term,
                    "command": e.command,
                    "index": e.index
                }
                for e in entries
            ]
        
        # Crear mensaje
        message = RaftMessage(
            type="append_entries",
            term=self.state.current_term,
            sender_id=self.node_id,
            leader_id=self.node_id,
            prev_log_index=prev_log_index,
            prev_log_term=prev_log_term,
            entries=entries_to_send,
            leader_commit=self.state.commit_index
        )
        
        try:
            response = await self.network.send_message(
                self.node_id,
                target_node,
                {
                    "type": "raft_message",
                    "payload": message.__dict__
                },
                timeout=1.0
            )
            
            if response:
                await self._handle_append_response(
                    target_node, 
                    response.get("payload", {})
                )
                
        except Exception as e:
            logger.debug(f"Error enviando AppendEntries a {target_node}: {e}")
    
    async def handle_append_entries(self, payload: Dict) -> RaftMessage:
        """
        Maneja AppendEntries recibido.
        
        Args:
            payload: Datos del mensaje
            
        Returns:
            Respuesta de AppendEntries
        """
        leader_term = payload["term"]
        leader_id = payload["leader_id"]
        prev_log_index = payload.get("prev_log_index", -1)
        prev_log_term = payload.get("prev_log_term", 0)
        entries = payload.get("entries", [])
        leader_commit = payload.get("leader_commit", 0)
        
        # Si su term es mayor o igual, actualizamos
        if leader_term >= self.state.current_term:
            self.state.become_follower(leader_term, leader_id)
        
        success = False
        
        # Verificar consistencia del log
        if prev_log_index < 0:
            # Primer heartbeat, siempre OK
            success = True
        elif prev_log_index < len(self.state.log):
            if self.state.log[prev_log_index].term == prev_log_term:
                success = True
        
        # Si hay entradas, replicar
        if success and entries:
            for entry_dict in entries:
                entry = LogEntry(
                    term=entry_dict["term"],
                    command=entry_dict["command"],
                    index=entry_dict["index"]
                )
                
                # Añadir al log (simplificado: sin validación de prev_log)
                if entry.index >= len(self.state.log):
                    self.state.log.append(entry)
                    logger.debug(
                        f"Nodo {self.node_id}: Entrada {entry.index} "
                        f"replicada al log"
                    )
        
        # Actualizar commit_index
        if leader_commit > self.state.commit_index:
            self.state.commit_index = min(leader_commit, len(self.state.log) - 1)
        
        # Responder
        return RaftMessage(
            type="append_response",
            term=self.state.current_term,
            sender_id=self.node_id,
            success=success,
            match_index=len(self.state.log) - 1 if success else -1
        )
    
    async def _handle_append_response(self, follower_id: int, payload: Dict):
        """Maneja respuesta de AppendEntries."""
        if self.state.state != NodeState.LEADER:
            return
        
        success = payload.get("success", False)
        match_index = payload.get("match_index", -1)
        
        if success:
            # Actualizar índices de replicación
            self.state.match_index[follower_id] = match_index
            self.state.next_index[follower_id] = match_index + 1
            
            logger.debug(
                f"Nodo {follower_id}: AppendEntries OK "
                f"(match_index={match_index})"
            )
            
            # Verificar si podemos avanzar commit_index
            await self._update_commit_index()
        else:
            # Decrementar next_index y reintentar
            if follower_id in self.state.next_index:
                self.state.next_index[follower_id] = max(
                    0, 
                    self.state.next_index[follower_id] - 1
                )
    
    async def _update_commit_index(self):
        """
        Actualiza commit_index basándose en match_index de followers.
        
        El líder solo puede commitear entradas de su propio term
        si la mayoría de followers las han replicado.
        """
        if self.state.state != NodeState.LEADER:
            return
        
        # Para cada índice N > commit_index
        for n in range(self.state.commit_index + 1, len(self.state.log)):
            # Solo commitear entradas del term actual (safety de Raft)
            if self.state.log[n].term != self.state.current_term:
                continue
            
            # Contar cuántos nodos tienen este índice
            replicated_count = 1  # Contamos a nosotros mismos
            
            for node_id in self.all_nodes:
                if node_id != self.node_id:
                    if self.state.match_index.get(node_id, -1) >= n:
                        replicated_count += 1
            
            # Si mayoría lo tiene, commitear
            quorum = len(self.all_nodes) // 2 + 1
            if replicated_count >= quorum:
                self.state.commit_index = n
                logger.info(
                    f"Líder {self.node_id}: Commiteado índice {n} "
                    f"({replicated_count}/{len(self.all_nodes)} nodos)"
                )
    
    async def append_entry(self, command: Dict) -> bool:
        """
        Añade entrada al log y replica (SOLO LÍDER).
        
        Args:
            command: Comando a replicar
            
        Returns:
            True si se replicó con quorum, False si no
        """
        if self.state.state != NodeState.LEADER:
            logger.error(
                f"Nodo {self.node_id}: Solo el líder puede append_entry"
            )
            return False
        
        # Añadir al log local
        entry = LogEntry(
            term=self.state.current_term,
            command=command,
            index=len(self.state.log)
        )
        self.state.log.append(entry)
        
        logger.debug(
            f"Líder {self.node_id}: Entrada añadida al log "
            f"(índice {entry.index})"
        )
        
        # Replicar a followers
        tasks = []
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                tasks.append(
                    self._send_append_entries(node_id, entries=[entry])
                )
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Esperar un poco para que lleguen respuestas
        await asyncio.sleep(1.0)
        
        # Verificar si se alcanzó quorum
        quorum = len(self.all_nodes) // 2 + 1
        replicated_count = 1  # Contamos este nodo
        
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                if self.state.match_index.get(node_id, -1) >= entry.index:
                    replicated_count += 1
        
        if replicated_count >= quorum:
            # Commit
            self.state.commit_index = entry.index
            logger.info(
                f"Líder {self.node_id}: Entrada {entry.index} replicada "
                f"({replicated_count}/{len(self.all_nodes)} nodos)"
            )
            return True
        else:
            logger.warning(
                f"Líder {self.node_id}: Entrada {entry.index} "
                f"NO alcanzó quorum "
                f"({replicated_count}/{len(self.all_nodes)} nodos)"
            )
            return False
