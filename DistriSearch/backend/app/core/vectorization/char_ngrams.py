"""
Character N-Gram Processor

Processes filenames and short text using character n-grams.
Useful for capturing typos, abbreviations, and name variants.
"""

import re
from typing import Dict, List, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class CharNGramProcessor:
    """
    Character N-Gram Processor for filename similarity.
    
    Generates character-level n-grams that capture:
    - Partial matches and typos
    - Abbreviations and variants
    - Similar naming patterns
    """
    
    def __init__(
        self,
        ngram_sizes: List[int] = None,
        lowercase: bool = True,
        include_boundaries: bool = True
    ):
        """
        Initialize character n-gram processor.
        
        Args:
            ngram_sizes: List of n-gram sizes to generate (default: [2, 3, 4])
            lowercase: Convert text to lowercase
            include_boundaries: Add boundary markers (^ for start, $ for end)
        """
        self.ngram_sizes = ngram_sizes or [2, 3, 4]
        self.lowercase = lowercase
        self.include_boundaries = include_boundaries
    
    def get_ngrams(self, text: str) -> Set[str]:
        """
        Get all character n-grams from text.
        
        Args:
            text: Input text
            
        Returns:
            Set of character n-grams
        """
        if not text:
            return set()
        
        if self.lowercase:
            text = text.lower()
        
        # Add boundary markers
        if self.include_boundaries:
            text = f'^{text}$'
        
        ngrams = set()
        
        for n in self.ngram_sizes:
            if len(text) >= n:
                ngrams.update(
                    text[i:i+n] for i in range(len(text) - n + 1)
                )
        
        return ngrams
    
    def get_ngrams_weighted(self, text: str) -> Dict[str, float]:
        """
        Get character n-grams with position-based weights.
        
        N-grams at the start of the text get higher weights.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary mapping n-grams to weights
        """
        if not text:
            return {}
        
        if self.lowercase:
            text = text.lower()
        
        if self.include_boundaries:
            text = f'^{text}$'
        
        weights: Dict[str, float] = {}
        
        for n in self.ngram_sizes:
            if len(text) >= n:
                for i in range(len(text) - n + 1):
                    ngram = text[i:i+n]
                    # Weight decreases with position
                    position_weight = 1.0 / (1 + i * 0.1)
                    # Longer n-grams get higher weight
                    length_weight = n / max(self.ngram_sizes)
                    
                    weight = position_weight * length_weight
                    
                    # Keep maximum weight for duplicate n-grams
                    if ngram not in weights or weights[ngram] < weight:
                        weights[ngram] = weight
        
        return weights
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute similarity between two texts using n-gram overlap.
        
        Uses Jaccard similarity on character n-gram sets.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        ngrams1 = self.get_ngrams(text1)
        ngrams2 = self.get_ngrams(text2)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        
        return len(intersection) / len(union)
    
    def compute_weighted_similarity(self, text1: str, text2: str) -> float:
        """
        Compute weighted similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Weighted similarity score (0-1)
        """
        weights1 = self.get_ngrams_weighted(text1)
        weights2 = self.get_ngrams_weighted(text2)
        
        if not weights1 or not weights2:
            return 0.0
        
        # Compute weighted intersection
        common_ngrams = set(weights1.keys()) & set(weights2.keys())
        
        if not common_ngrams:
            return 0.0
        
        # Sum of minimum weights for common n-grams
        weighted_intersection = sum(
            min(weights1[ng], weights2[ng]) for ng in common_ngrams
        )
        
        # Sum of all weights
        total_weight = sum(weights1.values()) + sum(weights2.values())
        
        # Normalize
        return 2 * weighted_intersection / total_weight if total_weight > 0 else 0.0
    
    def process_filename(self, filename: str) -> Dict[str, any]:
        """
        Process a filename and extract features.
        
        Args:
            filename: Original filename
            
        Returns:
            Dictionary with extracted features
        """
        # Remove extension
        name_part = filename
        extension = ""
        
        if '.' in filename:
            parts = filename.rsplit('.', 1)
            name_part = parts[0]
            extension = parts[1].lower()
        
        # Split on common separators
        tokens = re.split(r'[_\-.\s]', name_part)
        tokens = [t for t in tokens if t]
        
        # Split camelCase
        expanded_tokens = []
        for token in tokens:
            parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', token).split()
            expanded_tokens.extend(parts)
        
        # Detect patterns
        has_date_pattern = bool(re.search(
            r'\d{4}[-_]?\d{2}[-_]?\d{2}|\d{2}[-_]\d{2}[-_]\d{4}',
            name_part
        ))
        
        has_version = bool(re.search(
            r'v?\d+(\.\d+)+|version[-_]?\d+',
            name_part.lower()
        ))
        
        has_numbers = bool(re.search(r'\d+', name_part))
        
        # Get n-grams
        ngrams = self.get_ngrams(name_part)
        ngrams_weighted = self.get_ngrams_weighted(name_part)
        
        return {
            'original': filename,
            'name_part': name_part,
            'extension': extension,
            'tokens': expanded_tokens,
            'ngrams': ngrams,
            'ngrams_weighted': ngrams_weighted,
            'has_date_pattern': has_date_pattern,
            'has_version': has_version,
            'has_numbers': has_numbers,
            'name_length': len(name_part)
        }
    
    def get_signature(self, text: str, signature_size: int = 128) -> List[int]:
        """
        Get a fixed-size signature from character n-grams.
        
        Uses simple hashing to create a compact representation.
        
        Args:
            text: Input text
            signature_size: Size of output signature
            
        Returns:
            List of hash values
        """
        ngrams = self.get_ngrams(text)
        
        if not ngrams:
            return [0] * signature_size
        
        # Use built-in hash for simplicity
        signature = [0] * signature_size
        
        for ngram in ngrams:
            h = hash(ngram)
            idx = h % signature_size
            signature[idx] = max(signature[idx], (h >> 8) % 256)
        
        return signature
    
    def estimate_similarity_from_signatures(
        self,
        sig1: List[int],
        sig2: List[int]
    ) -> float:
        """
        Estimate similarity from pre-computed signatures.
        
        Args:
            sig1: First signature
            sig2: Second signature
            
        Returns:
            Estimated similarity (0-1)
        """
        if len(sig1) != len(sig2) or not sig1:
            return 0.0
        
        # Count matching non-zero positions
        matches = 0
        non_zero = 0
        
        for v1, v2 in zip(sig1, sig2):
            if v1 > 0 or v2 > 0:
                non_zero += 1
                if v1 == v2:
                    matches += 1
        
        return matches / non_zero if non_zero > 0 else 0.0


def compute_filename_similarity(file1: str, file2: str) -> float:
    """
    Convenience function to compute filename similarity.
    
    Args:
        file1: First filename
        file2: Second filename
        
    Returns:
        Similarity score (0-1)
    """
    processor = CharNGramProcessor()
    return processor.compute_weighted_similarity(file1, file2)


def infer_category(filename: str) -> Dict[str, str]:
    """
    Infer category information from filename.
    
    Args:
        filename: Filename to analyze
        
    Returns:
        Dictionary with category information
    """
    processor = CharNGramProcessor()
    features = processor.process_filename(filename)
    
    extension = features['extension']
    name_lower = features['name_part'].lower()
    tokens = [t.lower() for t in features['tokens']]
    
    # Infer domain
    domain = 'general'
    domain_keywords = {
        'finance': ['invoice', 'report', 'sales', 'revenue', 'budget', 'financial', 'accounting', 'tax'],
        'legal': ['contract', 'agreement', 'legal', 'law', 'policy', 'terms', 'compliance'],
        'hr': ['employee', 'hr', 'resume', 'cv', 'hiring', 'personnel', 'payroll'],
        'marketing': ['marketing', 'campaign', 'brand', 'advertisement', 'promotion'],
        'technical': ['spec', 'documentation', 'manual', 'guide', 'api', 'design', 'architecture'],
        'project': ['project', 'plan', 'timeline', 'milestone', 'roadmap', 'sprint'],
    }
    
    for d, keywords in domain_keywords.items():
        if any(kw in name_lower for kw in keywords):
            domain = d
            break
    
    # Infer type
    doc_type = 'document'
    type_mapping = {
        'pdf': 'pdf',
        'doc': 'word',
        'docx': 'word',
        'xls': 'spreadsheet',
        'xlsx': 'spreadsheet',
        'csv': 'data',
        'ppt': 'presentation',
        'pptx': 'presentation',
        'txt': 'text',
        'md': 'markdown',
        'json': 'data',
        'xml': 'data',
    }
    doc_type = type_mapping.get(extension, 'document')
    
    # Infer temporal info
    temporal = None
    import re
    
    # Look for quarter patterns (Q1, Q2, etc.)
    quarter_match = re.search(r'q([1-4])[-_]?(\d{4}|\d{2})', name_lower)
    if quarter_match:
        q = quarter_match.group(1)
        year = quarter_match.group(2)
        if len(year) == 2:
            year = '20' + year
        temporal = f'Q{q}-{year}'
    
    # Look for year patterns
    elif features['has_date_pattern']:
        year_match = re.search(r'20\d{2}', name_lower)
        if year_match:
            temporal = year_match.group(0)
    
    return {
        'domain': domain,
        'type': doc_type,
        'temporal': temporal
    }
