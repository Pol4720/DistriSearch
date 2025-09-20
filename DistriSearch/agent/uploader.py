import requests
import logging
from typing import List, Dict

logger = logging.getLogger('uploader')

class MetadataUploader:
    def __init__(self, backend_url, node_id, node_name):
        self.backend_url = backend_url
        self.node_id = node_id
        self.node_name = node_name
    
    def upload_metadata(self, files_metadata: List[Dict]) -> bool:
        """
        Envía metadatos de archivos al backend
        """
        if not files_metadata:
            logger.info("No hay archivos para enviar")
            return True
        
        # Añadir node_id a cada archivo
        for file_meta in files_metadata:
            file_meta['node_id'] = self.node_id
        
        try:
            logger.info(f"Enviando metadatos de {len(files_metadata)} archivos al backend")
            response = requests.post(
                f"{self.backend_url}/register/files",
                json=files_metadata
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Metadatos enviados correctamente. Indexados: {result.get('indexed_count', 0)}")
                return True
            else:
                logger.error(f"Error al enviar metadatos: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Error de conexión al enviar metadatos: {str(e)}")
            return False
