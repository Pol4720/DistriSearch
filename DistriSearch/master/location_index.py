"""
DistriSearch Master - Índice de ubicación semántica

Mantiene un índice semántico de los documentos de cada Slave.
Permite ubicar recursos por similitud semántica en lugar de hash.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentLocation:
    """Ubicación de un documento en el cluster"""
    file_id: str
    filename: str
    node_id: str
    embedding: np.ndarray
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "node_id": self.node_id,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class SemanticLocationIndex:
    """
    Índice de ubicación semántica para el cluster.
    
    Mantiene embeddings de todos los documentos indexados
    y perfiles agregados de cada Slave para routing eficiente.
    
    Funcionalidades:
    - Registrar ubicación de documentos con su embedding
    - Buscar documentos por similitud semántica
    - Mantener perfiles agregados de cada Slave
    - Seleccionar nodos para replicación por afinidad semántica
    """
    
    def __init__(self, embedding_dim: int = 384):
        """
        Args:
            embedding_dim: Dimensión de los embeddings (384 para all-MiniLM-L6-v2)
        """
        self.embedding_dim = embedding_dim
        
        # Índice de documentos: file_id -> DocumentLocation
        self._documents: Dict[str, DocumentLocation] = {}
        
        # Perfiles de Slaves: node_id -> embedding agregado
        self._slave_profiles: Dict[str, Dict] = {}
        
        # Matriz de embeddings para búsqueda rápida
        self._embedding_matrix: Optional[np.ndarray] = None
        self._file_ids: List[str] = []
        
        self._needs_rebuild = False
        
    def register_document(
        self, 
        file_id: str, 
        filename: str,
        node_id: str,
        embedding: np.ndarray,
        metadata: Dict = None
    ) -> None:
        """
        Registra la ubicación de un documento en el índice.
        
        Args:
            file_id: ID único del documento
            filename: Nombre del archivo
            node_id: ID del Slave donde está almacenado
            embedding: Vector de embedding del documento
            metadata: Metadatos adicionales
        """
        if embedding.shape[0] != self.embedding_dim:
            raise ValueError(f"Embedding dimension mismatch: expected {self.embedding_dim}, got {embedding.shape[0]}")
        
        # Normalizar embedding para similitud coseno
        embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
        
        doc = DocumentLocation(
            file_id=file_id,
            filename=filename,
            node_id=node_id,
            embedding=embedding,
            metadata=metadata or {}
        )
        
        self._documents[file_id] = doc
        self._needs_rebuild = True
        
        # Actualizar perfil del Slave
        self._update_slave_profile(node_id)
        
        logger.info(f"Documento registrado: {filename} en {node_id}")
    
    def remove_document(self, file_id: str) -> bool:
        """Elimina un documento del índice"""
        if file_id not in self._documents:
            return False
        
        doc = self._documents.pop(file_id)
        self._needs_rebuild = True
        self._update_slave_profile(doc.node_id)
        
        return True
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 10,
        node_filter: Optional[List[str]] = None
    ) -> List[Tuple[DocumentLocation, float]]:
        """
        Busca documentos por similitud semántica.
        
        Args:
            query_embedding: Embedding de la consulta
            top_k: Número máximo de resultados
            node_filter: Lista de nodos a incluir (None = todos)
            
        Returns:
            Lista de (documento, score) ordenada por similitud
        """
        if not self._documents:
            return []
        
        # Reconstruir matriz si es necesario
        if self._needs_rebuild:
            self._rebuild_index()
        
        # Normalizar query
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        
        # Calcular similitudes
        similarities = np.dot(self._embedding_matrix, query_embedding)
        
        # Filtrar por nodo si es necesario
        if node_filter:
            mask = np.array([
                self._documents[fid].node_id in node_filter 
                for fid in self._file_ids
            ])
            similarities = np.where(mask, similarities, -np.inf)
        
        # Top-k
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] == -np.inf:
                continue
            file_id = self._file_ids[idx]
            doc = self._documents[file_id]
            results.append((doc, float(similarities[idx])))
        
        return results
    
    def find_nodes_for_query(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Encuentra los nodos más relevantes para una consulta.
        
        Útil para routing de queries: envía la búsqueda solo
        a los Slaves con mayor afinidad semántica.
        
        Returns:
            Lista de (node_id, score) ordenada por relevancia
        """
        if not self._slave_profiles:
            return []
        
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        
        node_scores = []
        for node_id, profile in self._slave_profiles.items():
            if profile["embedding"] is not None:
                similarity = np.dot(profile["embedding"], query_embedding)
                node_scores.append((node_id, float(similarity)))
        
        node_scores.sort(key=lambda x: x[1], reverse=True)
        return node_scores[:top_k]
    
    def select_replica_nodes(
        self, 
        source_node: str,
        document_embedding: np.ndarray,
        replication_factor: int = 2
    ) -> List[str]:
        """
        Selecciona nodos para replicación por afinidad semántica.
        
        Elige los Slaves con contenido más similar al documento,
        excluyendo el nodo origen.
        
        Returns:
            Lista de node_ids seleccionados para replicación
        """
        if not self._slave_profiles or replication_factor < 1:
            return []
        
        # Encontrar nodos similares
        relevant_nodes = self.find_nodes_for_query(
            document_embedding, 
            top_k=replication_factor + 1
        )
        
        # Excluir nodo origen
        replica_nodes = [
            node_id for node_id, _ in relevant_nodes 
            if node_id != source_node
        ]
        
        return replica_nodes[:replication_factor]
    
    def get_document_location(self, file_id: str) -> Optional[DocumentLocation]:
        """Obtiene la ubicación de un documento específico"""
        return self._documents.get(file_id)
    
    def get_slave_profile(self, node_id: str) -> Optional[Dict]:
        """Obtiene el perfil de un Slave"""
        return self._slave_profiles.get(node_id)
    
    def get_all_documents_in_node(self, node_id: str) -> List[DocumentLocation]:
        """Obtiene todos los documentos de un nodo"""
        return [
            doc for doc in self._documents.values() 
            if doc.node_id == node_id
        ]
    
    def _rebuild_index(self) -> None:
        """Reconstruye la matriz de embeddings para búsqueda eficiente"""
        if not self._documents:
            self._embedding_matrix = None
            self._file_ids = []
            return
        
        self._file_ids = list(self._documents.keys())
        embeddings = [self._documents[fid].embedding for fid in self._file_ids]
        self._embedding_matrix = np.vstack(embeddings)
        self._needs_rebuild = False
        
        logger.debug(f"Índice reconstruido: {len(self._file_ids)} documentos")
    
    def _update_slave_profile(self, node_id: str) -> None:
        """
        Actualiza el perfil agregado de un Slave.
        
        El perfil es el centroide de todos sus documentos,
        usado para routing de queries.
        """
        docs = self.get_all_documents_in_node(node_id)
        
        if not docs:
            self._slave_profiles.pop(node_id, None)
            return
        
        # Calcular centroide (embedding promedio)
        embeddings = np.vstack([doc.embedding for doc in docs])
        centroid = np.mean(embeddings, axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-10)
        
        self._slave_profiles[node_id] = {
            "embedding": centroid,
            "document_count": len(docs),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Perfil actualizado para {node_id}: {len(docs)} documentos")
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del índice"""
        docs_per_node = {}
        for doc in self._documents.values():
            docs_per_node[doc.node_id] = docs_per_node.get(doc.node_id, 0) + 1
        
        return {
            "total_documents": len(self._documents),
            "total_nodes": len(self._slave_profiles),
            "documents_per_node": docs_per_node,
            "embedding_dim": self.embedding_dim
        }
