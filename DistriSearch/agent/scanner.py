import os
import hashlib
import mimetypes
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Librerías para extracción de texto (se instalarán en backend/agent requirements)
try:
    import PyPDF2  # PDF
except Exception:  # pragma: no cover
    PyPDF2 = None
try:
    import docx  # python-docx para .docx
except Exception:  # pragma: no cover
    docx = None
try:
    import csv
except Exception:
    csv = None
try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

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
        
        content_text: Optional[str] = self._extract_text(filepath, mime_type)

        return {
            'file_id': file_hash,
            'name': os.path.basename(filepath),
            'path': rel_path,
            'size': file_size,
            'mime_type': mime_type,
            'type': file_type,
            'last_updated': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
            'content': content_text
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

    # ---- Extracción de contenido ----
    def _extract_text(self, filepath: str, mime_type: str) -> Optional[str]:
        """Devuelve texto extraído o None. Limita tamaño para no saturar red/DB."""
        max_chars = 200000  # ~200KB de texto
        try:
            if mime_type.startswith('text/'):
                return self._read_text_file(filepath, max_chars)
            if mime_type == 'application/pdf' and PyPDF2:
                return self._read_pdf(filepath, max_chars)
            if mime_type in ('application/vnd.openxmlformats-officedocument.wordprocessingml.document',) and docx:
                return self._read_docx(filepath, max_chars)
            if mime_type in ('text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
                return self._read_tabular(filepath, max_chars)
        except Exception as e:
            logger.debug(f"No se pudo extraer texto de {filepath}: {e}")
        return None

    def _read_text_file(self, path: str, max_chars: int) -> str:
        with open(path, 'r', errors='ignore', encoding='utf-8', newline='') as f:
            data = f.read(max_chars)
        return data

    def _read_pdf(self, path: str, max_chars: int) -> Optional[str]:
        if not PyPDF2:
            return None
        text_parts: List[str] = []
        with open(path, 'rb') as f:
            try:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages[:50]:  # límite de páginas
                    if len(''.join(text_parts)) > max_chars:
                        break
                    extracted = page.extract_text() or ''
                    text_parts.append(extracted)
            except Exception:
                return None
        return ('\n'.join(text_parts))[:max_chars]

    def _read_docx(self, path: str, max_chars: int) -> Optional[str]:
        if not docx:
            return None
        document = docx.Document(path)
        text = '\n'.join(p.text for p in document.paragraphs)
        return text[:max_chars]

    def _read_tabular(self, path: str, max_chars: int) -> Optional[str]:
        # Intentar pandas primero para csv/xlsx si disponible
        if pd:
            try:
                if path.lower().endswith('.csv'):
                    df = pd.read_csv(path, nrows=500)  # leer parcialmente
                else:
                    df = pd.read_excel(path, nrows=200)
                text = df.to_csv(index=False)
                return text[:max_chars]
            except Exception:
                return None
        # Fallback CSV simple
        if csv and path.lower().endswith('.csv'):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    rows = []
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i > 500:
                            break
                        rows.append(','.join(row))
                return '\n'.join(rows)[:max_chars]
            except Exception:
                return None
        return None
