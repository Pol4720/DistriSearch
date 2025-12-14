"""
Core Vectorization Package

Implements adaptive document vectorization using TF-IDF, MinHash,
TextRank keywords, and LDA topics - without pre-trained embeddings.
"""

from .document_vectorizer import DocumentVectorizer
from .tfidf_processor import TFIDFProcessor
from .minhash_signature import MinHashSignature
from .textrank_keywords import TextRankKeywordExtractor
from .lda_topics import LDATopicModeler
from .char_ngrams import CharNGramProcessor

__all__ = [
    'DocumentVectorizer',
    'TFIDFProcessor',
    'MinHashSignature',
    'TextRankKeywordExtractor',
    'LDATopicModeler',
    'CharNGramProcessor'
]
