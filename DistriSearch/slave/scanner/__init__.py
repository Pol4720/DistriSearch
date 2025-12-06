"""
DistriSearch Slave - File Scanner
==================================
Escanea directorios locales y registra archivos en el índice.
"""

import os
import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import List, Optional, Callable, Set
from datetime import datetime
from dataclasses import dataclass

from core.models import FileType

logger = logging.getLogger(__name__)

# Extensiones por tipo de archivo
EXTENSION_MAP = {
    FileType.DOCUMENT: {'.txt', '.doc', '.docx', '.pdf', '.rtf', '.odt', '.md', '.tex'},
    FileType.IMAGE: {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'},
    FileType.VIDEO: {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'},
    FileType.AUDIO: {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'},
    FileType.CODE: {'.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt'},
    FileType.DATA: {'.json', '.xml', '.yaml', '.yml', '.csv', '.sql', '.db', '.sqlite'},
    FileType.ARCHIVE: {'.zip', '.tar', '.gz', '.rar', '.7z', '.bz2', '.xz'},
    FileType.EXECUTABLE: {'.exe', '.msi', '.sh', '.bat', '.cmd', '.ps1'},
}


@dataclass
class ScannedFile:
    """Información de un archivo escaneado."""
    file_id: str
    name: str
    path: str
    size: int
    mime_type: str
    file_type: FileType
    content_hash: str
    last_modified: datetime
    content: Optional[str] = None  # Solo para archivos de texto pequeños


class FileScanner:
    """Scanner de archivos locales para nodos Slave."""
    
    def __init__(
        self,
        node_id: str,
        base_path: str,
        max_file_size: int = 100 * 1024 * 1024,  # 100 MB
        extract_content: bool = True,
        max_content_size: int = 1024 * 1024,  # 1 MB para extracción de contenido
        excluded_dirs: Optional[Set[str]] = None,
        excluded_extensions: Optional[Set[str]] = None
    ):
        """
        Inicializa el scanner.
        
        Args:
            node_id: ID del nodo slave
            base_path: Directorio raíz a escanear
            max_file_size: Tamaño máximo de archivo a indexar
            extract_content: Si extraer contenido de texto
            max_content_size: Tamaño máximo para extracción de contenido
            excluded_dirs: Directorios a excluir
            excluded_extensions: Extensiones a excluir
        """
        self.node_id = node_id
        self.base_path = Path(base_path).resolve()
        self.max_file_size = max_file_size
        self.extract_content = extract_content
        self.max_content_size = max_content_size
        
        self.excluded_dirs = excluded_dirs or {
            '.git', '.svn', '__pycache__', 'node_modules', 
            '.venv', 'venv', '.env', 'dist', 'build'
        }
        self.excluded_extensions = excluded_extensions or {
            '.pyc', '.pyo', '.class', '.o', '.obj', '.dll', '.so'
        }
        
        self._files_scanned = 0
        self._bytes_scanned = 0
    
    def _get_file_type(self, path: Path) -> FileType:
        """Determina el tipo de archivo por su extensión."""
        ext = path.suffix.lower()
        
        for file_type, extensions in EXTENSION_MAP.items():
            if ext in extensions:
                return file_type
        
        return FileType.OTHER
    
    def _compute_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Calcula hash SHA-256 del archivo."""
        hasher = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, PermissionError):
            return ""
    
    def _generate_file_id(self, path: Path, content_hash: str) -> str:
        """Genera ID único para el archivo."""
        rel_path = path.relative_to(self.base_path) if path.is_relative_to(self.base_path) else path
        unique_str = f"{self.node_id}:{rel_path}:{content_hash}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16]
    
    def _extract_text_content(self, path: Path) -> Optional[str]:
        """Extrae contenido de texto del archivo si es posible."""
        if not self.extract_content:
            return None
        
        # Solo extraer de archivos pequeños
        try:
            size = path.stat().st_size
            if size > self.max_content_size:
                return None
        except OSError:
            return None
        
        # Solo archivos de texto
        file_type = self._get_file_type(path)
        if file_type not in {FileType.DOCUMENT, FileType.CODE, FileType.DATA}:
            return None
        
        # Intentar leer como texto
        encodings = ['utf-8', 'latin-1', 'cp1252']
        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, IOError):
                continue
        
        return None
    
    def _should_skip(self, path: Path) -> bool:
        """Determina si un archivo o directorio debe ser omitido."""
        name = path.name
        
        # Archivos ocultos
        if name.startswith('.'):
            return True
        
        # Directorios excluidos
        if path.is_dir() and name in self.excluded_dirs:
            return True
        
        # Extensiones excluidas
        if path.is_file() and path.suffix.lower() in self.excluded_extensions:
            return True
        
        return False
    
    def scan_file(self, path: Path) -> Optional[ScannedFile]:
        """
        Escanea un archivo individual.
        
        Args:
            path: Ruta al archivo
            
        Returns:
            ScannedFile o None si debe omitirse
        """
        try:
            if not path.is_file():
                return None
            
            if self._should_skip(path):
                return None
            
            stat = path.stat()
            
            # Omitir archivos muy grandes
            if stat.st_size > self.max_file_size:
                logger.debug(f"Archivo muy grande omitido: {path}")
                return None
            
            # Calcular hash
            content_hash = self._compute_hash(path)
            if not content_hash:
                return None
            
            # Determinar tipo MIME
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Extraer contenido de texto
            content = self._extract_text_content(path)
            
            # Crear objeto ScannedFile
            scanned = ScannedFile(
                file_id=self._generate_file_id(path, content_hash),
                name=path.name,
                path=str(path),
                size=stat.st_size,
                mime_type=mime_type,
                file_type=self._get_file_type(path),
                content_hash=content_hash,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                content=content
            )
            
            self._files_scanned += 1
            self._bytes_scanned += stat.st_size
            
            return scanned
            
        except (OSError, PermissionError) as e:
            logger.warning(f"Error escaneando {path}: {e}")
            return None
    
    def scan_directory(
        self,
        path: Optional[Path] = None,
        recursive: bool = True,
        on_file: Optional[Callable[[ScannedFile], None]] = None
    ) -> List[ScannedFile]:
        """
        Escanea un directorio completo.
        
        Args:
            path: Directorio a escanear (default: base_path)
            recursive: Si escanear subdirectorios
            on_file: Callback para cada archivo encontrado
            
        Returns:
            Lista de archivos escaneados
        """
        scan_path = path or self.base_path
        results = []
        
        try:
            if recursive:
                for root, dirs, files in os.walk(scan_path):
                    root_path = Path(root)
                    
                    # Filtrar directorios excluidos
                    dirs[:] = [d for d in dirs if not self._should_skip(root_path / d)]
                    
                    for filename in files:
                        file_path = root_path / filename
                        scanned = self.scan_file(file_path)
                        
                        if scanned:
                            results.append(scanned)
                            if on_file:
                                on_file(scanned)
            else:
                for item in scan_path.iterdir():
                    if item.is_file():
                        scanned = self.scan_file(item)
                        if scanned:
                            results.append(scanned)
                            if on_file:
                                on_file(scanned)
        
        except PermissionError as e:
            logger.warning(f"Permiso denegado: {scan_path}")
        
        return results
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del escaneo."""
        return {
            "node_id": self.node_id,
            "base_path": str(self.base_path),
            "files_scanned": self._files_scanned,
            "bytes_scanned": self._bytes_scanned,
            "bytes_scanned_mb": round(self._bytes_scanned / (1024 * 1024), 2)
        }
    
    def reset_stats(self):
        """Reinicia las estadísticas."""
        self._files_scanned = 0
        self._bytes_scanned = 0


def create_scanner(node_id: str, base_path: str, **kwargs) -> FileScanner:
    """Factory function para crear un FileScanner."""
    return FileScanner(node_id, base_path, **kwargs)
