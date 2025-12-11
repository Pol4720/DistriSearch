"""
Document Vectorizer

Main class for computing Adaptive Document Vectors using multiple
vectorization techniques: TF-IDF, MinHash, TextRank keywords, LDA topics,
and character n-grams.
"""

import hashlib
from typing import Dict, List, Optional, Set, Tuple
import logging

from shared.models.document import (
    DocumentVector,
    NameVector,
    ContentVector,
    StructuralFeatures
)
from app.core.vectorization.tfidf_processor import (
    TFIDFProcessor,
    FilenameTFIDFProcessor
)
from app.core.vectorization.minhash_signature import (
    MinHashSignature,
    ContentMinHasher
)
from app.core.vectorization.textrank_keywords import TextRankKeywordExtractor
from app.core.vectorization.lda_topics import LDATopicModeler
from app.core.vectorization.char_ngrams import (
    CharNGramProcessor,
    infer_category
)

logger = logging.getLogger(__name__)


class DocumentVectorizer:
    """
    Adaptive Document Vectorizer.
    
    Computes multi-level document vectors:
    - Level 1: Name vector (TF-IDF + char n-grams + inferred category)
    - Level 2: Content vector (MinHash signatures + TextRank keywords + LDA topics)
    - Level 3: Structural features (extension, size, patterns)
    
    This implementation does NOT use pre-trained embeddings, instead relying
    on corpus-specific models (LDA trained on local corpus, TF-IDF fitted
    on document collection).
    """
    
    def __init__(
        self,
        minhash_num_perm: int = 128,
        lda_num_topics: int = 20,
        tfidf_max_features: int = 5000,
        textrank_keywords: int = 10,
        name_weight: float = 0.4,
        content_weight: float = 0.4,
        topic_weight: float = 0.2
    ):
        """
        Initialize document vectorizer.
        
        Args:
            minhash_num_perm: Number of MinHash permutations
            lda_num_topics: Number of LDA topics
            tfidf_max_features: Max TF-IDF vocabulary size
            textrank_keywords: Number of keywords to extract
            name_weight: Weight for name similarity (0-1)
            content_weight: Weight for content similarity (0-1)
            topic_weight: Weight for topic similarity (0-1)
        """
        # Validate weights
        if abs(name_weight + content_weight + topic_weight - 1.0) > 0.01:
            logger.warning("Similarity weights don't sum to 1.0, normalizing")
            total = name_weight + content_weight + topic_weight
            name_weight /= total
            content_weight /= total
            topic_weight /= total
        
        self.name_weight = name_weight
        self.content_weight = content_weight
        self.topic_weight = topic_weight
        
        # Initialize processors
        self.filename_tfidf = FilenameTFIDFProcessor(max_features=1000)
        self.content_tfidf = TFIDFProcessor(max_features=tfidf_max_features)
        self.minhash = MinHashSignature(num_perm=minhash_num_perm)
        self.content_minhasher = ContentMinHasher(
            num_perm=minhash_num_perm,
            segment_size=1000
        )
        self.keyword_extractor = TextRankKeywordExtractor()
        self.lda = LDATopicModeler(num_topics=lda_num_topics)
        self.char_ngram = CharNGramProcessor()
        
        # State
        self._is_fitted = False
    
    def fit(self, documents: List[Dict[str, str]]) -> 'DocumentVectorizer':
        """
        Fit vectorizer on a corpus of documents.
        
        This trains the LDA model and fits TF-IDF vectorizers.
        
        Args:
            documents: List of dicts with 'filename' and 'content' keys
            
        Returns:
            Self for chaining
        """
        if not documents:
            logger.warning("Empty document list for fitting")
            return self
        
        # Extract filenames and contents
        filenames = [doc.get('filename', '') for doc in documents]
        contents = [doc.get('content', '') for doc in documents]
        
        # Filter valid entries
        valid_filenames = [f for f in filenames if f]
        valid_contents = [c for c in contents if c and len(c) > 50]
        
        # Fit filename TF-IDF
        if valid_filenames:
            preprocessed_filenames = [
                self.filename_tfidf.preprocess_filename(f) 
                for f in valid_filenames
            ]
            self.filename_tfidf.fit(preprocessed_filenames)
            logger.info(f"Fitted filename TF-IDF on {len(valid_filenames)} filenames")
        
        # Fit content TF-IDF
        if valid_contents:
            self.content_tfidf.fit(valid_contents)
            logger.info(f"Fitted content TF-IDF on {len(valid_contents)} documents")
        
        # Train LDA
        if len(valid_contents) >= 10:
            self.lda.train(valid_contents)
            logger.info(f"Trained LDA on {len(valid_contents)} documents")
        
        self._is_fitted = True
        return self
    
    def vectorize(
        self,
        filename: str,
        content: Optional[str] = None,
        file_size: int = 0,
        mime_type: str = ""
    ) -> DocumentVector:
        """
        Compute adaptive vector for a document.
        
        Args:
            filename: Document filename
            content: Document text content (optional for some file types)
            file_size: File size in bytes
            mime_type: MIME type of the document
            
        Returns:
            DocumentVector with all three levels
        """
        # Level 1: Name Vector
        name_vector = self._compute_name_vector(filename)
        
        # Level 2: Content Vector (if content available)
        if content and len(content) > 10:
            content_vector = self._compute_content_vector(content)
        else:
            content_vector = ContentVector()
        
        # Level 3: Structural Features
        structural = self._compute_structural_features(
            filename, file_size, mime_type, content
        )
        
        return DocumentVector(
            name_vector=name_vector,
            content_vector=content_vector,
            structural_features=structural,
            name_weight=self.name_weight,
            content_weight=self.content_weight,
            topic_weight=self.topic_weight
        )
    
    def _compute_name_vector(self, filename: str) -> NameVector:
        """
        Compute name vector (Level 1).
        
        Args:
            filename: Document filename
            
        Returns:
            NameVector with TF-IDF, n-grams, and category
        """
        # TF-IDF on filename
        tokens_tfidf = self.filename_tfidf.get_filename_tfidf(filename)
        
        # Character n-gram signature
        char_ngrams_signature = self.char_ngram.get_signature(filename)
        
        # Infer category
        category = infer_category(filename)
        
        return NameVector(
            tokens_tfidf=tokens_tfidf,
            char_ngrams_signature=char_ngrams_signature,
            category=category
        )
    
    def _compute_content_vector(self, content: str) -> ContentVector:
        """
        Compute content vector (Level 2).
        
        Args:
            content: Document text content
            
        Returns:
            ContentVector with MinHash, keywords, and topics
        """
        # MinHash signatures for content segments
        minhash_signatures = self.content_minhasher.compute_segmented_signatures(
            content
        )
        
        # TextRank keywords
        keywords = self.keyword_extractor.extract_keywords(content, top_n=10)
        
        # LDA topic distribution
        topic_distribution = self.lda.get_topic_distribution(content)
        
        return ContentVector(
            minhash_signatures=minhash_signatures,
            keywords_textrank=keywords,
            topic_distribution=topic_distribution
        )
    
    def _compute_structural_features(
        self,
        filename: str,
        file_size: int,
        mime_type: str,
        content: Optional[str]
    ) -> StructuralFeatures:
        """
        Compute structural features (Level 3).
        
        Args:
            filename: Document filename
            file_size: File size in bytes
            mime_type: MIME type
            content: Document content
            
        Returns:
            StructuralFeatures
        """
        # Extract extension
        extension = ""
        if '.' in filename:
            extension = filename.rsplit('.', 1)[1].lower()
        
        # Process filename for patterns
        features = self.char_ngram.process_filename(filename)
        
        # Count sections if content available
        section_count = 0
        has_tables = False
        
        if content:
            # Simple section detection (headers, numbered sections)
            import re
            section_markers = re.findall(
                r'^(?:#{1,6}|(?:\d+\.)+|\*{3,}|={3,})',
                content,
                re.MULTILINE
            )
            section_count = len(section_markers)
            
            # Simple table detection (pipe characters in lines)
            has_tables = bool(re.search(r'\|.*\|.*\|', content))
        
        return StructuralFeatures(
            extension=extension,
            name_length=len(filename),
            file_size=file_size,
            has_date_pattern=features.get('has_date_pattern', False),
            has_version=features.get('has_version', False),
            section_count=section_count,
            has_tables=has_tables
        )
    
    def compute_similarity(
        self,
        vec1: DocumentVector,
        vec2: DocumentVector
    ) -> float:
        """
        Compute weighted similarity between two document vectors.
        
        Similarity = w_name * name_sim + w_content * content_sim + w_topic * topic_sim
        
        Args:
            vec1: First document vector
            vec2: Second document vector
            
        Returns:
            Similarity score (0-1)
        """
        # Name similarity
        name_sim = self._compute_name_similarity(vec1.name_vector, vec2.name_vector)
        
        # Content similarity
        content_sim = self._compute_content_similarity(
            vec1.content_vector, vec2.content_vector
        )
        
        # Topic similarity
        topic_sim = self._compute_topic_similarity(
            vec1.content_vector, vec2.content_vector
        )
        
        # Weighted combination
        total = (
            self.name_weight * name_sim +
            self.content_weight * content_sim +
            self.topic_weight * topic_sim
        )
        
        return total
    
    def _compute_name_similarity(
        self,
        nv1: NameVector,
        nv2: NameVector
    ) -> float:
        """
        Compute similarity between name vectors.
        
        Combines TF-IDF cosine similarity with n-gram signature similarity.
        """
        # TF-IDF cosine similarity
        tfidf_sim = self.content_tfidf.compute_similarity_from_dicts(
            nv1.tokens_tfidf,
            nv2.tokens_tfidf
        )
        
        # Character n-gram signature similarity
        ngram_sim = self.char_ngram.estimate_similarity_from_signatures(
            nv1.char_ngrams_signature,
            nv2.char_ngrams_signature
        )
        
        # Category match bonus
        category_bonus = 0.0
        if nv1.category and nv2.category:
            if nv1.category.get('domain') == nv2.category.get('domain'):
                category_bonus += 0.1
            if nv1.category.get('type') == nv2.category.get('type'):
                category_bonus += 0.05
        
        # Combine (weighted average with category bonus)
        base_sim = 0.6 * tfidf_sim + 0.4 * ngram_sim
        
        return min(1.0, base_sim + category_bonus)
    
    def _compute_content_similarity(
        self,
        cv1: ContentVector,
        cv2: ContentVector
    ) -> float:
        """
        Compute similarity between content vectors.
        
        Uses MinHash Jaccard similarity on content segments.
        """
        if not cv1.minhash_signatures or not cv2.minhash_signatures:
            return 0.0
        
        # Use content minhasher for segmented comparison
        return self.content_minhasher.compute_combined_similarity(
            cv1.minhash_signatures,
            cv2.minhash_signatures
        )
    
    def _compute_topic_similarity(
        self,
        cv1: ContentVector,
        cv2: ContentVector
    ) -> float:
        """
        Compute topic similarity using Jensen-Shannon divergence.
        """
        if not cv1.topic_distribution or not cv2.topic_distribution:
            return 0.0
        
        return self.lda.compute_topic_similarity(
            cv1.topic_distribution,
            cv2.topic_distribution
        )
    
    def compute_content_hash(self, content: str) -> str:
        """
        Compute SHA-256 hash of content for deduplication.
        
        Args:
            content: Document content
            
        Returns:
            Hex digest of content hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_similarity_breakdown(
        self,
        vec1: DocumentVector,
        vec2: DocumentVector
    ) -> Dict[str, float]:
        """
        Get detailed breakdown of similarity scores.
        
        Args:
            vec1: First document vector
            vec2: Second document vector
            
        Returns:
            Dictionary with individual and total similarity scores
        """
        name_sim = self._compute_name_similarity(vec1.name_vector, vec2.name_vector)
        content_sim = self._compute_content_similarity(
            vec1.content_vector, vec2.content_vector
        )
        topic_sim = self._compute_topic_similarity(
            vec1.content_vector, vec2.content_vector
        )
        
        total = (
            self.name_weight * name_sim +
            self.content_weight * content_sim +
            self.topic_weight * topic_sim
        )
        
        return {
            'name_similarity': name_sim,
            'content_similarity': content_sim,
            'topic_similarity': topic_sim,
            'total_similarity': total,
            'weights': {
                'name': self.name_weight,
                'content': self.content_weight,
                'topic': self.topic_weight
            }
        }
    
    def save(self, path: str):
        """
        Save fitted vectorizer components.
        
        Args:
            path: Directory path to save to
        """
        import os
        os.makedirs(path, exist_ok=True)
        
        # Save LDA if trained
        if self.lda.is_trained:
            self.lda.save(os.path.join(path, 'lda'))
        
        logger.info(f"Vectorizer saved to {path}")
    
    def load(self, path: str) -> 'DocumentVectorizer':
        """
        Load fitted vectorizer components.
        
        Args:
            path: Directory path to load from
            
        Returns:
            Self for chaining
        """
        import os
        
        lda_path = os.path.join(path, 'lda')
        if os.path.exists(lda_path):
            self.lda.load(lda_path)
        
        self._is_fitted = True
        logger.info(f"Vectorizer loaded from {path}")
        
        return self
    
    @property
    def is_fitted(self) -> bool:
        """Check if vectorizer is fitted."""
        return self._is_fitted


# Convenience function for quick vectorization
def vectorize_document(
    filename: str,
    content: Optional[str] = None,
    file_size: int = 0
) -> DocumentVector:
    """
    Quick document vectorization without fitting.
    
    Args:
        filename: Document filename
        content: Document content
        file_size: File size in bytes
        
    Returns:
        DocumentVector
    """
    vectorizer = DocumentVectorizer()
    return vectorizer.vectorize(filename, content, file_size)
