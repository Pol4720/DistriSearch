"""
Configuración y verificación de quorum.
"""
from typing import Set
from dataclasses import dataclass


@dataclass
class QuorumConfig:
    """Configuración de quorum para replicación."""
    
    replication_factor: int = 3  # k réplicas
    write_quorum: int = 2  # Mínimo para escritura
    read_quorum: int = 2  # Mínimo para lectura
    
    def __post_init__(self):
        """Validación de configuración."""
        # Quorum debe ser mayoría
        majority = (self.replication_factor // 2) + 1
        
        if self.write_quorum < majority:
            raise ValueError(
                f"write_quorum ({self.write_quorum}) debe ser >= "
                f"mayoría ({majority})"
            )
        
        if self.read_quorum < 1:
            raise ValueError("read_quorum debe ser >= 1")
        
        # write_quorum + read_quorum > replication_factor
        # garantiza que lecturas vean últimas escrituras
        if self.write_quorum + self.read_quorum <= self.replication_factor:
            raise ValueError(
                f"write_quorum ({self.write_quorum}) + "
                f"read_quorum ({self.read_quorum}) debe ser > "
                f"replication_factor ({self.replication_factor})"
            )


def verify_quorum(
    successful: Set[int],
    required: int,
    replication_factor: int
) -> bool:
    """
    Verifica si se alcanzó quorum.
    
    Args:
        successful: Conjunto de nodos que respondieron exitosamente
        required: Número mínimo requerido
        replication_factor: Factor de replicación total
        
    Returns:
        True si se alcanzó quorum
    """
    return len(successful) >= required


def calculate_quorum(replication_factor: int) -> int:
    """
    Calcula el quorum (mayoría) para un factor de replicación.
    
    Args:
        replication_factor: Factor de replicación (k)
        
    Returns:
        Tamaño de quorum (⌊k/2⌋ + 1)
    """
    return (replication_factor // 2) + 1
