import os
import hashlib
import mimetypes
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger('scanner')

class FileScanner:
    def __init__(self, shared_folder):
        self.shared_folder = os.path.abspath(shared_folder)
        if not os.path.exists(self.shared_folder):
            os.makedirs(self.shared_folder, exist_ok=True)
            logger.info(f"Carpeta compartida creada: {self.shared_folder}")
        
        # Asegurar que mimetypes esté inicializado
        mimetypes.init()
    
    def scan(self) -> List[Dict]:
        """
        Escanea la carpeta compartida y retorna metadatos de los archivos
        """
        logger.info(f"Escaneando carpeta: {self.shared_folder}")
        files_metadata = []
        
        for root, _, files in os.walk(self.shared_folder):
            for filename in files:
                try:
                    filepath = os.path.join(root, filename)
                    metadata = self._extract_metadata(filepath)
                    files_metadata.append(metadata)
                except Exception as e:
                    logger.error(f"Error al procesar archivo {filename}: {str(e)}")
        
        return files_metadata
    
    def _extract_metadata(self, filepath: str) -> Dict:
        """
        Extrae metadatos de un archivo
        """
        # Calcular hash SHA256 (identifica únicamente al archivo)
        file_hash = self._calculate_hash(filepath)
        
        # Obtener tamaño
        file_size = os.path.getsize(filepath)
        
        # Obtener tipo MIME
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = 'application/octet-stream'  # tipo por defecto
        
        # Determinar categoría del archivo
        file_type = self._categorize_file(mime_type)
        
        # Ruta relativa a la carpeta compartida
        rel_path = os.path.relpath(filepath, self.shared_folder)
        
        return {
            'file_id': file_hash,
            'name': os.path.basename(filepath),
            'path': rel_path,
            'size': file_size,
            'mime_type': mime_type,
            'type': file_type,
            'last_updated': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
        }
    
    def _calculate_hash(self, filepath: str) -> str:
        """
        Calcula el hash SHA256 de un archivo
        """
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            # Leer en bloques de 4K para archivos grandes
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _categorize_file(self, mime_type: str) -> str:
        """
        Categoriza el archivo según su tipo MIME
        """
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type.startswith(('text/', 'application/pdf', 'application/msword', 
                                  'application/vnd.ms-', 'application/vnd.openxmlformats-')):
            return 'document'
        else:
            return 'other'
