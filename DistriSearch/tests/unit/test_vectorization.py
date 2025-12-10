"""
Unit Tests for Vectorization Module
Tests TF-IDF, MinHash LSH, and LDA implementations
"""

import pytest
import numpy as np
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vectorization.tfidf import TFIDFVectorizer
from vectorization.minhash import MinHashLSH
from vectorization.lda import LDATopicModel
from vectorization.pipeline import VectorizationPipeline
from shared.models import Document


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_documents() -> List[str]:
    """Sample documents for testing"""
    return [
        "Machine learning is a subset of artificial intelligence that enables systems to learn.",
        "Deep learning uses neural networks with many layers to process complex data.",
        "Natural language processing helps computers understand human language.",
        "Computer vision enables machines to interpret visual information from the world.",
        "Data science combines statistics, programming, and domain expertise.",
        "Python is a popular programming language for machine learning applications.",
        "TensorFlow and PyTorch are popular deep learning frameworks.",
        "Supervised learning uses labeled data to train predictive models.",
        "Unsupervised learning finds patterns in unlabeled data sets.",
        "Reinforcement learning trains agents through rewards and penalties."
    ]


@pytest.fixture
def document_objects(sample_documents: List[str]) -> List[Document]:
    """Convert sample documents to Document objects"""
    return [
        Document(
            id=f"doc_{i}",
            title=f"Document {i}",
            content=doc,
            metadata={"index": i}
        )
        for i, doc in enumerate(sample_documents)
    ]


@pytest.fixture
def tfidf_vectorizer() -> TFIDFVectorizer:
    """Create TF-IDF vectorizer instance"""
    return TFIDFVectorizer(
        max_features=1000,
        min_df=1,
        max_df=0.95
    )


@pytest.fixture
def minhash_lsh() -> MinHashLSH:
    """Create MinHash LSH instance"""
    return MinHashLSH(
        num_perm=128,
        threshold=0.5,
        num_bands=32
    )


@pytest.fixture
def lda_model() -> LDATopicModel:
    """Create LDA model instance"""
    return LDATopicModel(
        n_topics=5,
        n_iterations=50,
        alpha=0.1,
        beta=0.01
    )


# ============================================================================
# TF-IDF Tests
# ============================================================================

class TestTFIDFVectorizer:
    """Tests for TF-IDF vectorization"""
    
    def test_initialization(self, tfidf_vectorizer: TFIDFVectorizer):
        """Test vectorizer initialization"""
        assert tfidf_vectorizer is not None
        assert tfidf_vectorizer.max_features == 1000
        assert tfidf_vectorizer.min_df == 1
        assert tfidf_vectorizer.max_df == 0.95
    
    def test_fit(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test fitting the vectorizer"""
        tfidf_vectorizer.fit(sample_documents)
        
        assert tfidf_vectorizer.vocabulary is not None
        assert len(tfidf_vectorizer.vocabulary) > 0
        assert tfidf_vectorizer.idf_values is not None
    
    def test_transform(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test transforming documents"""
        tfidf_vectorizer.fit(sample_documents)
        vectors = tfidf_vectorizer.transform(sample_documents)
        
        assert vectors is not None
        assert len(vectors) == len(sample_documents)
        
        # Check vector properties
        for vec in vectors:
            assert isinstance(vec, np.ndarray)
            assert len(vec) > 0
    
    def test_fit_transform(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test fit_transform method"""
        vectors = tfidf_vectorizer.fit_transform(sample_documents)
        
        assert vectors is not None
        assert len(vectors) == len(sample_documents)
    
    def test_transform_single_document(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test transforming a single document"""
        tfidf_vectorizer.fit(sample_documents)
        
        query = "machine learning neural networks"
        vector = tfidf_vectorizer.transform_query(query)
        
        assert vector is not None
        assert isinstance(vector, np.ndarray)
    
    def test_vocabulary_consistency(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test vocabulary remains consistent after fitting"""
        tfidf_vectorizer.fit(sample_documents)
        vocab_before = tfidf_vectorizer.vocabulary.copy()
        
        # Transform new documents
        tfidf_vectorizer.transform(["new document with different words"])
        
        assert tfidf_vectorizer.vocabulary == vocab_before
    
    def test_empty_document(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test handling of empty documents"""
        tfidf_vectorizer.fit(sample_documents)
        
        vector = tfidf_vectorizer.transform_query("")
        assert vector is not None
        assert np.all(vector == 0)
    
    def test_serialization(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test model serialization and deserialization"""
        tfidf_vectorizer.fit(sample_documents)
        
        # Serialize
        state = tfidf_vectorizer.to_dict()
        
        # Deserialize
        new_vectorizer = TFIDFVectorizer.from_dict(state)
        
        assert new_vectorizer.vocabulary == tfidf_vectorizer.vocabulary
        assert np.allclose(new_vectorizer.idf_values, tfidf_vectorizer.idf_values)


# ============================================================================
# MinHash LSH Tests
# ============================================================================

class TestMinHashLSH:
    """Tests for MinHash LSH"""
    
    def test_initialization(self, minhash_lsh: MinHashLSH):
        """Test MinHash initialization"""
        assert minhash_lsh is not None
        assert minhash_lsh.num_perm == 128
        assert minhash_lsh.threshold == 0.5
    
    def test_compute_signature(self, minhash_lsh: MinHashLSH):
        """Test computing MinHash signature"""
        text = "machine learning is great"
        signature = minhash_lsh.compute_signature(text)
        
        assert signature is not None
        assert len(signature) == minhash_lsh.num_perm
    
    def test_signature_consistency(self, minhash_lsh: MinHashLSH):
        """Test that same text produces same signature"""
        text = "consistent hashing test"
        
        sig1 = minhash_lsh.compute_signature(text)
        sig2 = minhash_lsh.compute_signature(text)
        
        assert np.array_equal(sig1, sig2)
    
    def test_add_document(self, minhash_lsh: MinHashLSH):
        """Test adding documents to index"""
        minhash_lsh.add_document("doc1", "machine learning algorithms")
        minhash_lsh.add_document("doc2", "deep learning neural networks")
        
        assert minhash_lsh.get_document_count() == 2
    
    def test_query_similar(self, minhash_lsh: MinHashLSH, sample_documents: List[str]):
        """Test querying for similar documents"""
        # Add documents
        for i, doc in enumerate(sample_documents):
            minhash_lsh.add_document(f"doc_{i}", doc)
        
        # Query
        similar = minhash_lsh.query("machine learning neural networks")
        
        assert isinstance(similar, list)
        # Should find at least some candidates
    
    def test_jaccard_similarity(self, minhash_lsh: MinHashLSH):
        """Test Jaccard similarity estimation"""
        text1 = "machine learning is a field of study"
        text2 = "machine learning is used for predictions"
        text3 = "cooking recipes and food preparation"
        
        sig1 = minhash_lsh.compute_signature(text1)
        sig2 = minhash_lsh.compute_signature(text2)
        sig3 = minhash_lsh.compute_signature(text3)
        
        sim_12 = minhash_lsh.estimate_similarity(sig1, sig2)
        sim_13 = minhash_lsh.estimate_similarity(sig1, sig3)
        
        # Similar texts should have higher similarity
        assert sim_12 > sim_13
    
    def test_remove_document(self, minhash_lsh: MinHashLSH):
        """Test removing documents from index"""
        minhash_lsh.add_document("doc1", "test document")
        minhash_lsh.add_document("doc2", "another document")
        
        assert minhash_lsh.get_document_count() == 2
        
        minhash_lsh.remove_document("doc1")
        
        assert minhash_lsh.get_document_count() == 1
    
    def test_clear_index(self, minhash_lsh: MinHashLSH, sample_documents: List[str]):
        """Test clearing the index"""
        for i, doc in enumerate(sample_documents):
            minhash_lsh.add_document(f"doc_{i}", doc)
        
        assert minhash_lsh.get_document_count() > 0
        
        minhash_lsh.clear()
        
        assert minhash_lsh.get_document_count() == 0


# ============================================================================
# LDA Tests
# ============================================================================

class TestLDATopicModel:
    """Tests for LDA Topic Model"""
    
    def test_initialization(self, lda_model: LDATopicModel):
        """Test LDA model initialization"""
        assert lda_model is not None
        assert lda_model.n_topics == 5
        assert lda_model.alpha == 0.1
        assert lda_model.beta == 0.01
    
    def test_fit(self, lda_model: LDATopicModel, sample_documents: List[str]):
        """Test fitting the LDA model"""
        lda_model.fit(sample_documents)
        
        assert lda_model.vocabulary is not None
        assert len(lda_model.vocabulary) > 0
        assert lda_model.topic_word_distribution is not None
    
    def test_transform(self, lda_model: LDATopicModel, sample_documents: List[str]):
        """Test getting topic distributions for documents"""
        lda_model.fit(sample_documents)
        distributions = lda_model.transform(sample_documents)
        
        assert distributions is not None
        assert len(distributions) == len(sample_documents)
        
        # Check distribution properties
        for dist in distributions:
            assert len(dist) == lda_model.n_topics
            assert abs(sum(dist) - 1.0) < 0.01  # Should sum to ~1
            assert all(p >= 0 for p in dist)  # All probabilities non-negative
    
    def test_get_topics(self, lda_model: LDATopicModel, sample_documents: List[str]):
        """Test getting top words for each topic"""
        lda_model.fit(sample_documents)
        topics = lda_model.get_topics(n_words=10)
        
        assert topics is not None
        assert len(topics) == lda_model.n_topics
        
        for topic_words in topics:
            assert len(topic_words) <= 10
    
    def test_infer_topics(self, lda_model: LDATopicModel, sample_documents: List[str]):
        """Test inferring topics for new document"""
        lda_model.fit(sample_documents)
        
        query = "neural networks deep learning artificial intelligence"
        distribution = lda_model.infer_topics(query)
        
        assert distribution is not None
        assert len(distribution) == lda_model.n_topics
        assert abs(sum(distribution) - 1.0) < 0.01


# ============================================================================
# Pipeline Tests
# ============================================================================

class TestVectorizationPipeline:
    """Tests for the complete vectorization pipeline"""
    
    @pytest.fixture
    def pipeline(self) -> VectorizationPipeline:
        """Create pipeline instance"""
        return VectorizationPipeline(
            tfidf_config={"max_features": 500},
            minhash_config={"num_perm": 64},
            lda_config={"n_topics": 3, "n_iterations": 20}
        )
    
    def test_initialization(self, pipeline: VectorizationPipeline):
        """Test pipeline initialization"""
        assert pipeline is not None
        assert pipeline.tfidf is not None
        assert pipeline.minhash is not None
        assert pipeline.lda is not None
    
    def test_fit(self, pipeline: VectorizationPipeline, sample_documents: List[str]):
        """Test fitting the pipeline"""
        pipeline.fit(sample_documents)
        
        assert pipeline.is_fitted
    
    def test_vectorize(self, pipeline: VectorizationPipeline, sample_documents: List[str]):
        """Test document vectorization through pipeline"""
        pipeline.fit(sample_documents)
        
        doc = "machine learning neural networks deep learning"
        result = pipeline.vectorize(doc)
        
        assert result is not None
        assert "tfidf" in result
        assert "minhash" in result
        assert "lda" in result
    
    def test_search(self, pipeline: VectorizationPipeline, document_objects: List[Document]):
        """Test searching through pipeline"""
        documents = [doc.content for doc in document_objects]
        pipeline.fit(documents)
        
        # Index documents
        for doc in document_objects:
            pipeline.index_document(doc.id, doc.content)
        
        # Search
        query = "machine learning"
        results = pipeline.search(query, top_k=5)
        
        assert results is not None
        assert len(results) <= 5
    
    def test_combined_similarity(self, pipeline: VectorizationPipeline, sample_documents: List[str]):
        """Test combined similarity scoring"""
        pipeline.fit(sample_documents)
        
        doc1 = "machine learning algorithms for data analysis"
        doc2 = "machine learning methods for predictions"
        doc3 = "cooking healthy meals at home"
        
        vec1 = pipeline.vectorize(doc1)
        vec2 = pipeline.vectorize(doc2)
        vec3 = pipeline.vectorize(doc3)
        
        sim_12 = pipeline.compute_similarity(vec1, vec2)
        sim_13 = pipeline.compute_similarity(vec1, vec3)
        
        # Similar documents should have higher similarity
        assert sim_12 > sim_13


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_corpus(self, tfidf_vectorizer: TFIDFVectorizer):
        """Test handling of empty corpus"""
        with pytest.raises(ValueError):
            tfidf_vectorizer.fit([])
    
    def test_single_document(self, tfidf_vectorizer: TFIDFVectorizer):
        """Test with single document"""
        docs = ["single document test"]
        tfidf_vectorizer.fit(docs)
        vectors = tfidf_vectorizer.transform(docs)
        
        assert len(vectors) == 1
    
    def test_very_long_document(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test handling of very long documents"""
        long_doc = " ".join(sample_documents * 100)  # Very long document
        
        tfidf_vectorizer.fit(sample_documents)
        vector = tfidf_vectorizer.transform_query(long_doc)
        
        assert vector is not None
    
    def test_special_characters(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test handling of special characters"""
        tfidf_vectorizer.fit(sample_documents)
        
        special_doc = "test @#$%^&*() special <<>> characters!!!"
        vector = tfidf_vectorizer.transform_query(special_doc)
        
        assert vector is not None
    
    def test_unicode_text(self, tfidf_vectorizer: TFIDFVectorizer, sample_documents: List[str]):
        """Test handling of unicode text"""
        tfidf_vectorizer.fit(sample_documents)
        
        unicode_doc = "测试 тест اختبار テスト machine learning"
        vector = tfidf_vectorizer.transform_query(unicode_doc)
        
        assert vector is not None
    
    def test_duplicate_documents(self, minhash_lsh: MinHashLSH):
        """Test handling of duplicate documents"""
        minhash_lsh.add_document("doc1", "test document")
        minhash_lsh.add_document("doc1", "updated test document")  # Same ID
        
        # Should update, not add duplicate
        assert minhash_lsh.get_document_count() == 1


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests"""
    
    @pytest.mark.slow
    def test_large_corpus(self, tfidf_vectorizer: TFIDFVectorizer):
        """Test with large corpus"""
        # Generate large corpus
        large_corpus = [
            f"Document {i} contains various words about topic {i % 10} with some unique content {i * 7}"
            for i in range(1000)
        ]
        
        tfidf_vectorizer.fit(large_corpus)
        vectors = tfidf_vectorizer.transform(large_corpus)
        
        assert len(vectors) == 1000
    
    @pytest.mark.slow
    def test_minhash_scalability(self, minhash_lsh: MinHashLSH):
        """Test MinHash with many documents"""
        for i in range(1000):
            minhash_lsh.add_document(
                f"doc_{i}",
                f"Document {i} about topic {i % 20} with content {i * 3}"
            )
        
        assert minhash_lsh.get_document_count() == 1000
        
        # Query should still be fast
        results = minhash_lsh.query("document about topic 5")
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
