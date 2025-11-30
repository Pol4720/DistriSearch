"""
Gestión de snapshots del Data Balancer.
"""
import logging
from typing import Dict, Optional
from balancer.balancer_core import DataBalancer
from storage.persistence import PersistenceManager

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Gestiona snapshots del estado del Data Balancer."""
    
    def __init__(self, balancer: DataBalancer, persistence: PersistenceManager):
        """
        Inicializa el gestor de snapshots.
        
        Args:
            balancer: Instancia de DataBalancer
            persistence: Gestor de persistencia
        """
        self.balancer = balancer
        self.persistence = persistence
    
    def save_snapshot(self, name: str = "latest") -> bool:
        """
        Guarda un snapshot del estado actual.
        
        Args:
            name: Nombre del snapshot
            
        Returns:
            True si se guardó exitosamente
        """
        try:
            data = self.balancer.to_dict()
            success = self.persistence.snapshot(name, data)
            
            if success:
                logger.info(f"Snapshot '{name}' guardado")
            else:
                logger.error(f"Error guardando snapshot '{name}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Excepción guardando snapshot '{name}': {e}")
            return False
    
    def load_snapshot(self, name: str = "latest") -> bool:
        """
        Carga un snapshot.
        
        Args:
            name: Nombre del snapshot
            
        Returns:
            True si se cargó exitosamente
        """
        try:
            data = self.persistence.load_snapshot(name)
            
            if data is None:
                logger.warning(f"Snapshot '{name}' no encontrado")
                return False
            
            self.balancer.from_dict(data)
            logger.info(f"Snapshot '{name}' cargado")
            return True
            
        except Exception as e:
            logger.error(f"Excepción cargando snapshot '{name}': {e}")
            return False
    
    def list_snapshots(self) -> list:
        """Lista todos los snapshots disponibles."""
        return self.persistence.list_snapshots()
    
    def delete_snapshot(self, name: str) -> bool:
        """
        Elimina un snapshot.
        
        Args:
            name: Nombre del snapshot
            
        Returns:
            True si se eliminó
        """
        filename = f"snapshots/{name}.json"
        return self.persistence.delete_file(filename)
