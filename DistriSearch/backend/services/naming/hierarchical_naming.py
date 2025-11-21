"""
Sistema de nombrado jerárquico para archivos (estilo DNS/Unix)
Permite organizar archivos en estructura de directorios virtuales
Ejemplo: /proyectos/distrisearch/docs/readme.md
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
import re
from pymongo import MongoClient
import os
import logging
import threading

logger = logging.getLogger(__name__)


class NamespaceNode:
    """Nodo en el árbol de nombres jerárquico"""
    
    def __init__(self, name: str, is_file: bool = False, parent: Optional['NamespaceNode'] = None):
        self.name = name
        self.is_file = is_file
        self.parent = parent
        self.children: Dict[str, 'NamespaceNode'] = {}
        
        # Metadata solo para archivos
        self.file_id: Optional[str] = None
        self.file_metadata: Optional[Dict] = None
        
        # Metadata del nodo
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.attributes: Dict[str, any] = {}
    
    def get_full_path(self) -> str:
        """Obtiene ruta completa desde la raíz"""
        if self.parent is None:
            return "/"
        
        parts = []
        current = self
        while current.parent is not None:
            parts.append(current.name)
            current = current.parent
        
        return "/" + "/".join(reversed(parts))
    
    def add_child(self, name: str, is_file: bool = False) -> 'NamespaceNode':
        """Agrega hijo si no existe"""
        if name not in self.children:
            self.children[name] = NamespaceNode(name, is_file, parent=self)
            self.updated_at = datetime.utcnow()
        
        return self.children[name]
    
    def remove_child(self, name: str) -> bool:
        """Elimina hijo"""
        if name in self.children:
            del self.children[name]
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario"""
        return {
            "name": self.name,
            "is_file": self.is_file,
            "full_path": self.get_full_path(),
            "children": list(self.children.keys()),
            "file_id": self.file_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "attributes": self.attributes
        }


class HierarchicalNamespace:
    """
    Sistema de nombres jerárquico con persistencia en MongoDB
    Características:
    - Rutas estilo Unix: /dir1/dir2/archivo.txt
    - Aliases (symbolic links)
    - Búsqueda por patrón (wildcards)
    - Navegación por directorio
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DBNAME", "distrisearch")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        
        # Árbol en memoria (cache)
        self.root = NamespaceNode("/")
        
        # Aliases: alias_path -> real_path
        self.aliases: Dict[str, str] = {}
        
        # Inicializar colecciones
        self._init_collections()
        
        # Cargar desde DB
        self._load_from_db()
        
        logger.info("✅ HierarchicalNamespace inicializado")
    
    def _init_collections(self):
        """Inicializa colecciones MongoDB"""
        # Colección para paths
        self.db.namespace_paths.create_index("path", unique=True)
        self.db.namespace_paths.create_index("parent_path")
        
        # Colección para aliases
        self.db.namespace_aliases.create_index("alias", unique=True)
    
    def _load_from_db(self):
        """Carga namespace desde MongoDB al arrancar"""
        try:
            # Cargar todos los paths
            paths = list(self.db.namespace_paths.find().sort("path", 1))
            
            for doc in paths:
                self._reconstruct_path(doc)
            
            # Cargar aliases
            aliases = list(self.db.namespace_aliases.find())
            for alias_doc in aliases:
                self.aliases[alias_doc['alias']] = alias_doc['real_path']
            
            logger.info(f"📂 Cargados {len(paths)} paths y {len(aliases)} aliases desde DB")
            
        except Exception as e:
            logger.error(f"Error cargando namespace desde DB: {e}")
    
    def _reconstruct_path(self, doc: Dict):
        """Reconstruye un path en el árbol desde documento DB"""
        path = doc['path']
        parts = [p for p in path.split('/') if p]
        
        current = self.root
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            is_file = is_last and doc.get('is_file', False)
            
            if part not in current.children:
                current.children[part] = NamespaceNode(part, is_file, parent=current)
            
            current = current.children[part]
        
        # Restaurar metadata si es archivo
        if doc.get('is_file'):
            current.file_id = doc.get('file_id')
            current.file_metadata = doc.get('file_metadata')
            current.attributes = doc.get('attributes', {})
    
    def register_path(self, path: str, file_id: str, metadata: Dict) -> bool:
        """
        Registra un archivo en el namespace jerárquico
        Ejemplo: /proyectos/distrisearch/backend/main.py
        """
        if not path.startswith('/'):
            path = '/' + path
        
        parts = [p for p in path.split('/') if p]
        
        if not parts:
            logger.error("Path vacío")
            return False
        
        try:
            # Crear directorios intermedios
            current = self.root
            for part in parts[:-1]:
                current = current.add_child(part, is_file=False)
            
            # Crear archivo
            filename = parts[-1]
            file_node = current.add_child(filename, is_file=True)
            file_node.file_id = file_id
            file_node.file_metadata = metadata
            file_node.updated_at = datetime.utcnow()
            
            # Persistir en DB
            self.db.namespace_paths.update_one(
                {"path": path},
                {
                    "$set": {
                        "path": path,
                        "parent_path": current.get_full_path(),
                        "name": filename,
                        "is_file": True,
                        "file_id": file_id,
                        "file_metadata": metadata,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            logger.info(f"📝 Path registrado: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error registrando path {path}: {e}")
            return False
    
    def resolve(self, path: str) -> Optional[Dict]:
        """
        Resuelve un path a información de archivo
        Soporta aliases
        """
        # Normalizar path
        if not path.startswith('/'):
            path = '/' + path
        
        # Verificar si es alias
        if path in self.aliases:
            path = self.aliases[path]
        
        parts = [p for p in path.split('/') if p]
        
        current = self.root
        for part in parts:
            if part not in current.children:
                return None
            current = current.children[part]
        
        if current.is_file:
            return {
                "file_id": current.file_id,
                "metadata": current.file_metadata,
                "path": path,
                "full_path": current.get_full_path(),
                "name": current.name,
                "created_at": current.created_at,
                "updated_at": current.updated_at,
                "attributes": current.attributes
            }
        
        return None
    
    def list_directory(self, path: str = "/") -> List[Dict]:
        """
        Lista contenidos de un directorio
        Retorna tanto directorios como archivos
        """
        if not path.startswith('/'):
            path = '/' + path
        
        parts = [p for p in path.split('/') if p]
        
        current = self.root
        for part in parts:
            if part not in current.children:
                return []
            current = current.children[part]
        
        result = []
        for name, node in current.children.items():
            result.append({
                "name": name,
                "is_file": node.is_file,
                "full_path": node.get_full_path(),
                "file_id": node.file_id if node.is_file else None,
                "updated_at": node.updated_at
            })
        
        return sorted(result, key=lambda x: (x['is_file'], x['name']))
    
    def create_alias(self, alias_path: str, real_path: str) -> bool:
        """
        Crea un alias (symbolic link)
        Ejemplo: /latest -> /proyectos/distrisearch/v1.0/readme.md
        """
        if not alias_path.startswith('/'):
            alias_path = '/' + alias_path
        
        if not real_path.startswith('/'):
            real_path = '/' + real_path
        
        # Verificar que el path real existe
        if self.resolve(real_path) is None:
            logger.error(f"Path real no existe: {real_path}")
            return False
        
        try:
            self.aliases[alias_path] = real_path
            
            # Persistir en DB
            self.db.namespace_aliases.update_one(
                {"alias": alias_path},
                {
                    "$set": {
                        "alias": alias_path,
                        "real_path": real_path,
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            logger.info(f"🔗 Alias creado: {alias_path} -> {real_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creando alias: {e}")
            return False
    
    def search_by_pattern(self, pattern: str) -> List[Dict]:
        """
        Busca archivos por patrón (wildcards)
        Soporta * y ?
        Ejemplo: /*.txt, /proyectos/*/readme.md
        """
        import fnmatch
        
        results = []
        
        def _search_recursive(node: NamespaceNode):
            full_path = node.get_full_path()
            
            if node.is_file and fnmatch.fnmatch(full_path, pattern):
                results.append({
                    "file_id": node.file_id,
                    "metadata": node.file_metadata,
                    "path": full_path,
                    "name": node.name
                })
            
            for child in node.children.values():
                _search_recursive(child)
        
        _search_recursive(self.root)
        return results
    
    def get_tree_structure(self, path: str = "/", max_depth: int = 3) -> Dict:
        """
        Obtiene estructura de árbol para visualización
        """
        if not path.startswith('/'):
            path = '/' + path
        
        parts = [p for p in path.split('/') if p]
        
        current = self.root
        for part in parts:
            if part not in current.children:
                return {}
            current = current.children[part]
        
        def _build_tree(node: NamespaceNode, depth: int) -> Dict:
            if depth >= max_depth:
                return {"name": node.name, "truncated": True}
            
            tree = {
                "name": node.name,
                "is_file": node.is_file,
                "full_path": node.get_full_path()
            }
            
            if not node.is_file and node.children:
                tree["children"] = [
                    _build_tree(child, depth + 1) 
                    for child in node.children.values()
                ]
            
            return tree
        
        return _build_tree(current, 0)
    
    def delete_path(self, path: str, recursive: bool = False) -> bool:
        """
        Elimina un path del namespace
        Si recursive=True, elimina directorios con contenido
        """
        if not path.startswith('/'):
            path = '/' + path
        
        parts = [p for p in path.split('/') if p]
        
        if not parts:
            logger.error("No se puede eliminar raíz")
            return False
        
        try:
            # Navegar hasta el padre
            current = self.root
            for part in parts[:-1]:
                if part not in current.children:
                    return False
                current = current.children[part]
            
            # Verificar si existe
            target_name = parts[-1]
            if target_name not in current.children:
                return False
            
            target_node = current.children[target_name]
            
            # Verificar si es directorio con contenido
            if not target_node.is_file and target_node.children and not recursive:
                logger.error(f"Directorio no vacío: {path}. Use recursive=True")
                return False
            
            # Eliminar del árbol
            current.remove_child(target_name)
            
            # Eliminar de DB
            self.db.namespace_paths.delete_one({"path": path})
            
            # Si era directorio, eliminar todos los hijos
            if recursive and not target_node.is_file:
                self.db.namespace_paths.delete_many({"path": {"$regex": f"^{path}/"}})
            
            logger.info(f"🗑️ Path eliminado: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando path {path}: {e}")
            return False


# Singleton
_namespace = None
_namespace_lock = threading.Lock()

def get_namespace() -> HierarchicalNamespace:
    """Obtiene instancia singleton del namespace"""
    global _namespace
    if _namespace is None:
        with _namespace_lock:
            if _namespace is None:
                _namespace = HierarchicalNamespace()
    return _namespace