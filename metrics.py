"""
Métricas Prometheus para monitoreo.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# Definir métricas
search_requests = Counter(
    'distrisearch_search_requests_total',
    'Total de búsquedas',
    ['node_id']
)

search_latency = Histogram(
    'distrisearch_search_latency_seconds',
    'Latencia de búsquedas',
    ['node_id'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)

index_size = Gauge(
    'distrisearch_index_size_terms',
    'Términos en índice local',
    ['node_id']
)

replication_lag = Gauge(
    'distrisearch_replication_lag_seconds',
    'Lag de replicación',
    ['node_id', 'replica_id']
)

raft_term = Gauge(
    'distrisearch_raft_term',
    'Term actual de Raft',
    ['node_id']
)

raft_state = Gauge(
    'distrisearch_raft_state',
    'Estado Raft (0=follower, 1=candidate, 2=leader)',
    ['node_id']
)


def track_search_metrics(node_id: int):
    """Decorator para medir latencia de búsqueda."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            search_requests.labels(node_id=node_id).inc()
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency = time.time() - start
                search_latency.labels(node_id=node_id).observe(latency)
        return wrapper
    return decorator


def export_metrics() -> bytes:
    """Exporta métricas en formato Prometheus."""
    return generate_latest(REGISTRY)