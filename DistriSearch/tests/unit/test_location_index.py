import sys
import os

# Setup path para imports directos (evitar __init__.py que tiene imports relativos)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np
import pytest

# Importar directamente sin pasar por master/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "location_index",
    os.path.join(ROOT, "master", "location_index.py")
)
location_index_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(location_index_module)
SemanticLocationIndex = location_index_module.SemanticLocationIndex


def test_register_document_dimension_mismatch():
    index = SemanticLocationIndex(embedding_dim=4)
    bad_embedding = np.ones(3)

    with pytest.raises(ValueError):
        index.register_document(
            file_id="doc-1",
            filename="file.txt",
            node_id="node-a",
            embedding=bad_embedding,
        )


def test_search_orders_by_similarity_and_filters_nodes():
    index = SemanticLocationIndex(embedding_dim=4)

    index.register_document("d1", "a.txt", "node-1", np.array([1, 0, 0, 0], dtype=float))
    index.register_document("d2", "b.txt", "node-2", np.array([0, 1, 0, 0], dtype=float))

    query = np.array([0.9, 0.1, 0, 0], dtype=float)
    results = index.search(query, top_k=2)

    assert [doc.node_id for doc, _ in results] == ["node-1", "node-2"]

    filtered = index.search(query, top_k=2, node_filter=["node-2"])
    assert filtered[0][0].node_id == "node-2"


def test_select_replica_nodes_uses_affinity_and_excludes_source():
    index = SemanticLocationIndex(embedding_dim=4)

    # Perfiles: node-1 orientado al eje X, node-2 al eje Y, node-3 mixto
    index.register_document("d1", "a.txt", "node-1", np.array([1, 0, 0, 0], dtype=float))
    index.register_document("d2", "b.txt", "node-2", np.array([0, 1, 0, 0], dtype=float))
    index.register_document("d3", "c.txt", "node-3", np.array([0.7, 0.7, 0, 0], dtype=float))

    target_embedding = np.array([0.8, 0.2, 0, 0], dtype=float)
    selected = index.select_replica_nodes(
        source_node="node-1",
        document_embedding=target_embedding,
        replication_factor=2,
    )

    assert "node-1" not in selected
    assert "node-2" in selected or "node-3" in selected
    assert len(selected) == 2
