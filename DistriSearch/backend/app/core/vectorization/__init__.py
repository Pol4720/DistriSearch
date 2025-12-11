"""
Core Vectorization Package

Implements adaptive document vectorization using TF-IDF, MinHash,
TextRank keywords, and LDA topics - without pre-trained embeddings.
"""

from app.core.vectorization.document_vectorizer import DocumentVectorizer
from app.core.vectorization.tfidf_processor import TFIDFProcessor
from app.core.vectorization.minhash_signature import MinHashSignature
from app.core.vectorization.textrank_keywords import TextRankKeywordExtractor
from app.core.vectorization.lda_topics import LDATopicModeler
from app.core.vectorization.char_ngrams import CharNGramProcessor

__all__ = [
    'DocumentVectorizer',
    'TFIDFProcessor',
    'MinHashSignature',
    'TextRankKeywordExtractor',
    'LDATopicModeler',
    'CharNGramProcessor'
]
