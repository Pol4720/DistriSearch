"""
Tests unitarios para EmbeddingService
Valida la generación de embeddings semánticos
"""
import pytest
import numpy as np
import sys
import os

# Añadir path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master.embedding_service import EmbeddingService, get_embedding_service


class TestEmbeddingService:
    """Tests para el servicio de embeddings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup antes de cada test"""
        self.service = EmbeddingService()
        yield
    
    @pytest.mark.critical
    def test_singleton_instance(self):
        """TEST: get_embedding_service retorna singleton"""
        print("\n" + "="*60)
        print("TEST: Singleton de EmbeddingService")
        print("="*60)
        
        service1 = get_embedding_service()
        service2 = get_embedding_service()
        
        assert service1 is service2, "Deben ser la misma instancia"
        print("✅ Singleton funciona correctamente")
    
    @pytest.mark.critical
    def test_encode_text_returns_numpy_array(self):
        """TEST: encode() retorna array numpy"""
        print("\n" + "="*60)
        print("TEST: encode() retorna numpy array")
        print("="*60)
        
        text = "Este es un texto de prueba para embeddings"
        embedding = self.service.encode(text)
        
        assert isinstance(embedding, np.ndarray), "Debe ser numpy array"
        assert len(embedding.shape) == 1, "Debe ser vector 1D"
        print(f"✅ Embedding shape: {embedding.shape}")
    
    @pytest.mark.critical
    def test_encode_batch_texts(self):
        """TEST: encode() con lista de textos"""
        print("\n" + "="*60)
        print("TEST: Batch encoding")
        print("="*60)
        
        texts = [
            "Documento sobre inteligencia artificial",
            "Receta de cocina italiana",
            "Manual de programación Python"
        ]
        embeddings = self.service.encode(texts)
        
        assert isinstance(embeddings, np.ndarray), "Debe ser numpy array"
        assert embeddings.shape[0] == len(texts), f"Deben ser {len(texts)} embeddings"
        print(f"✅ Batch embeddings shape: {embeddings.shape}")
    
    @pytest.mark.critical
    def test_embedding_dimension(self):
        """TEST: Dimensión del embedding es correcta"""
        print("\n" + "="*60)
        print("TEST: Dimensión de embeddings")
        print("="*60)
        
        text = "Texto de prueba"
        embedding = self.service.encode(text)
        
        expected_dim = self.service.embedding_dim
        assert embedding.shape[0] == expected_dim, f"Debe tener {expected_dim} dimensiones"
        print(f"✅ Dimensión: {expected_dim}")
    
    @pytest.mark.critical
    def test_similar_texts_have_high_similarity(self):
        """TEST: Textos similares tienen alta similitud"""
        print("\n" + "="*60)
        print("TEST: Similitud de textos relacionados")
        print("="*60)
        
        text1 = "Python es un lenguaje de programación"
        text2 = "Python es un lenguaje para programar"
        text3 = "Receta de paella valenciana"
        
        emb1 = self.service.encode(text1)
        emb2 = self.service.encode(text2)
        emb3 = self.service.encode(text3)
        
        sim_related = self.service.similarity(emb1, emb2)
        sim_unrelated = self.service.similarity(emb1, emb3)
        
        print(f"Similitud textos relacionados: {sim_related:.4f}")
        print(f"Similitud textos no relacionados: {sim_unrelated:.4f}")
        
        assert sim_related > sim_unrelated, "Textos relacionados deben tener mayor similitud"
        assert sim_related > 0.7, "Textos muy similares deben tener similitud > 0.7"
        print("✅ Similitud semántica funciona correctamente")
    
    @pytest.mark.critical
    def test_encode_document(self):
        """TEST: encode_document() genera embedding para documento"""
        print("\n" + "="*60)
        print("TEST: encode_document()")
        print("="*60)
        
        filename = "manual_python.pdf"
        content = "Este manual explica los fundamentos de Python y sus aplicaciones"
        
        embedding = self.service.encode_document(filename, content)
        
        assert isinstance(embedding, np.ndarray), "Debe ser numpy array"
        assert embedding.shape[0] == self.service.embedding_dim
        print(f"✅ Document embedding shape: {embedding.shape}")
    
    @pytest.mark.critical
    def test_encode_query(self):
        """TEST: encode_query() genera embedding para búsqueda"""
        print("\n" + "="*60)
        print("TEST: encode_query()")
        print("="*60)
        
        query = "¿Cómo programar en Python?"
        embedding = self.service.encode_query(query)
        
        assert isinstance(embedding, np.ndarray), "Debe ser numpy array"
        assert embedding.shape[0] == self.service.embedding_dim
        print(f"✅ Query embedding shape: {embedding.shape}")
    
    def test_normalized_embeddings(self):
        """TEST: Embeddings están normalizados por defecto"""
        print("\n" + "="*60)
        print("TEST: Normalización de embeddings")
        print("="*60)
        
        text = "Texto para verificar normalización"
        embedding = self.service.encode(text, normalize=True)
        
        norm = np.linalg.norm(embedding)
        
        assert abs(norm - 1.0) < 0.01, f"Norma debe ser ~1.0, got {norm}"
        print(f"✅ Norma del embedding: {norm:.6f}")
    
    def test_batch_similarity(self):
        """TEST: batch_similarity() calcula similitudes múltiples"""
        print("\n" + "="*60)
        print("TEST: batch_similarity()")
        print("="*60)
        
        query = "Programación en Python"
        documents = [
            "Tutorial de Python para principiantes",
            "Receta de cocina mediterránea",
            "Guía de desarrollo de software"
        ]
        
        query_emb = self.service.encode(query)
        doc_embs = self.service.encode(documents)
        
        similarities = self.service.batch_similarity(query_emb, doc_embs)
        
        assert len(similarities) == len(documents), "Debe haber una similitud por documento"
        assert all(0 <= s <= 1 for s in similarities), "Similitudes deben estar en [0, 1]"
        
        print(f"Similitudes: {similarities}")
        print("✅ batch_similarity funciona correctamente")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
