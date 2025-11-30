"""
Módulo de sharding para particionamiento de datos.
Distribuye la carga del Data Balancer usando consistent hashing.
"""
from sharding.hash_strategy import ConsistentHash, hash_term
from sharding.shard_manager import ShardManager
from sharding.shard_coordinator import ShardCoordinator

__all__ = [
    "ConsistentHash",
    "hash_term",
    "ShardManager",
    "ShardCoordinator",
]
