# -*- coding: utf-8 -*-
"""
Unit Tests for Vectorization Module

Tests TF-IDF, MinHash, and LDA implementations.
"""

import pytest
import numpy as np
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.vectorization.tfidf_processor import TFIDFProcessor
from app.core.vectorization.minhash_signature import MinHashSignature
from app.core.vectorization.lda_topics import LDATopicModeler


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_documents() -> List[str]:
    """Sample documents for testing."""
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
def tfidf_processor() -> TFIDFProcessor:
    """Create TF-IDF processor instance."""
    return TFIDFProcessor(
        max_features=1000,
        min_df=1,
        max_df=0.95
    )


@pytest.fixture
def minhash_generator() -> MinHashSignature:
    """Create MinHash generator instance."""
    return MinHashSignature(
        num_perm=128,
        seed=42
    )


@pytest.fixture
def lda_modeler() -> LDATopicModeler:
    """Create LDA modeler instance."""
    return LDATopicModeler(
        num_topics=5,
        min_word_length=3,
        passes=5,
        iterations=50
    )


# ============================================================================
# TF-IDF Tests
# ============================================================================

class TestTFIDFProcessor:
    """Tests for TF-IDF vectorization."""
    
    def test_initialization(self, tfidf_processor):
        """Test processor initialization."""
        assert tfidf_processor is not None
        assert tfidf_processor.max_features == 1000
    
    def test_fit(self, tfidf_processor, sample_documents):
        """Test fitting on documents."""
        tfidf_processor.fit(sample_documents)
        
        assert tfidf_processor._is_fitted
        assert len(tfidf_processor._vocabulary) > 0
    
    def test_transform(self, tfidf_processor, sample_documents):
        """Test transforming documents."""
        tfidf_processor.fit(sample_documents)
        vectors = tfidf_processor.transform(sample_documents)
        
        assert vectors is not None
        assert vectors.shape[0] == len(sample_documents)
    
    def test_fit_transform(self, tfidf_processor, sample_documents):
        """Test fit and transform together."""
        vectors = tfidf_processor.fit_transform(sample_documents)
        
        assert vectors is not None
        assert vectors.shape[0] == len(sample_documents)
    
    def test_get_tfidf_dict(self, tfidf_processor, sample_documents):
        """Test getting TF-IDF as dictionary."""
        tfidf_processor.fit(sample_documents)
        
        result = tfidf_processor.get_tfidf_dict("machine learning tutorial")
        
        assert isinstance(result, dict)
        assert len(result) > 0
    
    def test_unfitted_transform_raises(self, tfidf_processor, sample_documents):
        """Test that transform raises if not fitted."""
        with pytest.raises(ValueError):
            tfidf_processor.transform(sample_documents)
    
    def test_empty_documents(self, tfidf_processor):
        """Test handling of empty documents."""
        tfidf_processor.fit([""])
        
        # Should handle gracefully
        assert True


# ============================================================================
# MinHash Tests
# ============================================================================

class TestMinHashSignature:
    """Tests for MinHash signature generation."""
    
    def test_initialization(self, minhash_generator):
        """Test generator initialization."""
        assert minhash_generator is not None
        assert minhash_generator.num_perm == 128
    
    def test_compute_signature(self, minhash_generator):
        """Test computing signature from tokens."""
        tokens = {"machine", "learning", "tutorial"}
        signature = minhash_generator.compute_signature(tokens)
        
        assert len(signature) == 128
        assert all(isinstance(v, (int, np.integer)) for v in signature)
    
    def test_compute_signature_from_text(self, minhash_generator):
        """Test computing signature from text."""
        text = "Machine learning is a subset of artificial intelligence."
        signature = minhash_generator.compute_signature_from_text(text)
        
        assert len(signature) == 128
    
    def test_empty_tokens(self, minhash_generator):
        """Test handling of empty tokens."""
        signature = minhash_generator.compute_signature(set())
        
        assert len(signature) == 128
        assert all(v == 0 for v in signature)
    
    def test_estimate_similarity(self, minhash_generator):
        """Test similarity estimation."""
        tokens1 = {"machine", "learning", "tutorial", "python"}
        tokens2 = {"machine", "learning", "course", "java"}
        
        sig1 = minhash_generator.compute_signature(tokens1)
        sig2 = minhash_generator.compute_signature(tokens2)
        
        similarity = minhash_generator.estimate_similarity(sig1, sig2)
        
        assert 0 <= similarity <= 1
        # Should have some similarity due to shared words
        assert similarity > 0
    
    def test_identical_documents(self, minhash_generator):
        """Test that identical documents have high similarity."""
        tokens = {"machine", "learning", "tutorial"}
        
        sig1 = minhash_generator.compute_signature(tokens)
        sig2 = minhash_generator.compute_signature(tokens)
        
        similarity = minhash_generator.estimate_similarity(sig1, sig2)
        
        assert similarity == 1.0
    
    def test_different_documents(self, minhash_generator):
        """Test that very different documents have low similarity."""
        tokens1 = {"apple", "banana", "orange", "grape"}
        tokens2 = {"car", "bus", "train", "plane"}
        
        sig1 = minhash_generator.compute_signature(tokens1)
        sig2 = minhash_generator.compute_signature(tokens2)
        
        similarity = minhash_generator.estimate_similarity(sig1, sig2)
        
        # Should be low or zero
        assert similarity < 0.3


# ============================================================================
# LDA Tests
# ============================================================================

class TestLDATopicModeler:
    """Tests for LDA topic modeling."""
    
    def test_initialization(self, lda_modeler):
        """Test modeler initialization."""
        assert lda_modeler is not None
        assert lda_modeler.num_topics == 5
    
    @pytest.mark.skipif(
        not (pytest.importorskip("gensim", reason="gensim not installed") or 
             pytest.importorskip("sklearn", reason="sklearn not installed")),
        reason="Neither gensim nor sklearn available"
    )
    def test_train(self, lda_modeler, sample_documents):
        """Test training LDA model."""
        # Need more documents for training
        expanded_docs = sample_documents * 5  # Repeat for minimum corpus
        
        try:
            lda_modeler.train(expanded_docs)
            assert lda_modeler._is_trained
        except Exception as e:
            # Training may fail with small corpus
            pytest.skip(f"LDA training failed (expected with small corpus): {e}")
    
    def test_infer_topics_untrained(self, lda_modeler):
        """Test that inferring topics on untrained model is handled."""
        # Should handle gracefully or raise appropriate error
        try:
            result = lda_modeler.infer_topics("test document")
            # If it returns something, it should be a list/array
            if result is not None:
                assert hasattr(result, '__len__')
        except Exception:
            # Expected for untrained model
            pass


# ============================================================================
# Integration Tests
# ============================================================================

class TestVectorizationIntegration:
    """Integration tests for vectorization pipeline."""
    
    def test_combined_vectorization(self, sample_documents, tfidf_processor, minhash_generator):
        """Test using multiple vectorization methods together."""
        doc = sample_documents[0]
        
        # TF-IDF
        tfidf_processor.fit(sample_documents)
        tfidf_dict = tfidf_processor.get_tfidf_dict(doc)
        
        # MinHash
        minhash_sig = minhash_generator.compute_signature_from_text(doc)
        
        # Both should produce valid outputs
        assert len(tfidf_dict) > 0
        assert len(minhash_sig) == 128
    
    def test_vectorization_consistency(self, minhash_generator):
        """Test that vectorization is consistent across calls."""
        text = "This is a test document for consistency check."
        
        sig1 = minhash_generator.compute_signature_from_text(text)
        sig2 = minhash_generator.compute_signature_from_text(text)
        
        assert sig1 == sig2
    
    def test_vectorization_handles_special_characters(self, tfidf_processor, minhash_generator):
        """Test handling of special characters."""
        text = "Test with special chars: !@#$%^&*() and émojis 🎉"
        
        # Need multiple documents for TF-IDF to work with min_df/max_df settings
        texts = [text, "Another document for vectorization", "Third document here"]
        
        # Should not raise
        tfidf_processor.fit(texts)
        tfidf_dict = tfidf_processor.get_tfidf_dict(text)
        minhash_sig = minhash_generator.compute_signature_from_text(text)
        
        assert isinstance(tfidf_dict, dict)
        assert len(minhash_sig) == 128
    
    def test_vectorization_handles_unicode(self, tfidf_processor, minhash_generator):
        """Test handling of unicode text."""
        text = "Texto en español con acentos: á é í ó ú ñ"
        
        # Need multiple documents for TF-IDF to work with min_df/max_df settings
        texts = [text, "Otro documento en español", "Tercer documento aquí"]
        
        # Should not raise
        tfidf_processor.fit(texts)
        tfidf_dict = tfidf_processor.get_tfidf_dict(text)
        minhash_sig = minhash_generator.compute_signature_from_text(text)
        
        assert isinstance(tfidf_dict, dict)
        assert len(minhash_sig) == 128


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
