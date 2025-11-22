import requests
from typing import Dict, List, Optional
import streamlit as st

class ApiClient:
    """Cliente para interactuar con la API del backend"""

    def __init__(self, base_url: str, api_key: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        if api_key:
            self.headers["X-API-KEY"] = api_key
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
    
    def set_token(self, token: str):
        """Actualiza el token de autenticación"""
        self.headers["Authorization"] = f"Bearer {token}"
    
    def _handle_response(self, response):
        """Maneja respuestas HTTP con logging de errores"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            raise Exception(f"HTTP {response.status_code}: {error_detail}")
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
    
    # ✅ NUEVO: Autenticación
    def login(self, username: str, password: str) -> Dict:
        """Inicia sesión y retorna token"""
        response = requests.post(
            f"{self.base_url}/auth/token",
            data={"username": username, "password": password},
            timeout=10
        )
        return self._handle_response(response)
    
    def register(self, email: str, username: str, password: str) -> Dict:
        """Registra un nuevo usuario"""
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={"email": email, "username": username, "password": password},
            timeout=10
        )
        return self._handle_response(response)
    
    def get_current_user(self) -> Dict:
        """Obtiene información del usuario actual"""
        response = requests.get(
            f"{self.base_url}/auth/me",
            headers=self.headers,
            timeout=5
        )
        return self._handle_response(response)
    
    # ✅ BÚSQUEDA
    def search_files(self, query: str, file_type: Optional[str] = None, max_results: int = 50) -> Dict:
        """Busca archivos en el sistema"""
        params = {
            'q': query,
            'max_results': max_results
        }
        
        if file_type:
            params['file_type'] = file_type
        
        response = requests.get(
            f"{self.base_url}/search/",
            params=params,
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)

    def search_files_with_score(self, query: str, file_type: Optional[str] = None, max_results: int = 50) -> Dict:
        """Búsqueda incluyendo el score BM25"""
        params = {
            'q': query,
            'max_results': max_results,
            'include_score': 'true'
        }
        if file_type:
            params['file_type'] = file_type
        
        response = requests.get(
            f"{self.base_url}/search/",
            params=params,
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)
    
    # ✅ NODOS
    def get_nodes(self) -> List[Dict]:
        """Obtiene la lista de nodos conectados"""
        response = requests.get(
            f"{self.base_url}/search/nodes",
            headers=self.headers,
            timeout=5
        )
        return self._handle_response(response)
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """Obtiene información de un nodo específico"""
        try:
            nodes = self.get_nodes()
            for node in nodes:
                if node.get('node_id') == node_id:
                    return node
            return None
        except:
            return None

    def register_node(self, node: Dict) -> Dict:
        """Registra un nuevo nodo"""
        response = requests.post(
            f"{self.base_url}/register/node",
            json=node,
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)

    def delete_node(self, node_id: str, delete_files: bool = True) -> Dict:
        """Elimina un nodo"""
        response = requests.delete(
            f"{self.base_url}/register/node/{node_id}",
            params={"delete_files": str(delete_files).lower()},
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)
    
    # ✅ ESTADÍSTICAS
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del sistema"""
        response = requests.get(
            f"{self.base_url}/search/stats",
            headers=self.headers,
            timeout=5
        )
        return self._handle_response(response)
    
    # ✅ DESCARGA
    def get_download_url(self, file_id: str) -> Dict:
        """Obtiene información de descarga del backend"""
        response = requests.post(
            f"{self.base_url}/download/",
            json={'file_id': file_id},
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)
    
    # ✅ REPLICACIÓN
    def run_replication(self, batch: int = 25) -> Dict:
        """Ejecuta replicación de archivos"""
        response = requests.post(
            f"{self.base_url}/auth/replication/sync",
            headers=self.headers,
            timeout=60
        )
        return self._handle_response(response)
    
    def get_replication_status(self) -> Dict:
        """Obtiene estado de replicación"""
        response = requests.get(
            f"{self.base_url}/auth/replication/status",
            headers=self.headers,
            timeout=5
        )
        return self._handle_response(response)
    
    # ✅ CONFIGURACIÓN AVANZADA (Nodos simulados)
    def set_node_mount(self, node_id: str, folder: str) -> Dict:
        """Configura carpeta montada para un nodo"""
        response = requests.post(
            f"{self.base_url}/register/node/{node_id}/mount",
            json={"folder": folder},
            headers=self.headers,
            timeout=10
        )
        return self._handle_response(response)

    def import_node_folder(self, node_id: str) -> Dict:
        """Escanea e importa archivos de carpeta de nodo"""
        response = requests.post(
            f"{self.base_url}/register/node/{node_id}/scan-import",
            headers=self.headers,
            timeout=60
        )
        return self._handle_response(response)
