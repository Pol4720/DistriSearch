# -*- coding: utf-8 -*-
"""
Distance Metrics - Unified distance calculation for document vectors.

Implements the weighted distance formula from architecture:
d(A,B) = 0.4 * cos_name + 0.4 * jaccard_content + 0.2 * jsd_topics
"""

import numpy as np
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of distance metrics supported."""
    COSINE = "cosine"
    JACCARD = "jaccard"
    JENSEN_SHANNON = "jensen_shannon"
    EUCLIDEAN = "euclidean"
    WEIGHTED_COMBINED = "weighted_combined"


@dataclass
class DistanceWeights:
    """Weights for combined distance calculation."""
    name_weight: float = 0.4
    content_weight: float = 0.4
    topic_weight: float = 0.2
    
    def __post_init__(self):
        total = self.name_weight + self.content_weight + self.topic_weight
        if not np.isclose(total, 1.0):
            # Normalize weights
            self.name_weight /= total
            self.content_weight /= total
            self.topic_weight /= total


class DistanceCalculator:
    """
    Calculates distances between document vectors using various metrics.
    
    Primary metric is weighted combination per architecture spec:
    d(A,B) = 0.4 * cosine_distance(name) + 0.4 * jaccard_distance(content) + 0.2 * jsd(topics)
    """
    
    def __init__(self, weights: Optional[DistanceWeights] = None):
        """
        Initialize distance calculator.
        
        Args:
            weights: Custom weights for combined distance
        """
        self.weights = weights or DistanceWeights()
        self._epsilon = 1e-10
    
    def cosine_similarity(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray
    ) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec_a: First vector
            vec_b: Second vector
            
        Returns:
            Similarity score in [0, 1]
        """
        if vec_a is None or vec_b is None:
            return 0.0
        
        vec_a = np.asarray(vec_a, dtype=np.float64)
        vec_b = np.asarray(vec_b, dtype=np.float64)
        
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        
        if norm_a < self._epsilon or norm_b < self._epsilon:
            return 0.0
        
        dot_product = np.dot(vec_a, vec_b)
        similarity = dot_product / (norm_a * norm_b)
        
        # Clamp to valid range due to floating point errors
        return float(np.clip(similarity, -1.0, 1.0))
    
    def cosine_distance(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray
    ) -> float:
        """
        Calculate cosine distance between two vectors.
        
        Args:
            vec_a: First vector
            vec_b: Second vector
            
        Returns:
            Distance score in [0, 1]
        """
        similarity = self.cosine_similarity(vec_a, vec_b)
        return (1.0 - similarity) / 2.0  # Normalize to [0, 1]
    
    def jaccard_similarity(
        self,
        signature_a: np.ndarray,
        signature_b: np.ndarray
    ) -> float:
        """
        Estimate Jaccard similarity using MinHash signatures.
        
        Args:
            signature_a: MinHash signature of first document
            signature_b: MinHash signature of second document
            
        Returns:
            Estimated Jaccard similarity in [0, 1]
        """
        if signature_a is None or signature_b is None:
            return 0.0
        
        sig_a = np.asarray(signature_a)
        sig_b = np.asarray(signature_b)
        
        if len(sig_a) != len(sig_b):
            logger.warning(
                f"MinHash signature length mismatch: {len(sig_a)} vs {len(sig_b)}"
            )
            min_len = min(len(sig_a), len(sig_b))
            sig_a = sig_a[:min_len]
            sig_b = sig_b[:min_len]
        
        if len(sig_a) == 0:
            return 0.0
        
        # Jaccard estimate = proportion of matching hash values
        matches = np.sum(sig_a == sig_b)
        return float(matches / len(sig_a))
    
    def jaccard_distance(
        self,
        signature_a: np.ndarray,
        signature_b: np.ndarray
    ) -> float:
        """
        Calculate Jaccard distance using MinHash signatures.
        
        Args:
            signature_a: MinHash signature of first document
            signature_b: MinHash signature of second document
            
        Returns:
            Distance score in [0, 1]
        """
        return 1.0 - self.jaccard_similarity(signature_a, signature_b)
    
    def jensen_shannon_divergence(
        self,
        dist_a: np.ndarray,
        dist_b: np.ndarray
    ) -> float:
        """
        Calculate Jensen-Shannon Divergence between two probability distributions.
        
        JSD is a symmetric measure derived from KL divergence.
        JSD(P||Q) = 0.5 * KL(P||M) + 0.5 * KL(Q||M) where M = 0.5 * (P + Q)
        
        Args:
            dist_a: First probability distribution (topic distribution)
            dist_b: Second probability distribution (topic distribution)
            
        Returns:
            JSD value in [0, 1] (using base-2 log for normalization)
        """
        if dist_a is None or dist_b is None:
            return 1.0  # Maximum distance if no topic distribution
        
        p = np.asarray(dist_a, dtype=np.float64)
        q = np.asarray(dist_b, dtype=np.float64)
        
        # Ensure same length
        if len(p) != len(q):
            # Pad shorter distribution with zeros
            max_len = max(len(p), len(q))
            p = np.pad(p, (0, max_len - len(p)), 'constant')
            q = np.pad(q, (0, max_len - len(q)), 'constant')
        
        # Normalize to ensure valid probability distributions
        p_sum = np.sum(p)
        q_sum = np.sum(q)
        
        if p_sum < self._epsilon or q_sum < self._epsilon:
            return 1.0
        
        p = p / p_sum
        q = q / q_sum
        
        # Add small epsilon to avoid log(0)
        p = p + self._epsilon
        q = q + self._epsilon
        
        # Renormalize
        p = p / np.sum(p)
        q = q / np.sum(q)
        
        # Calculate midpoint distribution
        m = 0.5 * (p + q)
        
        # KL divergences
        kl_pm = np.sum(p * np.log2(p / m))
        kl_qm = np.sum(q * np.log2(q / m))
        
        # JSD
        jsd = 0.5 * kl_pm + 0.5 * kl_qm
        
        # JSD is bounded by [0, 1] when using log base 2
        return float(np.clip(jsd, 0.0, 1.0))
    
    def euclidean_distance(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray,
        normalize: bool = True
    ) -> float:
        """
        Calculate Euclidean distance between two vectors.
        
        Args:
            vec_a: First vector
            vec_b: Second vector
            normalize: Whether to normalize to [0, 1] range
            
        Returns:
            Euclidean distance (optionally normalized)
        """
        if vec_a is None or vec_b is None:
            return 1.0 if normalize else float('inf')
        
        vec_a = np.asarray(vec_a, dtype=np.float64)
        vec_b = np.asarray(vec_b, dtype=np.float64)
        
        distance = np.linalg.norm(vec_a - vec_b)
        
        if normalize:
            # Normalize by maximum possible distance
            max_dist = np.sqrt(len(vec_a)) * 2  # Assuming normalized vectors
            distance = distance / max_dist if max_dist > 0 else 0.0
            distance = min(distance, 1.0)
        
        return float(distance)
    
    def weighted_distance(
        self,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any]
    ) -> float:
        """
        Calculate weighted combined distance between two documents.
        
        Uses formula: d(A,B) = w1*cos(name) + w2*jaccard(content) + w3*jsd(topics)
        
        Args:
            doc_a: First document with vectors dict containing:
                   - name_vector: TF-IDF vector of document name
                   - minhash_signature: MinHash of content
                   - topic_distribution: LDA topic distribution
            doc_b: Second document with same structure
            
        Returns:
            Combined weighted distance in [0, 1]
        """
        # Extract vectors
        name_a = doc_a.get("name_vector")
        name_b = doc_b.get("name_vector")
        
        minhash_a = doc_a.get("minhash_signature")
        minhash_b = doc_b.get("minhash_signature")
        
        topic_a = doc_a.get("topic_distribution")
        topic_b = doc_b.get("topic_distribution")
        
        # Calculate component distances
        name_dist = self.cosine_distance(name_a, name_b)
        content_dist = self.jaccard_distance(minhash_a, minhash_b)
        topic_dist = self.jensen_shannon_divergence(topic_a, topic_b)
        
        # Weighted combination
        combined = (
            self.weights.name_weight * name_dist +
            self.weights.content_weight * content_dist +
            self.weights.topic_weight * topic_dist
        )
        
        return float(np.clip(combined, 0.0, 1.0))
    
    def compute(
        self,
        vec_a: Any,
        vec_b: Any,
        metric: MetricType = MetricType.WEIGHTED_COMBINED
    ) -> float:
        """
        Generic distance computation with specified metric.
        
        Args:
            vec_a: First vector/document
            vec_b: Second vector/document
            metric: Type of metric to use
            
        Returns:
            Distance value
        """
        if metric == MetricType.COSINE:
            return self.cosine_distance(vec_a, vec_b)
        elif metric == MetricType.JACCARD:
            return self.jaccard_distance(vec_a, vec_b)
        elif metric == MetricType.JENSEN_SHANNON:
            return self.jensen_shannon_divergence(vec_a, vec_b)
        elif metric == MetricType.EUCLIDEAN:
            return self.euclidean_distance(vec_a, vec_b)
        elif metric == MetricType.WEIGHTED_COMBINED:
            return self.weighted_distance(vec_a, vec_b)
        else:
            raise ValueError(f"Unknown metric type: {metric}")
    
    def batch_distances(
        self,
        query: Dict[str, Any],
        documents: list,
        metric: MetricType = MetricType.WEIGHTED_COMBINED
    ) -> np.ndarray:
        """
        Calculate distances from query to multiple documents.
        
        Args:
            query: Query document/vector
            documents: List of documents to compare against
            metric: Distance metric to use
            
        Returns:
            Array of distances
        """
        distances = np.zeros(len(documents))
        
        for i, doc in enumerate(documents):
            distances[i] = self.compute(query, doc, metric)
        
        return distances
