"""
Servicio de métricas de confiabilidad
Implementa tracking de MTTF, MTTR, MTBF
"""
import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from pymongo import MongoClient

logger = logging.getLogger(__name__)


class ReliabilityMetrics:
    """
    Tracking de métricas de confiabilidad del sistema:
    - MTTF: Mean Time To Failure
    - MTTR: Mean Time To Repair
    - MTBF: Mean Time Between Failures (MTTF + MTTR)
    - Disponibilidad: MTTF / (MTTF + MTTR)
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DBNAME", "distrisearch")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        
        self._init_collections()
    
    def _init_collections(self):
        """Inicializa colecciones de métricas"""
        # Eventos de falla
        self.db.failure_events.create_index([("node_id", 1), ("timestamp", -1)])
        self.db.failure_events.create_index([("type", 1)])
        
        # Métricas calculadas
        self.db.reliability_metrics.create_index([("node_id", 1), ("timestamp", -1)])
    
    async def record_failure(self, node_id: str, failure_type: str, details: Dict = None):
        """
        Registra evento de falla
        Tipos: crash, omission, timing, arbitrary
        """
        failure_event = {
            "node_id": node_id,
            "type": failure_type,
            "timestamp": datetime.utcnow(),
            "details": details or {},
            "status": "detected"
        }
        
        self.db.failure_events.insert_one(failure_event)
        logger.warning(f"⚠️ Falla registrada: {node_id} ({failure_type})")
        
        # Marcar nodo como offline
        self.db.nodes.update_one(
            {"node_id": node_id},
            {"$set": {"status": "offline", "last_failure": datetime.utcnow()}}
        )
    
    async def record_recovery(self, node_id: str, recovery_duration_seconds: float):
        """Registra recuperación de falla"""
        # Buscar última falla
        last_failure = self.db.failure_events.find_one(
            {"node_id": node_id, "status": "detected"},
            sort=[("timestamp", -1)]
        )
        
        if last_failure:
            # Actualizar con tiempo de recuperación
            self.db.failure_events.update_one(
                {"_id": last_failure["_id"]},
                {
                    "$set": {
                        "status": "recovered",
                        "recovery_time": datetime.utcnow(),
                        "downtime_seconds": recovery_duration_seconds
                    }
                }
            )
            
            logger.info(f"✅ Recuperación registrada: {node_id} (MTTR: {recovery_duration_seconds:.2f}s)")
    
    def calculate_metrics(self, node_id: str, window_days: int = 30) -> Dict:
        """
        Calcula métricas de confiabilidad para un nodo
        """
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        
        # Obtener fallas en ventana de tiempo
        failures = list(self.db.failure_events.find({
            "node_id": node_id,
            "timestamp": {"$gte": cutoff},
            "status": "recovered"
        }).sort("timestamp", 1))
        
        if not failures:
            return {
                "node_id": node_id,
                "mttf": None,
                "mttr": None,
                "mtbf": None,
                "availability": 1.0,
                "failures_count": 0
            }
        
        # Calcular MTTR (Mean Time To Repair)
        total_downtime = sum(f.get('downtime_seconds', 0) for f in failures)
        mttr = total_downtime / len(failures) if failures else 0
        
        # Calcular MTTF (Mean Time To Failure)
        uptimes = []
        for i in range(len(failures) - 1):
            current_recovery = failures[i].get('recovery_time')
            next_failure = failures[i + 1].get('timestamp')
            
            if current_recovery and next_failure:
                uptime = (next_failure - current_recovery).total_seconds()
                uptimes.append(uptime)
        
        mttf = sum(uptimes) / len(uptimes) if uptimes else 0
        
        # Calcular MTBF
        mtbf = mttf + mttr
        
        # Calcular Disponibilidad
        availability = mttf / mtbf if mtbf > 0 else 1.0
        
        metrics = {
            "node_id": node_id,
            "mttf": mttf,
            "mttr": mttr,
            "mtbf": mtbf,
            "availability": availability,
            "failures_count": len(failures),
            "window_days": window_days,
            "calculated_at": datetime.utcnow()
        }
        
        # Guardar métricas calculadas
        self.db.reliability_metrics.insert_one(metrics)
        
        return metrics
    
    def get_system_reliability(self) -> Dict:
        """Obtiene métricas de confiabilidad del sistema completo"""
        online_nodes = list(self.db.nodes.find({"status": "online"}))
        
        total_availability = 0
        total_mtbf = 0
        nodes_with_data = 0
        
        for node in online_nodes:
            metrics = self.calculate_metrics(node['node_id'])
            
            if metrics['mtbf']:
                total_availability += metrics['availability']
                total_mtbf += metrics['mtbf']
                nodes_with_data += 1
        
        return {
            "system_availability": total_availability / len(online_nodes) if online_nodes else 1.0,
            "average_mtbf": total_mtbf / nodes_with_data if nodes_with_data > 0 else 0,
            "online_nodes": len(online_nodes),
            "total_nodes": self.db.nodes.count_documents({}),
            "timestamp": datetime.utcnow()
        }


# Singleton
_reliability_metrics = None

def get_reliability_metrics() -> ReliabilityMetrics:
    global _reliability_metrics
    if _reliability_metrics is None:
        _reliability_metrics = ReliabilityMetrics()
    return _reliability_metrics