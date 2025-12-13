"""
Core Vectorization Package

Implements adaptive document vectorization using TF-IDF, MinHash,
TextRank keywords, and LDA topics - without pre-trained embeddings.
"""

from .core.vectorization.document_vectorizer import DocumentVectorizer
from .core.vectorization.tfidf_processor import TFIDFProcessor
from .core.vectorization.minhash_signature import MinHashSignature
from .core.vectorization.textrank_keywords import TextRankKeywordExtractor
from .core.vectorization.lda_topics import LDATopicModeler
from .core.vectorization.char_ngrams import CharNGramProcessor

__all__ = [
    'DocumentVectorizer',
    'TFIDFProcessor',
    'MinHashSignature',
    'TextRankKeywordExtractor',
    'LDATopicModeler',
    'CharNGramProcessor'
]
