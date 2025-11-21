"""
Sistema de Coordinación Distribuida para DistriSearch
- Elección de líder por Prueba de Trabajo (PoW)
"""
import hashlib
import time
import asyncio
import logging
from typing import Optional
from datetime import datetime
import os
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

logger = logging.getLogger(__name__)

class ProofOfWorkElection:
    """
    Elección de líder mediante Prueba de Trabajo
    El primer nodo en resolver el desafío criptográfico se convierte en líder
    """
    
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty  # Número de ceros iniciales requeridos
        self.current_challenge = None
        self.current_leader = None
        self.leader_timestamp = None
        self.leader_term = 0  # Término de liderazgo (incrementa con cada elección)
        self.executor = ProcessPoolExecutor(max_workers=multiprocessing.cpu_count())
    
    def generate_challenge(self) -> str:
        """Genera un nuevo desafío para la prueba de trabajo"""
        timestamp = datetime.utcnow().isoformat()
        random_data = os.urandom(16).hex()
        self.current_challenge = f"{timestamp}:{random_data}:{self.leader_term + 1}"
        return self.current_challenge
    
    def verify_proof(self, challenge: str, nonce: int, node_id: str) -> bool:
        """Verifica si la solución es válida"""
        data = f"{challenge}:{node_id}:{nonce}"
        hash_result = hashlib.sha256(data.encode()).hexdigest()
        return hash_result.startswith('0' * self.difficulty)
    
    def _solve_sync(self, challenge: str, node_id: str, max_iterations: int) -> Optional[int]:
        """Versión síncrona para ejecutar en proceso separado"""
        for nonce in range(max_iterations):
            if self.verify_proof(challenge, nonce, node_id):
                return nonce
        return None
    
    async def solve_challenge(self, challenge: str, node_id: str, max_iterations: int = 1000000) -> Optional[int]:
        """
        Versión asíncrona que delega a proceso separado
        """
        loop = asyncio.get_event_loop()
        
        # Ejecutar en proceso separado
        nonce = await loop.run_in_executor(
            self.executor,
            self._solve_sync,
            challenge,
            node_id,
            max_iterations
        )
        
        if nonce is not None:
            logger.info(f"✅ Solución encontrada! Nonce: {nonce}")
        
        return nonce
    
    def set_leader(self, node_id: str, nonce: int, challenge: str):
        """Establece un nuevo líder después de verificar la prueba"""
        if self.verify_proof(challenge, nonce, node_id):
            self.current_leader = node_id
            self.leader_timestamp = datetime.utcnow()
            self.leader_term += 1
            logger.info(f"👑 Nuevo líder elegido: {node_id} (Término: {self.leader_term})")
            return True
        return False