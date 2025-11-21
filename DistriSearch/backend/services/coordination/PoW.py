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
from coordinator import logger

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
    
    async def solve_challenge(self, challenge: str, node_id: str, max_iterations: int = 1000000) -> Optional[int]:
        """
        Intenta resolver el desafío de prueba de trabajo
        Retorna el nonce si encuentra solución, None si no
        """
        for nonce in range(max_iterations):
            if self.verify_proof(challenge, nonce, node_id):
                logger.info(f"✅ Solución encontrada! Nonce: {nonce}")
                return nonce
            
            # Yield cada 1000 iteraciones para no bloquear
            if nonce % 1000 == 0:
                await asyncio.sleep(0)
        
        return None
    
    def set_leader(self, node_id: str, nonce: int, challenge: str):
        """Establece un nuevo líder después de verificar la prueba"""
        if self.verify_proof(challenge, nonce, node_id):
            self.current_leader = node_id
            self.leader_timestamp = datetime.utcnow()
            self.leader_term += 1
            logger.info(f"👑 Nuevo líder elegido: {node_id} (Término: {self.leader_term})")
            return True
        return False