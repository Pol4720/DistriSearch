"""
Sistema de Coordinación Distribuida para DistriSearch
- Sincronización de tiempo con relojes lógicos de Lamport
"""
import asyncio

class LamportClock:
    """Implementación de relojes lógicos de Lamport"""
    
    def __init__(self):
        self.counter = 0
        self.lock = asyncio.Lock()
    
    async def increment(self) -> int:
        """Incrementa el contador para evento local"""
        async with self.lock:
            self.counter += 1
            return self.counter
    
    async def update(self, received_time: int) -> int:
        """Actualiza reloj al recibir mensaje externo"""
        async with self.lock:
            self.counter = max(self.counter, received_time) + 1
            return self.counter
    
    def get_time(self) -> int:
        """Obtiene tiempo actual del reloj lógico"""
        return self.counter