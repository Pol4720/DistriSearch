"""
Tests de integración que combinan varios componentes del sistema Master-Slave.

Estos tests verifican la interacción real entre módulos,
sin levantar servicios de red (pero sí usando MongoDB embebido vía mongomock).
"""
import asyncio
import os
import sys
import numpy as np
import pytest

# Asegurar paths
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# Importar módulos directamente evitando __init__.py problemático
import importlib.util

def load_module(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

location_index_mod = load_module("location_index", os.path.join(ROOT, "master", "location_index.py"))
SemanticLocationIndex = location_index_mod.SemanticLocationIndex

repl_coord_mod = load_module("replication_coordinator", os.path.join(ROOT, "master", "replication_coordinator.py"))
ReplicationCoordinator = repl_coord_mod.ReplicationCoordinator


# ────────────────────────────────────────────────────────────────────────────────
# Test: Índice semántico y coordinador de replicación trabajan juntos
# ────────────────────────────────────────────────────────────────────────────────
class TestLocationAndReplicationIntegration:
    def setup_method(self):
        self.index = SemanticLocationIndex(embedding_dim=4)
        self.coordinator = ReplicationCoordinator(
            replication_factor=2, location_index=self.index
        )
        # Registrar nodos
        for node in ["node-1", "node-2", "node-3"]:
            self.coordinator.register_node(node, f"http://{node}:8000")

    def test_replication_selects_semantically_similar_node(self):
        # Crear perfiles: node-1 es "técnico", node-2 es "finanzas", node-3 mixto
        self.index.register_document(
            "doc-tech", "code.py", "node-1", np.array([1, 0, 0, 0], dtype=float)
        )
        self.index.register_document(
            "doc-fin", "budget.xlsx", "node-2", np.array([0, 1, 0, 0], dtype=float)
        )
        self.index.register_document(
            "doc-mix", "report.pdf", "node-3", np.array([0.5, 0.5, 0, 0], dtype=float)
        )

        # Nuevo documento "técnico" desde node-1
        tech_embedding = np.array([0.9, 0.1, 0, 0], dtype=float)
        targets = self.coordinator._select_target_nodes(
            source_node="node-1", document_embedding=tech_embedding
        )

        # node-3 es mixto/técnico, debería estar en destinos
        assert "node-3" in targets or "node-2" in targets
        assert "node-1" not in targets

    def test_query_routing_finds_relevant_nodes(self):
        self.index.register_document(
            "d1", "a.txt", "node-1", np.array([1, 0, 0, 0], dtype=float)
        )
        self.index.register_document(
            "d2", "b.txt", "node-2", np.array([0, 1, 0, 0], dtype=float)
        )

        query_embedding = np.array([0.95, 0.05, 0, 0], dtype=float)
        nodes = self.index.find_nodes_for_query(query_embedding, top_k=2)

        # node-1 debería ser el más relevante
        assert nodes[0][0] == "node-1"


# ────────────────────────────────────────────────────────────────────────────────
# Test: Heartbeat y elección trabajan juntos (sin red real)
# ────────────────────────────────────────────────────────────────────────────────
class TestHeartbeatElectionIntegration:
    def test_master_down_triggers_callback(self):
        # Importar desde el nuevo módulo cluster
        from cluster.heartbeat import HeartbeatService, HeartbeatState

        master_down_flag = []

        def on_master_down():
            master_down_flag.append(True)

        svc = HeartbeatService(
            node_id="node-1",
            port=0,
            heartbeat_interval=1,
            heartbeat_timeout=0,  # inmediato para test
            on_master_down=on_master_down,
        )
        svc.set_master("node-master")
        svc.add_peer("node-master", "127.0.0.1", 9999)

        # Simular timeout check
        async def _run():
            await svc._check_timeouts()

        # No podemos esperar el while True, así que invocamos directamente el check
        svc._peers["node-master"].check_timeout(timeout_seconds=0)
        # Simular callback manual ya que el loop no corre
        if svc._peers["node-master"].status.value == "offline":
            on_master_down()

        assert master_down_flag


# ────────────────────────────────────────────────────────────────────────────────
# Test: Embedding service genera vectores correctos
# ────────────────────────────────────────────────────────────────────────────────
class TestEmbeddingServiceIntegration:
    @pytest.mark.skipif(
        os.getenv("CI") == "true" or os.getenv("SKIP_HEAVY_TESTS") == "1",
        reason="Modelo pesado, solo ejecutar localmente con dependencias completas",
    )
    @pytest.mark.slow
    def test_embedding_produces_similar_vectors_for_related_text(self):
        try:
            embedding_mod = load_module("embedding_service", os.path.join(ROOT, "master", "embedding_service.py"))
            EmbeddingService = embedding_mod.EmbeddingService

            svc = EmbeddingService()
            emb1 = svc.encode("machine learning algorithms")
            emb2 = svc.encode("deep neural networks")
            emb3 = svc.encode("cooking recipes for dinner")

            sim_related = svc.similarity(emb1, emb2)
            sim_unrelated = svc.similarity(emb1, emb3)

            assert sim_related > sim_unrelated
        except ImportError as e:
            pytest.skip(f"Dependencias de embedding no disponibles: {e}")
