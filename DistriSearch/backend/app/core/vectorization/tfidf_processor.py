"""
TF-IDF Processor

Implements TF-IDF (Term Frequency - Inverse Document Frequency) processing
for document and filename vectorization.
"""

import re
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix
import logging

logger = logging.getLogger(__name__)


class TFIDFProcessor:
    """
    TF-IDF processor for text vectorization.
    
    This processor handles both document content and filenames,
    with configurable parameters for each use case.
    """
    
    def __init__(
        self,
        max_features: int = 5000,
        min_df: int = 1,
        max_df: float = 0.95,
        ngram_range: Tuple[int, int] = (1, 2),
        use_idf: bool = True,
        smooth_idf: bool = True,
        sublinear_tf: bool = True,
        lowercase: bool = True
    ):
        """
        Initialize TF-IDF processor.
        
        Args:
            max_features: Maximum number of features (vocabulary size)
            min_df: Minimum document frequency for a term
            max_df: Maximum document frequency (as ratio)
            ngram_range: Range of n-grams to consider
            use_idf: Whether to use inverse document frequency
            smooth_idf: Smooth IDF weights
            sublinear_tf: Apply sublinear TF scaling (1 + log(tf))
            lowercase: Convert text to lowercase
        """
        self.max_features = max_features
        self.ngram_range = ngram_range
        
        self._vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=min_df,
            max_df=max_df,
            ngram_range=ngram_range,
            use_idf=use_idf,
            smooth_idf=smooth_idf,
            sublinear_tf=sublinear_tf,
            lowercase=lowercase,
            token_pattern=r'(?u)\b\w+\b',  # Include single-char tokens
            strip_accents='unicode'
        )
        
        self._is_fitted = False
        self._vocabulary: Dict[str, int] = {}
        self._idf_values: Optional[np.ndarray] = None
    
    def fit(self, documents: List[str]) -> 'TFIDFProcessor':
        """
        Fit the TF-IDF vectorizer on a corpus of documents.
        
        Args:
            documents: List of document texts
            
        Returns:
            Self for chaining
        """
        if not documents:
            logger.warning("Empty document list provided for fitting")
            return self
        
        # Filter out empty documents
        valid_docs = [doc for doc in documents if doc and doc.strip()]
        
        if not valid_docs:
            logger.warning("No valid documents for fitting")
            return self
        
        try:
            self._vectorizer.fit(valid_docs)
            self._vocabulary = self._vectorizer.vocabulary_
            self._idf_values = self._vectorizer.idf_
            self._is_fitted = True
            logger.info(f"TF-IDF fitted with vocabulary size: {len(self._vocabulary)}")
        except Exception as e:
            logger.error(f"Error fitting TF-IDF: {e}")
            raise
        
        return self
    
    def transform(self, documents: List[str]) -> csr_matrix:
        """
        Transform documents to TF-IDF vectors.
        
        Args:
            documents: List of document texts
            
        Returns:
            Sparse matrix of TF-IDF vectors
        """
        if not self._is_fitted:
            raise ValueError("TF-IDF processor must be fitted before transform")
        
        return self._vectorizer.transform(documents)
    
    def fit_transform(self, documents: List[str]) -> csr_matrix:
        """
        Fit and transform in one step.
        
        Args:
            documents: List of document texts
            
        Returns:
            Sparse matrix of TF-IDF vectors
        """
        self.fit(documents)
        return self.transform(documents)
    
    def get_tfidf_dict(self, text: str) -> Dict[str, float]:
        """
        Get TF-IDF weights as a dictionary for a single document.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary mapping terms to their TF-IDF weights
        """
        if not self._is_fitted:
            # For unfitted processor, compute simple TF weights
            return self._compute_simple_tf(text)
        
        # Transform the text
        vector = self._vectorizer.transform([text])
        
        # Get feature names
        feature_names = self._vectorizer.get_feature_names_out()
        
        # Extract non-zero values
        result = {}
        cx = vector.tocoo()
        for _, col, value in zip(cx.row, cx.col, cx.data):
            if value > 0:
                result[feature_names[col]] = float(value)
        
        return result
    
    def _compute_simple_tf(self, text: str) -> Dict[str, float]:
        """
        Compute simple term frequency for unfitted processor.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary of term frequencies
        """
        # Tokenize
        tokens = self._tokenize(text.lower())
        
        if not tokens:
            return {}
        
        # Count frequencies
        freq: Dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        
        # Normalize by max frequency
        max_freq = max(freq.values())
        return {term: count / max_freq for term, count in freq.items()}
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Simple word tokenization
        return re.findall(r'\b\w+\b', text.lower())
    
    def compute_cosine_similarity(
        self, 
        vec1: csr_matrix, 
        vec2: csr_matrix
    ) -> float:
        """
        Compute cosine similarity between two TF-IDF vectors.
        
        Args:
            vec1: First TF-IDF vector
            vec2: Second TF-IDF vector
            
        Returns:
            Cosine similarity (0-1)
        """
        # Ensure vectors are 1D
        if vec1.shape[0] > 1:
            vec1 = vec1[0]
        if vec2.shape[0] > 1:
            vec2 = vec2[0]
        
        # Compute dot product
        dot = vec1.dot(vec2.T).toarray()[0, 0]
        
        # Compute norms
        norm1 = np.sqrt(vec1.multiply(vec1).sum())
        norm2 = np.sqrt(vec2.multiply(vec2).sum())
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot / (norm1 * norm2))
    
    def compute_similarity_from_dicts(
        self,
        dict1: Dict[str, float],
        dict2: Dict[str, float]
    ) -> float:
        """
        Compute cosine similarity between two TF-IDF dictionaries.
        
        Args:
            dict1: First TF-IDF dictionary
            dict2: Second TF-IDF dictionary
            
        Returns:
            Cosine similarity (0-1)
        """
        if not dict1 or not dict2:
            return 0.0
        
        # Get all terms
        all_terms = set(dict1.keys()) | set(dict2.keys())
        
        # Compute dot product and norms
        dot_product = 0.0
        norm1_sq = 0.0
        norm2_sq = 0.0
        
        for term in all_terms:
            v1 = dict1.get(term, 0.0)
            v2 = dict2.get(term, 0.0)
            dot_product += v1 * v2
            norm1_sq += v1 * v1
            norm2_sq += v2 * v2
        
        if norm1_sq == 0 or norm2_sq == 0:
            return 0.0
        
        return dot_product / (np.sqrt(norm1_sq) * np.sqrt(norm2_sq))
    
    @property
    def vocabulary(self) -> Dict[str, int]:
        """Get the vocabulary mapping."""
        return self._vocabulary.copy()
    
    @property
    def vocabulary_size(self) -> int:
        """Get vocabulary size."""
        return len(self._vocabulary)
    
    @property
    def is_fitted(self) -> bool:
        """Check if processor is fitted."""
        return self._is_fitted
    
    def get_top_terms(self, text: str, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N terms by TF-IDF weight for a document.
        
        Args:
            text: Document text
            n: Number of top terms to return
            
        Returns:
            List of (term, weight) tuples sorted by weight descending
        """
        tfidf_dict = self.get_tfidf_dict(text)
        sorted_terms = sorted(
            tfidf_dict.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return sorted_terms[:n]


class FilenameTFIDFProcessor(TFIDFProcessor):
    """
    Specialized TF-IDF processor for filenames.
    
    Uses different preprocessing optimized for filenames:
    - Splits on common separators (_, -, .)
    - Handles camelCase
    - Preserves numbers and version patterns
    """
    
    def __init__(
        self,
        max_features: int = 1000,
        ngram_range: Tuple[int, int] = (1, 2)
    ):
        super().__init__(
            max_features=max_features,
            min_df=1,
            max_df=1.0,
            ngram_range=ngram_range,
            use_idf=True,
            smooth_idf=True,
            sublinear_tf=True,
            lowercase=True
        )
    
    def preprocess_filename(self, filename: str) -> str:
        """
        Preprocess filename for TF-IDF.
        
        Args:
            filename: Original filename
            
        Returns:
            Preprocessed text suitable for TF-IDF
        """
        # Remove extension
        if '.' in filename:
            name_part = filename.rsplit('.', 1)[0]
        else:
            name_part = filename
        
        # Split camelCase
        name_part = re.sub(r'([a-z])([A-Z])', r'\1 \2', name_part)
        
        # Replace separators with spaces
        name_part = re.sub(r'[_\-.]', ' ', name_part)
        
        # Normalize whitespace
        name_part = ' '.join(name_part.split())
        
        return name_part.lower()
    
    def get_filename_tfidf(self, filename: str) -> Dict[str, float]:
        """
        Get TF-IDF weights for a filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Dictionary of TF-IDF weights
        """
        preprocessed = self.preprocess_filename(filename)
        return self.get_tfidf_dict(preprocessed)
