"""
Tests para el módulo de almacenamiento (índice invertido).
"""
import pytest
import tempfile
import shutil
import os
from storage import InvertedIndex, Document


@pytest.fixture
def temp_storage_dir():
    """Fixture que crea directorio temporal para tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_index_creation(temp_storage_dir):
    """Test creación de índice."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    assert index.node_id == 1
    assert len(index.index) == 0
    assert len(index.documents) == 0


def test_tokenize():
    """Test tokenización de texto."""
    index = InvertedIndex(node_id=1)
    
    tokens = index.tokenize("Python es un lenguaje de programación")
    
    # Debe eliminar stopwords y convertir a lowercase
    assert "python" in tokens
    assert "lenguaje" in tokens
    assert "programación" in tokens
    
    # Stopwords no deben estar
    assert "es" not in tokens
    assert "un" not in tokens
    assert "de" not in tokens


def test_add_document(temp_storage_dir):
    """Test añadir documento."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    content = "Python es excelente para machine learning"
    terms = index.add_document("doc1", content)
    
    # Verificar términos extraídos
    assert "python" in terms
    assert "excelente" in terms
    assert "machine" in terms
    assert "learning" in terms
    
    # Verificar que el documento está almacenado
    assert "doc1" in index.documents
    
    # Verificar índice invertido
    assert "python" in index.index
    assert "doc1" in index.index["python"]


def test_remove_document(temp_storage_dir):
    """Test eliminar documento."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    index.add_document("doc1", "Python programming")
    index.add_document("doc2", "Java programming")
    
    # Eliminar doc1
    terms_removed = index.remove_document("doc1")
    
    # Python solo estaba en doc1, debe ser removido
    assert "python" in terms_removed
    
    # Programming estaba en ambos, no debe ser removido
    assert "programming" not in terms_removed
    
    # Verificar índice
    assert "doc1" not in index.documents
    assert "python" not in index.index
    assert "programming" in index.index
    assert "doc2" in index.index["programming"]


def test_search(temp_storage_dir):
    """Test búsqueda de documentos."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    # Añadir documentos
    index.add_document("doc1", "Python es genial para machine learning")
    index.add_document("doc2", "Java es usado en desarrollo empresarial")
    index.add_document("doc3", "Python y Java son lenguajes populares")
    
    # Buscar "python"
    results = index.search("python")
    
    # Debe encontrar doc1 y doc3
    doc_ids = [doc_id for doc_id, _ in results]
    assert "doc1" in doc_ids
    assert "doc3" in doc_ids
    assert "doc2" not in doc_ids


def test_search_multiple_terms(temp_storage_dir):
    """Test búsqueda con múltiples términos."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    index.add_document("doc1", "Python machine learning")
    index.add_document("doc2", "Python web development")
    index.add_document("doc3", "Java machine learning")
    
    # Buscar "python machine"
    results = index.search("python machine")
    
    # doc1 debe tener mayor score (contiene ambos términos)
    assert len(results) > 0
    assert results[0][0] == "doc1"


def test_search_ranking(temp_storage_dir):
    """Test ranking de resultados."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    # Documento con múltiples ocurrencias
    index.add_document("doc1", "python python python programming")
    index.add_document("doc2", "python programming")
    
    results = index.search("python")
    
    # doc1 debe tener mayor score (más ocurrencias)
    assert results[0][0] == "doc1"
    assert results[0][1] > results[1][1]


def test_get_terms(temp_storage_dir):
    """Test obtener todos los términos."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    index.add_document("doc1", "Python programming")
    index.add_document("doc2", "Java development")
    
    terms = index.get_terms()
    
    assert "python" in terms
    assert "programming" in terms
    assert "java" in terms
    assert "development" in terms


def test_persistence(temp_storage_dir):
    """Test guardar y cargar índice."""
    # Crear índice y añadir datos
    index1 = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    index1.add_document("doc1", "Python programming")
    index1.save()
    
    # Crear nuevo índice desde mismo directorio
    index2 = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    # Debe cargar los datos guardados
    assert "doc1" in index2.documents
    assert "python" in index2.index
    
    # Búsqueda debe funcionar
    results = index2.search("python")
    assert len(results) > 0


def test_get_document(temp_storage_dir):
    """Test obtener documento por ID."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    content = "Python es genial"
    metadata = {"author": "test"}
    
    index.add_document("doc1", content, metadata)
    
    doc = index.get_document("doc1")
    
    assert doc is not None
    assert doc.doc_id == "doc1"
    assert doc.content == content
    assert doc.metadata["author"] == "test"


def test_stats(temp_storage_dir):
    """Test estadísticas del índice."""
    index = InvertedIndex(node_id=1, persist_path=temp_storage_dir)
    
    index.add_document("doc1", "Python programming")
    index.add_document("doc2", "Java programming")
    
    stats = index.get_stats()
    
    assert stats['num_documents'] == 2
    assert stats['num_terms'] > 0
    assert stats['total_postings'] > 0
