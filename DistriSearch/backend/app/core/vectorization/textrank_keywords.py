"""
TextRank Keyword Extractor

Implements TextRank algorithm for unsupervised keyword extraction
from documents. No pre-trained models required.
"""

import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
import logging

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import sent_tokenize, word_tokenize
except ImportError:
    nltk = None

logger = logging.getLogger(__name__)


class TextRankKeywordExtractor:
    """
    Extracts keywords from text using TextRank algorithm.
    
    TextRank builds a graph of words based on co-occurrence within
    a sliding window, then applies PageRank to find important words.
    """
    
    # English stopwords (fallback if NLTK not available)
    DEFAULT_STOPWORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they',
        'have', 'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'can', 'just', 'should', 'now', 'also', 'into', 'could', 'would',
        'there', 'their', 'been', 'being', 'having', 'doing', 'does', 'did',
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
        'your', 'yours', 'yourself', 'yourselves', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'them', 'theirs', 'themselves',
        'about', 'above', 'after', 'again', 'against', 'any', 'because',
        'before', 'below', 'between', 'during', 'further', 'here', 'once',
        'over', 'through', 'under', 'until', 'while', 'out', 'up', 'down',
    }
    
    def __init__(
        self,
        window_size: int = 4,
        min_word_length: int = 3,
        damping: float = 0.85,
        max_iterations: int = 100,
        convergence_threshold: float = 0.0001,
        language: str = 'english'
    ):
        """
        Initialize TextRank keyword extractor.
        
        Args:
            window_size: Co-occurrence window size
            min_word_length: Minimum word length to consider
            damping: PageRank damping factor
            max_iterations: Maximum PageRank iterations
            convergence_threshold: Convergence threshold for PageRank
            language: Language for stopwords
        """
        self.window_size = window_size
        self.min_word_length = min_word_length
        self.damping = damping
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        
        # Load stopwords
        self.stopwords = self._load_stopwords(language)
        
        if nx is None:
            logger.warning("NetworkX not available. Using simplified TextRank.")
    
    def _load_stopwords(self, language: str) -> Set[str]:
        """
        Load stopwords for the specified language.
        
        Args:
            language: Language name
            
        Returns:
            Set of stopwords
        """
        if nltk is not None:
            try:
                nltk.download('stopwords', quiet=True)
                return set(stopwords.words(language))
            except Exception as e:
                logger.debug(f"Could not load NLTK stopwords: {e}")
        
        return self.DEFAULT_STOPWORDS
    
    def extract_keywords(
        self,
        text: str,
        top_n: int = 10,
        include_scores: bool = False
    ) -> List[str]:
        """
        Extract keywords from text using TextRank.
        
        Args:
            text: Input text
            top_n: Number of keywords to extract
            include_scores: If True, return (keyword, score) tuples
            
        Returns:
            List of keywords (or keyword-score tuples)
        """
        # Preprocess and tokenize
        words = self._preprocess(text)
        
        if len(words) < 2:
            return list(words)[:top_n]
        
        # Build co-occurrence graph
        graph = self._build_graph(words)
        
        if not graph:
            return list(set(words))[:top_n]
        
        # Run PageRank (or simplified version)
        if nx is not None:
            scores = nx.pagerank(
                graph,
                alpha=self.damping,
                max_iter=self.max_iterations,
                tol=self.convergence_threshold
            )
        else:
            scores = self._simple_pagerank(graph)
        
        # Sort by score and get top N
        sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_keywords = sorted_words[:top_n]
        
        if include_scores:
            return [(word, score) for word, score in top_keywords]
        
        return [word for word, _ in top_keywords]
    
    def extract_keyphrases(
        self,
        text: str,
        top_n: int = 10,
        max_phrase_length: int = 3
    ) -> List[str]:
        """
        Extract keyphrases (multi-word keywords) from text.
        
        Args:
            text: Input text
            top_n: Number of keyphrases to extract
            max_phrase_length: Maximum words in a keyphrase
            
        Returns:
            List of keyphrases
        """
        # Get single keywords with scores
        keywords_with_scores = self.extract_keywords(
            text, 
            top_n=top_n * 2,
            include_scores=True
        )
        
        if not keywords_with_scores:
            return []
        
        keyword_set = {kw for kw, _ in keywords_with_scores}
        keyword_scores = {kw: score for kw, score in keywords_with_scores}
        
        # Tokenize original text to find consecutive keywords
        words = self._tokenize(text.lower())
        
        # Find consecutive keyword sequences
        phrases: Dict[str, float] = {}
        i = 0
        
        while i < len(words):
            if words[i] in keyword_set:
                # Start building phrase
                phrase_words = [words[i]]
                j = i + 1
                
                while (j < len(words) and 
                       j - i < max_phrase_length and
                       words[j] in keyword_set):
                    phrase_words.append(words[j])
                    j += 1
                
                # Score phrase as sum of word scores
                phrase = ' '.join(phrase_words)
                phrase_score = sum(
                    keyword_scores.get(w, 0) for w in phrase_words
                )
                
                # Bonus for longer phrases
                phrase_score *= (1 + 0.1 * (len(phrase_words) - 1))
                
                if phrase not in phrases or phrases[phrase] < phrase_score:
                    phrases[phrase] = phrase_score
                
                i = j
            else:
                i += 1
        
        # Sort and return top phrases
        sorted_phrases = sorted(
            phrases.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return [phrase for phrase, _ in sorted_phrases[:top_n]]
    
    def _preprocess(self, text: str) -> List[str]:
        """
        Preprocess text for keyword extraction.
        
        Args:
            text: Input text
            
        Returns:
            List of filtered tokens
        """
        # Tokenize
        words = self._tokenize(text.lower())
        
        # Filter
        filtered = [
            word for word in words
            if (len(word) >= self.min_word_length and
                word not in self.stopwords and
                word.isalpha())  # Only alphabetic words
        ]
        
        return filtered
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text
            
        Returns:
            List of word tokens
        """
        if nltk is not None:
            try:
                nltk.download('punkt', quiet=True)
                return word_tokenize(text)
            except Exception:
                pass
        
        # Fallback: simple regex tokenization
        return re.findall(r'\b\w+\b', text)
    
    def _build_graph(self, words: List[str]) -> Optional[object]:
        """
        Build co-occurrence graph from words.
        
        Args:
            words: List of preprocessed words
            
        Returns:
            NetworkX graph or dict representation
        """
        if nx is not None:
            graph = nx.Graph()
            
            # Add edges for words within window
            for i, word in enumerate(words):
                start = max(0, i - self.window_size)
                end = min(len(words), i + self.window_size + 1)
                
                for j in range(start, end):
                    if i != j:
                        other_word = words[j]
                        if graph.has_edge(word, other_word):
                            graph[word][other_word]['weight'] += 1
                        else:
                            graph.add_edge(word, other_word, weight=1)
            
            return graph
        else:
            # Return dict-based graph representation
            graph: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
            
            for i, word in enumerate(words):
                start = max(0, i - self.window_size)
                end = min(len(words), i + self.window_size + 1)
                
                for j in range(start, end):
                    if i != j:
                        graph[word][words[j]] += 1
            
            return dict(graph)
    
    def _simple_pagerank(
        self, 
        graph: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Simplified PageRank implementation without NetworkX.
        
        Args:
            graph: Dictionary-based graph
            
        Returns:
            Dictionary of word scores
        """
        nodes = set(graph.keys())
        for neighbors in graph.values():
            nodes.update(neighbors.keys())
        
        nodes = list(nodes)
        n = len(nodes)
        
        if n == 0:
            return {}
        
        # Initialize scores
        scores = {node: 1.0 / n for node in nodes}
        
        # Iterate
        for _ in range(self.max_iterations):
            new_scores = {}
            max_diff = 0.0
            
            for node in nodes:
                # Sum contributions from incoming edges
                incoming_sum = 0.0
                
                for other_node in nodes:
                    if node in graph.get(other_node, {}):
                        # Get total outgoing weight from other_node
                        total_weight = sum(graph[other_node].values())
                        if total_weight > 0:
                            weight = graph[other_node][node]
                            incoming_sum += scores[other_node] * weight / total_weight
                
                new_score = (1 - self.damping) / n + self.damping * incoming_sum
                new_scores[node] = new_score
                
                max_diff = max(max_diff, abs(new_score - scores[node]))
            
            scores = new_scores
            
            # Check convergence
            if max_diff < self.convergence_threshold:
                break
        
        return scores


def extract_keywords_simple(text: str, top_n: int = 10) -> List[str]:
    """
    Simple keyword extraction function using TextRank.
    
    Args:
        text: Input text
        top_n: Number of keywords to extract
        
    Returns:
        List of keywords
    """
    extractor = TextRankKeywordExtractor()
    return extractor.extract_keywords(text, top_n=top_n)
