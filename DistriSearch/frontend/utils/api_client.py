import requests
from typing import Dict, List, Optional

class ApiClient:
    """Cliente para interactuar con la API del backend"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        if api_key:
            self.headers["X-API-KEY"] = api_key
    
    def search_files(self, query: str, file_type: Optional[str] = None, max_results: int = 50) -> Dict:
        """
        Busca archivos en el sistema
        """
        params = {
            'q': query,
            'max_results': max_results
        }
        
        if file_type:
            params['file_type'] = file_type
        response = requests.get(
            f"{self.base_url}/search/",
            params=params,
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def search_files_with_score(self, query: str, file_type: Optional[str] = None, max_results: int = 50) -> Dict:
        """Búsqueda incluyendo el score por resultado (bm25)."""
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
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()
    
    def get_download_url(self, file_id: str) -> Dict:
        """Obtiene información de descarga del backend.

        Respuesta esperada:
        {
          "download_url": "http://.../download/file/{id}",
          "direct_node_url": "http://..." | null,
          "node": {...}
        }
        """
        response = requests.post(
            f"{self.base_url}/download/",
            json={'file_id': file_id},
            headers=self.headers or None
        )
        response.raise_for_status()
        return response.json()
    
    def get_nodes(self) -> List[Dict]:
        """
        Obtiene la lista de nodos conectados
        """
        response = requests.get(
            f"{self.base_url}/search/nodes",
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    # --- Node management ---
    def register_node(self, node: Dict) -> Dict:
        response = requests.post(
            f"{self.base_url}/register/node",
            json=node,
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def delete_node(self, node_id: str, delete_files: bool = True) -> Dict:
        response = requests.delete(
            f"{self.base_url}/register/node/{node_id}",
            params={"delete_files": str(delete_files).lower()},
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def run_replication(self, batch: int = 25) -> Dict:
        response = requests.post(
            f"{self.base_url}/central/replication/run",
            params={"batch": batch},
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def set_node_mount(self, node_id: str, folder: str) -> Dict:
        response = requests.post(
            f"{self.base_url}/register/node/{node_id}/mount",
            json={"folder": folder},
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def import_node_folder(self, node_id: str) -> Dict:
        response = requests.post(
            f"{self.base_url}/register/node/{node_id}/scan-import",
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas del sistema
        """
        response = requests.get(
            f"{self.base_url}/search/stats",
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    # --- Centralized mode helpers ---
    def central_scan(self, folder: Optional[str] = None) -> Dict:
        """Escanea la carpeta central y reindexa archivos."""
        payload = {"folder": folder} if folder else {}
        response = requests.post(
            f"{self.base_url}/central/scan",
            json=payload,
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def get_mode(self) -> Dict:
        """Obtiene estado de modos centralizado/distribuido."""
        response = requests.get(
            f"{self.base_url}/central/mode",
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    # --- DHT helpers ---
    def dht_start(self) -> Dict:
        """Inicia el servicio DHT en modo inproc si está habilitado."""
        response = requests.post(
            f"{self.base_url}/dht/start",
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def dht_join(self, seed_ip: str, seed_port: Optional[int] = None) -> Dict:
        params = {"seed_ip": seed_ip}
        if seed_port:
            params["seed_port"] = seed_port
        response = requests.post(
            f"{self.base_url}/dht/join",
            params=params,
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def dht_upload(self, filename: str, data: str) -> Dict:
        response = requests.post(
            f"{self.base_url}/dht/upload",
            params={"filename": filename, "data": data},
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def dht_download(self, filename: str) -> Dict:
        response = requests.post(
            f"{self.base_url}/dht/download",
            params={"filename": filename},
            headers=self.headers or None,
        )
        response.raise_for_status()
        return response.json()

    def dht_finger(self) -> Dict:
        response = requests.get(f"{self.base_url}/dht/finger", headers=self.headers or None)
        response.raise_for_status()
        return response.json()

    def dht_sucpred(self) -> Dict:
        response = requests.get(f"{self.base_url}/dht/sucpred", headers=self.headers or None)
        response.raise_for_status()
        return response.json()
