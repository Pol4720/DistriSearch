"""
Persistencia de índice invertido en disco.
"""
import json
import logging
from pathlib import Path
from typing import Dict
from storage.inverted_index import InvertedIndex
from storage.document import Document, PostingEntry

logger = logging.getLogger(__name__)


class IndexPersistence:
    """Gestiona carga y guardado de índices."""
    
    @staticmethod
    def save(index: InvertedIndex, filepath: Path):
        """
        Guarda índice a disco.
        
        Args:
            index: Índice a guardar
            filepath: Ruta del archivo
        """
        data = {
            "index": {
                term: [p.to_dict() for p in postings]
                for term, postings in index.index.items()
            },
            "documents": {
                doc_id: doc.to_dict()
                for doc_id, doc in index.documents.items()
            },
            "stats": index.get_stats()
        }
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(
            f"Índice guardado: {filepath} "
            f"({index.num_terms} términos, {index.num_documents} docs)"
        )
    
    @staticmethod
    def load(filepath: Path) -> InvertedIndex:
        """
        Carga índice desde disco.
        
        Args:
            filepath: Ruta del archivo
            
        Returns:
            Índice cargado
        """
        index = InvertedIndex()
        
        if not filepath.exists():
            logger.info(f"Archivo no existe, creando índice vacío: {filepath}")
            return index
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Cargar documentos
            for doc_id, doc_data in data.get("documents", {}).items():
                index.documents[doc_id] = Document.from_dict(doc_data)
            
            # Cargar índice
            for term, postings_data in data.get("index", {}).items():
                index.index[term] = [
                    PostingEntry(**p) for p in postings_data
                ]
            
            # Actualizar estadísticas
            index.num_documents = len(index.documents)
            index.num_terms = len(index.index)
            
            logger.info(
                f"Índice cargado: {filepath} "
                f"({index.num_terms} términos, {index.num_documents} docs)"
            )
            
        except Exception as e:
            logger.error(f"Error cargando índice: {e}")
        
        return index


class PersistenceManager:
    """
    Gestiona persistencia de todos los componentes del nodo.
    """
    
    def __init__(self, base_path: str = "data"):
        """
        Args:
            base_path: Directorio base para persistencia
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_json(self, filename: str, data: Dict) -> None:
        """
        Guarda datos en JSON.
        
        Args:
            filename: Nombre del archivo
            data: Datos a guardar
        """
        filepath = self.base_path / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Guardado: {filepath}")
    
    def load_json(self, filename: str) -> Dict:
        """
        Carga datos desde JSON.
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            Datos cargados o diccionario vacío
        """
        filepath = self.base_path / filename
        if not filepath.exists():
            logger.debug(f"Archivo no existe: {filepath}")
            return {}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Cargado: {filepath}")
            return data
        except Exception as e:
            logger.error(f"Error cargando {filepath}: {e}")
            return {}
    
    def snapshot(self, name: str, data: Dict) -> None:
        """
        Crea snapshot con timestamp.
        
        Args:
            name: Nombre base del snapshot
            data: Datos a guardar
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.json"
        self.save_json(filename, data)
