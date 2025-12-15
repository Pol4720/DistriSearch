"""
MinHash Signature Generator

Implements MinHash for estimating Jaccard similarity between documents.
Uses datasketch library for efficient MinHash computation.
"""

from typing import List, Optional, Set, Tuple
import hashlib
import logging
from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)


class MinHashSignature:
    """
    MinHash signature generator for document similarity estimation.
    
    MinHash allows efficient estimation of Jaccard similarity between sets
    without computing the actual intersection and union.
    """
    
    def __init__(
        self,
        num_perm: int = 128,
        seed: int = 42
    ):
        """
        Initialize MinHash signature generator.
        
        Args:
            num_perm: Number of permutations (signature size)
            seed: Random seed for reproducibility
        """
        self.num_perm = num_perm
        self.seed = seed
    
    def compute_signature(self, tokens: Set[str]) -> List[int]:
        """
        Compute MinHash signature for a set of tokens.
        
        Args:
            tokens: Set of string tokens
            
        Returns:
            List of MinHash values (signature)
        """
        if not tokens:
            return [0] * self.num_perm
        
        minhash = MinHash(num_perm=self.num_perm, seed=self.seed)
        
        for token in tokens:
            minhash.update(token.encode('utf-8'))
        
        return list(minhash.hashvalues)
    
    def compute_signature_from_text(
        self, 
        text: str, 
        tokenize: bool = True,
        ngram_size: int = 3
    ) -> List[int]:
        """
        Compute MinHash signature from text.
        
        Args:
            text: Input text
            tokenize: If True, use word tokens; if False, use character n-grams
            ngram_size: Size of character n-grams (if tokenize=False)
            
        Returns:
            MinHash signature
        """
        if tokenize:
            # Word-based tokens
            tokens = self._tokenize_words(text)
        else:
            # Character n-gram tokens
            tokens = self._get_char_ngrams(text, ngram_size)
        
        return self.compute_signature(tokens)
    
    def estimate_similarity(
        self, 
        sig1: List[int], 
        sig2: List[int]
    ) -> float:
        """
        Estimate Jaccard similarity from two MinHash signatures.
        
        Args:
            sig1: First MinHash signature
            sig2: Second MinHash signature
            
        Returns:
            Estimated Jaccard similarity (0-1)
        """
        if len(sig1) != len(sig2):
            raise ValueError("Signatures must have same length")
        
        if not sig1 or not sig2:
            return 0.0
        
        # Count matching hash values
        matches = sum(1 for h1, h2 in zip(sig1, sig2) if h1 == h2)
        
        return matches / len(sig1)
    
    def estimate_similarity_from_minhash(
        self,
        mh1: MinHash,
        mh2: MinHash
    ) -> float:
        """
        Estimate similarity from MinHash objects.
        
        Args:
            mh1: First MinHash object
            mh2: Second MinHash object
            
        Returns:
            Estimated Jaccard similarity
        """
        return mh1.jaccard(mh2)
    
    def create_minhash(self, tokens: Set[str]) -> MinHash:
        """
        Create a MinHash object from tokens.
        
        Args:
            tokens: Set of tokens
            
        Returns:
            MinHash object
        """
        minhash = MinHash(num_perm=self.num_perm, seed=self.seed)
        
        for token in tokens:
            minhash.update(token.encode('utf-8'))
        
        return minhash
    
    def _tokenize_words(self, text: str) -> Set[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text
            
        Returns:
            Set of word tokens
        """
        import re
        # Simple word tokenization, lowercase
        words = re.findall(r'\b\w+\b', text.lower())
        return set(words)
    
    def _get_char_ngrams(self, text: str, n: int = 3) -> Set[str]:
        """
        Get character n-grams from text.
        
        Args:
            text: Input text
            n: N-gram size
            
        Returns:
            Set of character n-grams
        """
        text = text.lower().strip()
        if len(text) < n:
            return {text} if text else set()
        
        return {text[i:i+n] for i in range(len(text) - n + 1)}


class MinHashLSHIndex:
    """
    MinHash LSH (Locality-Sensitive Hashing) Index for approximate nearest neighbors.
    
    This allows efficient querying of similar documents without
    comparing against all documents in the index.
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        num_perm: int = 128,
        seed: int = 42
    ):
        """
        Initialize MinHash LSH index.
        
        Args:
            threshold: Jaccard similarity threshold for matching
            num_perm: Number of permutations
            seed: Random seed
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.seed = seed
        
        self._lsh = MinHashLSH(
            threshold=threshold,
            num_perm=num_perm
        )
        self._minhashes: dict = {}
        self._signature_gen = MinHashSignature(num_perm=num_perm, seed=seed)
    
    def add(self, doc_id: str, tokens: Set[str]):
        """
        Add a document to the index.
        
        Args:
            doc_id: Unique document identifier
            tokens: Set of tokens representing the document
        """
        minhash = self._signature_gen.create_minhash(tokens)
        
        try:
            self._lsh.insert(doc_id, minhash)
            self._minhashes[doc_id] = minhash
        except ValueError as e:
            # Document already exists
            logger.debug(f"Document {doc_id} already in index: {e}")
    
    def query(self, tokens: Set[str]) -> List[str]:
        """
        Query for similar documents.
        
        Args:
            tokens: Set of tokens to query with
            
        Returns:
            List of similar document IDs
        """
        minhash = self._signature_gen.create_minhash(tokens)
        return list(self._lsh.query(minhash))
    
    def query_with_scores(
        self, 
        tokens: Set[str], 
        top_k: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Query for similar documents with similarity scores.
        
        Args:
            tokens: Set of tokens to query with
            top_k: Maximum number of results
            
        Returns:
            List of (doc_id, similarity) tuples sorted by similarity
        """
        query_minhash = self._signature_gen.create_minhash(tokens)
        candidates = self._lsh.query(query_minhash)
        
        # Compute exact similarities for candidates
        results = []
        for doc_id in candidates:
            doc_minhash = self._minhashes.get(doc_id)
            if doc_minhash:
                similarity = query_minhash.jaccard(doc_minhash)
                results.append((doc_id, similarity))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            results = results[:top_k]
        
        return results
    
    def remove(self, doc_id: str):
        """
        Remove a document from the index.
        
        Args:
            doc_id: Document ID to remove
        """
        if doc_id in self._minhashes:
            try:
                self._lsh.remove(doc_id)
            except KeyError:
                pass
            del self._minhashes[doc_id]
    
    def get_similarity(self, doc_id1: str, doc_id2: str) -> float:
        """
        Get similarity between two indexed documents.
        
        Args:
            doc_id1: First document ID
            doc_id2: Second document ID
            
        Returns:
            Jaccard similarity estimate
        """
        mh1 = self._minhashes.get(doc_id1)
        mh2 = self._minhashes.get(doc_id2)
        
        if not mh1 or not mh2:
            return 0.0
        
        return mh1.jaccard(mh2)
    
    def __len__(self) -> int:
        """Return number of documents in index."""
        return len(self._minhashes)
    
    def __contains__(self, doc_id: str) -> bool:
        """Check if document is in index."""
        return doc_id in self._minhashes


class ContentMinHasher:
    """
    Content-aware MinHash generator that segments documents
    for more accurate similarity estimation on long documents.
    """
    
    def __init__(
        self,
        num_perm: int = 128,
        segment_size: int = 1000,
        seed: int = 42
    ):
        """
        Initialize content MinHasher.
        
        Args:
            num_perm: Number of permutations per segment
            segment_size: Approximate number of words per segment
            seed: Random seed
        """
        self.num_perm = num_perm
        self.segment_size = segment_size
        self.seed = seed
        self._hasher = MinHashSignature(num_perm=num_perm, seed=seed)
    
    def compute_segmented_signatures(
        self, 
        text: str
    ) -> List[List[int]]:
        """
        Compute MinHash signatures for document segments.
        
        Args:
            text: Document text
            
        Returns:
            List of MinHash signatures (one per segment)
        """
        # Tokenize
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        
        if not words:
            return []
        
        # Segment document
        signatures = []
        for i in range(0, len(words), self.segment_size):
            segment_words = set(words[i:i + self.segment_size])
            sig = self._hasher.compute_signature(segment_words)
            signatures.append(sig)
        
        return signatures
    
    def compute_combined_similarity(
        self,
        sigs1: List[List[int]],
        sigs2: List[List[int]]
    ) -> float:
        """
        Compute similarity between two documents using segmented signatures.
        
        Uses maximum similarity across segments for better handling
        of documents where only parts are similar.
        
        Args:
            sigs1: Signatures of first document
            sigs2: Signatures of second document
            
        Returns:
            Maximum segment-wise similarity
        """
        if not sigs1 or not sigs2:
            return 0.0
        
        max_sim = 0.0
        
        for sig1 in sigs1:
            for sig2 in sigs2:
                sim = self._hasher.estimate_similarity(sig1, sig2)
                max_sim = max(max_sim, sim)
        
        return max_sim
    
    def compute_average_similarity(
        self,
        sigs1: List[List[int]],
        sigs2: List[List[int]]
    ) -> float:
        """
        Compute average similarity between document segments.
        
        Args:
            sigs1: Signatures of first document
            sigs2: Signatures of second document
            
        Returns:
            Average similarity
        """
        if not sigs1 or not sigs2:
            return 0.0
        
        total_sim = 0.0
        count = 0
        
        for sig1 in sigs1:
            for sig2 in sigs2:
                sim = self._hasher.estimate_similarity(sig1, sig2)
                total_sim += sim
                count += 1
        
        return total_sim / count if count > 0 else 0.0
