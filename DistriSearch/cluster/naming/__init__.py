"""
DistriSearch Cluster - Módulo de Naming

Sistema de nombres jerárquico y cache de IPs:
- HierarchicalNamespace: Organización jerárquica de archivos (estilo Unix)
- IPCache: Cache LRU de información de nodos
"""

from .hierarchical import HierarchicalNamespace, NamespaceNode, get_namespace
from .ip_cache import IPCache, get_ip_cache

__all__ = [
    "HierarchicalNamespace",
    "NamespaceNode",
    "get_namespace",
    "IPCache",
    "get_ip_cache",
]
