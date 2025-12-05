"""
DistriSearch Master - Servicio de Embeddings

Genera embeddings semánticos usando sentence-transformers.
Usado tanto para indexar documentos como para queries.
"""
import numpy as np
from typing import List, Optional, Union
import logging

logger = logging.getLogger(__name__)

# Modelo por defecto: pequeño, rápido, 384 dimensiones
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """
    Servicio de generación de embeddings semánticos.
    
    Usa sentence-transformers para generar vectores
    que capturan el significado semántico del texto.
    """
    
    _instance: Optional['EmbeddingService'] = None
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Args:
            model_name: Nombre del modelo de sentence-transformers
        """
        self.model_name = model_name
        self._model = None
        self._embedding_dim: Optional[int] = None
        
    @classmethod
    def get_instance(cls, model_name: str = DEFAULT_MODEL) -> 'EmbeddingService':
        """Obtiene instancia singleton del servicio"""
        if cls._instance is None or cls._instance.model_name != model_name:
            cls._instance = cls(model_name)
        return cls._instance
    
    def _load_model(self) -> None:
        """Carga el modelo de embeddings (lazy loading)"""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Cargando modelo de embeddings: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            
            # Obtener dimensión
            test_embedding = self._model.encode("test", convert_to_numpy=True)
            self._embedding_dim = test_embedding.shape[0]
            
            logger.info(f"Modelo cargado. Dimensión: {self._embedding_dim}")
            
        except ImportError:
            logger.error("sentence-transformers no está instalado")
            raise ImportError(
                "sentence-transformers es requerido. "
                "Instalar con: pip install sentence-transformers"
            )
    
    @property
    def embedding_dim(self) -> int:
        """Retorna la dimensión de los embeddings"""
        if self._embedding_dim is None:
            self._load_model()
        return self._embedding_dim
    
    def encode(
        self, 
        text: Union[str, List[str]], 
        normalize: bool = True
    ) -> np.ndarray:
        """
        Genera embedding(s) para texto(s).
        
        Args:
            text: Texto o lista de textos a codificar
            normalize: Si normalizar los vectores (para similitud coseno)
            
        Returns:
            Array numpy con el/los embedding(s)
        """
        self._load_model()
        
        embeddings = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=normalize
        )
        
        return embeddings
    
    def encode_document(
        self, 
        filename: str, 
        content: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> np.ndarray:
        """
        Genera embedding para un documento.
        
        Combina nombre de archivo, contenido y metadatos
        para crear una representación semántica rica.
        
        Args:
            filename: Nombre del archivo
            content: Contenido textual (opcional)
            metadata: Metadatos del documento (opcional)
            
        Returns:
            Embedding del documento
        """
        parts = [filename]
        
        if content:
            # Tomar primeras líneas del contenido
            preview = content[:1000] if len(content) > 1000 else content
            parts.append(preview)
        
        if metadata:
            # Añadir metadatos relevantes
            for key in ['description', 'tags', 'keywords']:
                if key in metadata:
                    value = metadata[key]
                    if isinstance(value, list):
                        parts.append(' '.join(value))
                    else:
                        parts.append(str(value))
        
        combined_text = ' '.join(parts)
        return self.encode(combined_text)
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Genera embedding para una consulta de búsqueda.
        
        Args:
            query: Texto de la consulta
            
        Returns:
            Embedding de la consulta
        """
        return self.encode(query)
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula similitud coseno entre dos embeddings.
        
        Args:
            embedding1: Primer embedding
            embedding2: Segundo embedding
            
        Returns:
            Score de similitud [0, 1]
        """
        # Asegurar normalización
        e1 = embedding1 / (np.linalg.norm(embedding1) + 1e-10)
        e2 = embedding2 / (np.linalg.norm(embedding2) + 1e-10)
        
        return float(np.dot(e1, e2))
    
    def batch_similarity(
        self, 
        query_embedding: np.ndarray, 
        embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Calcula similitud de una query contra múltiples embeddings.
        
        Args:
            query_embedding: Embedding de la consulta
            embeddings: Matriz de embeddings (N x dim)
            
        Returns:
            Array de scores de similitud
        """
        query = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        
        # Normalizar matriz
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-10)
        
        return np.dot(normalized, query)


# Función de conveniencia para acceso rápido
def get_embedding_service(model_name: str = DEFAULT_MODEL) -> EmbeddingService:
    """Obtiene instancia del servicio de embeddings"""
    return EmbeddingService.get_instance(model_name)
