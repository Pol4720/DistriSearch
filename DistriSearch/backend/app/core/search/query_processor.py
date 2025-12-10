# -*- coding: utf-8 -*-
"""
Query Processor - Processes and vectorizes search queries.

Transforms user queries into vector representations for
similarity search using the same vectorization as documents.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of search queries."""
    KEYWORD = "keyword"          # Simple keyword search
    PHRASE = "phrase"            # Exact phrase match
    SEMANTIC = "semantic"        # Semantic/vector search
    FUZZY = "fuzzy"             # Fuzzy matching
    FILENAME = "filename"        # Search by filename
    COMBINED = "combined"        # Multiple types


@dataclass
class ProcessedQuery:
    """Represents a processed search query."""
    original_query: str
    query_type: QueryType
    tokens: List[str] = field(default_factory=list)
    normalized_query: str = ""
    keywords: List[str] = field(default_factory=list)
    phrases: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    
    # Vector representations
    name_vector: Optional[Any] = None
    content_vector: Optional[Any] = None
    minhash_signature: Optional[Any] = None
    topic_distribution: Optional[Any] = None
    
    # Metadata
    processed_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    
    def to_document_format(self) -> Dict[str, Any]:
        """Convert to format compatible with document vectors."""
        return {
            "name_vector": self.name_vector,
            "content_vector": self.content_vector,
            "minhash_signature": self.minhash_signature,
            "topic_distribution": self.topic_distribution,
        }


class QueryProcessor:
    """
    Processes search queries for distributed search.
    
    Features:
    - Query parsing and normalization
    - Keyword extraction
    - Query vectorization (using same method as documents)
    - Filter extraction (file type, date, etc.)
    """
    
    def __init__(
        self,
        vectorizer: Optional[Any] = None,
        stopwords: Optional[Set[str]] = None,
        min_token_length: int = 2,
        max_query_tokens: int = 100
    ):
        """
        Initialize query processor.
        
        Args:
            vectorizer: DocumentVectorizer instance for query vectorization
            stopwords: Set of stopwords to filter
            min_token_length: Minimum token length
            max_query_tokens: Maximum tokens to process
        """
        self._vectorizer = vectorizer
        self._stopwords = stopwords or self._default_stopwords()
        self.min_token_length = min_token_length
        self.max_query_tokens = max_query_tokens
        
        # Filter patterns
        self._filter_patterns = {
            "type": re.compile(r'type:(\w+)', re.IGNORECASE),
            "ext": re.compile(r'ext:(\w+)', re.IGNORECASE),
            "date": re.compile(r'date:(\d{4}-\d{2}-\d{2})', re.IGNORECASE),
            "size": re.compile(r'size:([<>]?\d+[kmg]?b?)', re.IGNORECASE),
            "author": re.compile(r'author:(\w+)', re.IGNORECASE),
        }
        
        # Phrase pattern (quoted strings)
        self._phrase_pattern = re.compile(r'"([^"]+)"')
    
    def _default_stopwords(self) -> Set[str]:
        """Get default English stopwords."""
        return {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "this", "that", "these", "those", "it", "its", "they", "them",
        }
    
    def set_vectorizer(self, vectorizer: Any) -> None:
        """Set the document vectorizer."""
        self._vectorizer = vectorizer
    
    def process(
        self,
        query: str,
        query_type: Optional[QueryType] = None,
        include_vectors: bool = True
    ) -> ProcessedQuery:
        """
        Process a search query.
        
        Args:
            query: Raw query string
            query_type: Type of query (auto-detected if None)
            include_vectors: Whether to generate vectors
            
        Returns:
            Processed query
        """
        start_time = datetime.utcnow()
        
        # Determine query type
        if query_type is None:
            query_type = self._detect_query_type(query)
        
        # Extract filters
        filters, clean_query = self._extract_filters(query)
        
        # Extract phrases
        phrases, remaining = self._extract_phrases(clean_query)
        
        # Normalize and tokenize
        normalized = self._normalize(remaining)
        tokens = self._tokenize(normalized)
        
        # Extract keywords (non-stopword tokens)
        keywords = [t for t in tokens if t not in self._stopwords]
        
        processed = ProcessedQuery(
            original_query=query,
            query_type=query_type,
            tokens=tokens[:self.max_query_tokens],
            normalized_query=normalized,
            keywords=keywords,
            phrases=phrases,
            filters=filters
        )
        
        # Generate vectors if requested
        if include_vectors and self._vectorizer:
            self._vectorize_query(processed)
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processed.processing_time_ms = (end_time - start_time).total_seconds() * 1000
        
        return processed
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Auto-detect query type from query string."""
        # Check for phrases
        if '"' in query:
            return QueryType.PHRASE
        
        # Check for filename pattern
        if re.search(r'\.\w{2,4}$', query.split()[-1] if query.split() else ""):
            return QueryType.FILENAME
        
        # Check for fuzzy indicator
        if '~' in query:
            return QueryType.FUZZY
        
        # Check for filters
        if any(p.search(query) for p in self._filter_patterns.values()):
            return QueryType.COMBINED
        
        # Default to semantic for longer queries
        if len(query.split()) > 3:
            return QueryType.SEMANTIC
        
        return QueryType.KEYWORD
    
    def _extract_filters(self, query: str) -> tuple:
        """
        Extract filter expressions from query.
        
        Args:
            query: Query string
            
        Returns:
            Tuple of (filters dict, remaining query)
        """
        filters = {}
        remaining = query
        
        for filter_name, pattern in self._filter_patterns.items():
            match = pattern.search(remaining)
            if match:
                filters[filter_name] = match.group(1)
                remaining = pattern.sub('', remaining)
        
        return filters, remaining.strip()
    
    def _extract_phrases(self, query: str) -> tuple:
        """
        Extract quoted phrases from query.
        
        Args:
            query: Query string
            
        Returns:
            Tuple of (phrases list, remaining query)
        """
        phrases = self._phrase_pattern.findall(query)
        remaining = self._phrase_pattern.sub('', query)
        
        return phrases, remaining.strip()
    
    def _normalize(self, text: str) -> str:
        """Normalize query text."""
        # Lowercase
        text = text.lower()
        
        # Remove special characters except alphanumeric and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize normalized text."""
        tokens = text.split()
        
        # Filter by length
        tokens = [t for t in tokens if len(t) >= self.min_token_length]
        
        return tokens
    
    def _vectorize_query(self, processed: ProcessedQuery) -> None:
        """
        Generate vector representations for query.
        
        Args:
            processed: Processed query to vectorize
        """
        if not self._vectorizer:
            return
        
        try:
            # Create pseudo-document from query
            query_text = processed.normalized_query
            if processed.phrases:
                query_text = f"{query_text} {' '.join(processed.phrases)}"
            
            # Use vectorizer to generate representations
            # Note: This assumes vectorizer has methods for individual components
            if hasattr(self._vectorizer, 'tfidf_processor'):
                processed.name_vector = self._vectorizer.tfidf_processor.transform(
                    query_text
                )
            
            if hasattr(self._vectorizer, 'minhash_generator'):
                processed.minhash_signature = self._vectorizer.minhash_generator.compute(
                    query_text
                )
            
            if hasattr(self._vectorizer, 'lda_processor'):
                processed.topic_distribution = self._vectorizer.lda_processor.get_topics(
                    query_text
                )
            
        except Exception as e:
            logger.warning(f"Query vectorization failed: {e}")
    
    def expand_query(
        self,
        processed: ProcessedQuery,
        synonyms: Optional[Dict[str, List[str]]] = None
    ) -> ProcessedQuery:
        """
        Expand query with synonyms.
        
        Args:
            processed: Processed query
            synonyms: Synonym dictionary
            
        Returns:
            Expanded query
        """
        if not synonyms:
            return processed
        
        expanded_keywords = list(processed.keywords)
        
        for keyword in processed.keywords:
            if keyword in synonyms:
                expanded_keywords.extend(synonyms[keyword])
        
        # Deduplicate
        processed.keywords = list(dict.fromkeys(expanded_keywords))
        
        return processed
    
    def get_search_targets(
        self,
        processed: ProcessedQuery
    ) -> Dict[str, Any]:
        """
        Get targets for the search based on query type.
        
        Args:
            processed: Processed query
            
        Returns:
            Search targets configuration
        """
        targets = {
            "use_vector_search": False,
            "use_keyword_search": False,
            "use_phrase_search": False,
            "search_filename": False,
            "search_content": True,
        }
        
        if processed.query_type == QueryType.SEMANTIC:
            targets["use_vector_search"] = True
            
        elif processed.query_type == QueryType.KEYWORD:
            targets["use_keyword_search"] = True
            
        elif processed.query_type == QueryType.PHRASE:
            targets["use_phrase_search"] = True
            
        elif processed.query_type == QueryType.FILENAME:
            targets["search_filename"] = True
            targets["search_content"] = False
            
        elif processed.query_type == QueryType.COMBINED:
            targets["use_vector_search"] = True
            targets["use_keyword_search"] = True
            if processed.phrases:
                targets["use_phrase_search"] = True
        
        return targets
