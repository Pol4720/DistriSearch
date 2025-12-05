"""
Tests unitarios para SemanticLocationIndex
Valida el índice de ubicación semántica
"""
import pytest
import numpy as np
import sys
import os

# Añadir path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master.location_index import SemanticLocationIndex, DocumentLocation


class TestSemanticLocationIndex:
    """Tests para el índice de ubicación semántica"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup antes de cada test"""
        self.index = SemanticLocationIndex(embedding_dim=384)
        yield
    
    def _random_embedding(self, dim=384):
        """Genera embedding aleatorio normalizado"""
        emb = np.random.randn(dim).astype(np.float32)
        return emb / np.linalg.norm(emb)
    
    @pytest.mark.critical
    def test_register_document(self):
        """TEST: Registrar documento en el índice"""
        print("\n" + "="*60)
        print("TEST: register_document()")
        print("="*60)
        
        file_id = "doc_001"
        filename = "manual.pdf"
        node_id = "node_1"
        embedding = self._random_embedding()
        
        self.index.register_document(
            file_id=file_id,
            filename=filename,
            node_id=node_id,
            embedding=embedding
        )
        
        assert file_id in self.index._documents, "Documento debe estar registrado"
        doc = self.index._documents[file_id]
        assert doc.node_id == node_id
        assert doc.filename == filename
        print("✅ Documento registrado correctamente")
    
    @pytest.mark.critical
    def test_search_by_similarity(self):
        """TEST: Búsqueda por similitud semántica"""
        print("\n" + "="*60)
        print("TEST: search() por similitud")
        print("="*60)
        
        # Registrar documentos con embeddings conocidos
        base_embedding = self._random_embedding()
        
        # Documento similar (pequeña perturbación)
        similar_emb = base_embedding + 0.1 * self._random_embedding()
        similar_emb = similar_emb / np.linalg.norm(similar_emb)
        
        # Documento diferente
        different_emb = self._random_embedding()
        
        self.index.register_document("doc_similar", "similar.txt", "node_1", similar_emb)
        self.index.register_document("doc_different", "different.txt", "node_2", different_emb)
        
        # Buscar con query similar al primer documento
        results = self.index.search(base_embedding, top_k=2)
        
        assert len(results) == 2, "Deben retornar 2 resultados"
        assert results[0][0] == "doc_similar", "El más similar debe ser el primero"
        print(f"✅ Resultados ordenados por similitud: {[r[0] for r in results]}")
    
    @pytest.mark.critical
    def test_find_nodes_for_query(self):
        """TEST: Encontrar nodos relevantes para una query"""
        print("\n" + "="*60)
        print("TEST: find_nodes_for_query()")
        print("="*60)
        
        # Registrar documentos en diferentes nodos
        for i in range(5):
            self.index.register_document(
                f"doc_{i}",
                f"file_{i}.txt",
                f"node_{i % 3}",  # 3 nodos diferentes
                self._random_embedding()
            )
        
        query_embedding = self._random_embedding()
        nodes = self.index.find_nodes_for_query(query_embedding, max_nodes=2)
        
        assert len(nodes) <= 2, "No debe retornar más de max_nodes"
        assert all(isinstance(n, str) for n in nodes), "Deben ser IDs de nodos"
        print(f"✅ Nodos relevantes: {nodes}")
    
    @pytest.mark.critical
    def test_select_replica_nodes(self):
        """TEST: Seleccionar nodos para replicación por afinidad"""
        print("\n" + "="*60)
        print("TEST: select_replica_nodes()")
        print("="*60)
        
        # Registrar documentos
        for i in range(6):
            self.index.register_document(
                f"doc_{i}",
                f"file_{i}.txt",
                f"node_{i % 3}",
                self._random_embedding()
            )
        
        doc_embedding = self._random_embedding()
        source_node = "node_0"
        
        replica_nodes = self.index.select_replica_nodes(
            doc_embedding,
            source_node=source_node,
            count=2
        )
        
        assert source_node not in replica_nodes, "No debe incluir el nodo fuente"
        assert len(replica_nodes) <= 2, "No debe exceder el count"
        print(f"✅ Nodos para réplica: {replica_nodes}")
    
    def test_update_slave_profile(self):
        """TEST: Actualizar perfil de Slave"""
        print("\n" + "="*60)
        print("TEST: Actualización de perfiles de Slaves")
        print("="*60)
        
        node_id = "node_test"
        
        # Registrar varios documentos del mismo nodo
        for i in range(3):
            self.index.register_document(
                f"doc_{i}",
                f"file_{i}.txt",
                node_id,
                self._random_embedding()
            )
        
        assert node_id in self.index._slave_profiles, "Debe tener perfil del nodo"
        profile = self.index._slave_profiles[node_id]
        assert profile.get("document_count", 0) >= 3, "Debe contar documentos"
        print(f"✅ Perfil actualizado: {profile}")
    
    def test_remove_document(self):
        """TEST: Eliminar documento del índice"""
        print("\n" + "="*60)
        print("TEST: Eliminar documento")
        print("="*60)
        
        file_id = "doc_to_remove"
        self.index.register_document(
            file_id,
            "remove_me.txt",
            "node_1",
            self._random_embedding()
        )
        
        assert file_id in self.index._documents
        
        self.index.remove_document(file_id)
        
        assert file_id not in self.index._documents, "Documento debe ser eliminado"
        print("✅ Documento eliminado correctamente")
    
    def test_get_node_documents(self):
        """TEST: Obtener documentos de un nodo"""
        print("\n" + "="*60)
        print("TEST: get_node_documents()")
        print("="*60)
        
        target_node = "node_target"
        
        # Registrar documentos en varios nodos
        self.index.register_document("doc_1", "a.txt", target_node, self._random_embedding())
        self.index.register_document("doc_2", "b.txt", target_node, self._random_embedding())
        self.index.register_document("doc_3", "c.txt", "other_node", self._random_embedding())
        
        docs = self.index.get_node_documents(target_node)
        
        assert len(docs) == 2, "Debe retornar solo documentos del nodo objetivo"
        assert all(d.node_id == target_node for d in docs)
        print(f"✅ Documentos del nodo: {[d.file_id for d in docs]}")
    
    def test_embedding_dimension_validation(self):
        """TEST: Validación de dimensión de embedding"""
        print("\n" + "="*60)
        print("TEST: Validación de dimensión")
        print("="*60)
        
        wrong_dim_embedding = np.random.randn(100).astype(np.float32)  # Dimensión incorrecta
        
        with pytest.raises(ValueError):
            self.index.register_document(
                "doc_wrong",
                "wrong.txt",
                "node_1",
                wrong_dim_embedding
            )
        
        print("✅ Validación de dimensión funciona correctamente")
    
    def test_statistics(self):
        """TEST: Obtener estadísticas del índice"""
        print("\n" + "="*60)
        print("TEST: Estadísticas del índice")
        print("="*60)
        
        # Registrar documentos
        for i in range(5):
            self.index.register_document(
                f"doc_{i}",
                f"file_{i}.txt",
                f"node_{i % 2}",
                self._random_embedding()
            )
        
        stats = self.index.get_statistics()
        
        assert stats["total_documents"] == 5
        assert stats["total_nodes"] == 2
        print(f"✅ Estadísticas: {stats}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
