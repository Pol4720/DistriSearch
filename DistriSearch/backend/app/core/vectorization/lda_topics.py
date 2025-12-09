"""
LDA Topic Modeler

Implements Latent Dirichlet Allocation (LDA) for topic modeling.
Trained locally on the cluster corpus - no pre-trained models.
"""

import re
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np

try:
    from gensim import corpora
    from gensim.models import LdaModel, LdaMulticore
    GENSIM_AVAILABLE = True
except ImportError:
    GENSIM_AVAILABLE = False

try:
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class LDATopicModeler:
    """
    LDA Topic Modeler for extracting topic distributions from documents.
    
    This implementation trains LDA on the local corpus, allowing the
    topic model to adapt to the specific document collection in the cluster.
    """
    
    # Default stopwords (subset)
    DEFAULT_STOPWORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'were', 'will', 'with', 'this', 'but', 'they', 'have',
        'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how',
    }
    
    def __init__(
        self,
        num_topics: int = 20,
        min_word_length: int = 3,
        min_df: int = 5,
        max_df: float = 0.5,
        passes: int = 10,
        iterations: int = 50,
        random_state: int = 42,
        use_multicore: bool = True
    ):
        """
        Initialize LDA Topic Modeler.
        
        Args:
            num_topics: Number of topics to extract
            min_word_length: Minimum word length
            min_df: Minimum document frequency for words
            max_df: Maximum document frequency (as ratio)
            passes: Number of passes through corpus (gensim)
            iterations: Number of iterations (sklearn)
            random_state: Random seed
            use_multicore: Use multicore LDA if available
        """
        self.num_topics = num_topics
        self.min_word_length = min_word_length
        self.min_df = min_df
        self.max_df = max_df
        self.passes = passes
        self.iterations = iterations
        self.random_state = random_state
        self.use_multicore = use_multicore
        
        # Model components (set after training)
        self._model = None
        self._dictionary = None  # For gensim
        self._vectorizer = None  # For sklearn
        self._is_trained = False
        
        # Use gensim if available, else sklearn
        self._use_gensim = GENSIM_AVAILABLE
        
        if not GENSIM_AVAILABLE and not SKLEARN_AVAILABLE:
            logger.warning("Neither gensim nor sklearn available for LDA")
    
    def train(self, documents: List[str]) -> 'LDATopicModeler':
        """
        Train LDA model on a corpus of documents.
        
        Args:
            documents: List of document texts
            
        Returns:
            Self for chaining
        """
        if not documents:
            logger.warning("Empty document list for LDA training")
            return self
        
        # Preprocess documents
        processed_docs = [self._preprocess(doc) for doc in documents]
        processed_docs = [doc for doc in processed_docs if doc]  # Filter empty
        
        if len(processed_docs) < self.num_topics:
            logger.warning(
                f"Too few documents ({len(processed_docs)}) for "
                f"{self.num_topics} topics. Reducing topics."
            )
            self.num_topics = max(2, len(processed_docs) // 2)
        
        if self._use_gensim:
            self._train_gensim(processed_docs)
        elif SKLEARN_AVAILABLE:
            self._train_sklearn(processed_docs)
        else:
            logger.error("No LDA implementation available")
            return self
        
        self._is_trained = True
        logger.info(f"LDA model trained with {self.num_topics} topics")
        
        return self
    
    def _train_gensim(self, processed_docs: List[List[str]]):
        """Train using gensim."""
        # Create dictionary and corpus
        self._dictionary = corpora.Dictionary(processed_docs)
        
        # Filter extremes
        self._dictionary.filter_extremes(
            no_below=self.min_df,
            no_above=self.max_df
        )
        
        corpus = [self._dictionary.doc2bow(doc) for doc in processed_docs]
        
        # Train LDA
        if self.use_multicore:
            try:
                self._model = LdaMulticore(
                    corpus=corpus,
                    id2word=self._dictionary,
                    num_topics=self.num_topics,
                    passes=self.passes,
                    random_state=self.random_state,
                    workers=2
                )
            except Exception as e:
                logger.warning(f"Multicore LDA failed, using single core: {e}")
                self._model = LdaModel(
                    corpus=corpus,
                    id2word=self._dictionary,
                    num_topics=self.num_topics,
                    passes=self.passes,
                    random_state=self.random_state
                )
        else:
            self._model = LdaModel(
                corpus=corpus,
                id2word=self._dictionary,
                num_topics=self.num_topics,
                passes=self.passes,
                random_state=self.random_state
            )
    
    def _train_sklearn(self, processed_docs: List[List[str]]):
        """Train using sklearn."""
        # Join tokens back to strings for CountVectorizer
        texts = [' '.join(doc) for doc in processed_docs]
        
        # Create vectorizer
        self._vectorizer = CountVectorizer(
            min_df=self.min_df,
            max_df=self.max_df,
            stop_words='english'
        )
        
        # Fit transform
        doc_term_matrix = self._vectorizer.fit_transform(texts)
        
        # Train LDA
        self._model = LatentDirichletAllocation(
            n_components=self.num_topics,
            max_iter=self.iterations,
            random_state=self.random_state,
            learning_method='batch'
        )
        self._model.fit(doc_term_matrix)
    
    def get_topic_distribution(self, text: str) -> List[float]:
        """
        Get topic distribution for a document.
        
        Args:
            text: Document text
            
        Returns:
            List of topic probabilities (length = num_topics)
        """
        if not self._is_trained:
            return [1.0 / self.num_topics] * self.num_topics
        
        processed = self._preprocess(text)
        
        if not processed:
            return [1.0 / self.num_topics] * self.num_topics
        
        if self._use_gensim:
            return self._get_distribution_gensim(processed)
        else:
            return self._get_distribution_sklearn(processed)
    
    def _get_distribution_gensim(self, tokens: List[str]) -> List[float]:
        """Get topic distribution using gensim."""
        bow = self._dictionary.doc2bow(tokens)
        
        if not bow:
            return [1.0 / self.num_topics] * self.num_topics
        
        topic_dist = self._model.get_document_topics(
            bow, 
            minimum_probability=0.0
        )
        
        # Convert to fixed-length list
        distribution = [0.0] * self.num_topics
        for topic_id, prob in topic_dist:
            if topic_id < self.num_topics:
                distribution[topic_id] = prob
        
        return distribution
    
    def _get_distribution_sklearn(self, tokens: List[str]) -> List[float]:
        """Get topic distribution using sklearn."""
        text = ' '.join(tokens)
        doc_term_matrix = self._vectorizer.transform([text])
        
        distribution = self._model.transform(doc_term_matrix)[0]
        
        return distribution.tolist()
    
    def get_top_words(
        self, 
        topic_id: int, 
        n_words: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Get top words for a topic.
        
        Args:
            topic_id: Topic index
            n_words: Number of words to return
            
        Returns:
            List of (word, weight) tuples
        """
        if not self._is_trained or topic_id >= self.num_topics:
            return []
        
        if self._use_gensim:
            return self._model.show_topic(topic_id, n_words)
        else:
            feature_names = self._vectorizer.get_feature_names_out()
            topic = self._model.components_[topic_id]
            top_indices = topic.argsort()[:-n_words-1:-1]
            
            return [
                (feature_names[i], topic[i])
                for i in top_indices
            ]
    
    def get_all_topics(
        self, 
        n_words: int = 10
    ) -> Dict[int, List[Tuple[str, float]]]:
        """
        Get top words for all topics.
        
        Args:
            n_words: Number of words per topic
            
        Returns:
            Dictionary mapping topic_id to list of (word, weight) tuples
        """
        return {
            i: self.get_top_words(i, n_words)
            for i in range(self.num_topics)
        }
    
    def compute_topic_similarity(
        self,
        dist1: List[float],
        dist2: List[float]
    ) -> float:
        """
        Compute similarity between two topic distributions.
        Uses Jensen-Shannon divergence (converted to similarity).
        
        Args:
            dist1: First topic distribution
            dist2: Second topic distribution
            
        Returns:
            Similarity score (0-1)
        """
        if not dist1 or not dist2:
            return 0.0
        
        # Normalize distributions
        arr1 = np.array(dist1)
        arr2 = np.array(dist2)
        
        arr1 = arr1 / arr1.sum() if arr1.sum() > 0 else arr1
        arr2 = arr2 / arr2.sum() if arr2.sum() > 0 else arr2
        
        # Jensen-Shannon divergence
        m = 0.5 * (arr1 + arr2)
        
        # Avoid log(0) by adding small epsilon
        eps = 1e-10
        arr1 = np.clip(arr1, eps, 1)
        arr2 = np.clip(arr2, eps, 1)
        m = np.clip(m, eps, 1)
        
        kl1 = np.sum(arr1 * np.log(arr1 / m))
        kl2 = np.sum(arr2 * np.log(arr2 / m))
        
        js_divergence = 0.5 * (kl1 + kl2)
        
        # Convert divergence to similarity (0-1)
        # JS divergence is bounded [0, ln(2)]
        similarity = 1.0 - (js_divergence / np.log(2))
        
        return max(0.0, min(1.0, similarity))
    
    def _preprocess(self, text: str) -> List[str]:
        """
        Preprocess text for LDA.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Lowercase
        text = text.lower()
        
        # Tokenize (simple word extraction)
        tokens = re.findall(r'\b[a-z]+\b', text)
        
        # Filter
        filtered = [
            token for token in tokens
            if (len(token) >= self.min_word_length and
                token not in self.DEFAULT_STOPWORDS)
        ]
        
        return filtered
    
    def save(self, path: str):
        """
        Save trained model to disk.
        
        Args:
            path: Directory path to save model
        """
        if not self._is_trained:
            raise ValueError("Model must be trained before saving")
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            'num_topics': self.num_topics,
            'use_gensim': self._use_gensim,
            'is_trained': self._is_trained
        }
        
        with open(path / 'metadata.pkl', 'wb') as f:
            pickle.dump(metadata, f)
        
        if self._use_gensim:
            self._model.save(str(path / 'lda_model'))
            self._dictionary.save(str(path / 'dictionary'))
        else:
            with open(path / 'lda_model.pkl', 'wb') as f:
                pickle.dump(self._model, f)
            with open(path / 'vectorizer.pkl', 'wb') as f:
                pickle.dump(self._vectorizer, f)
        
        logger.info(f"LDA model saved to {path}")
    
    def load(self, path: str) -> 'LDATopicModeler':
        """
        Load trained model from disk.
        
        Args:
            path: Directory path with saved model
            
        Returns:
            Self for chaining
        """
        path = Path(path)
        
        # Load metadata
        with open(path / 'metadata.pkl', 'rb') as f:
            metadata = pickle.load(f)
        
        self.num_topics = metadata['num_topics']
        self._use_gensim = metadata['use_gensim']
        self._is_trained = metadata['is_trained']
        
        if self._use_gensim:
            self._model = LdaModel.load(str(path / 'lda_model'))
            self._dictionary = corpora.Dictionary.load(str(path / 'dictionary'))
        else:
            with open(path / 'lda_model.pkl', 'rb') as f:
                self._model = pickle.load(f)
            with open(path / 'vectorizer.pkl', 'rb') as f:
                self._vectorizer = pickle.load(f)
        
        logger.info(f"LDA model loaded from {path}")
        
        return self
    
    @property
    def is_trained(self) -> bool:
        """Check if model is trained."""
        return self._is_trained
