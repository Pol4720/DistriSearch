import requests
from typing import Dict, List, Optional

class ApiClient:
    """Cliente para interactuar con la API del backend"""
    
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
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
        
        response = requests.get(f"{self.base_url}/search/", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_download_url(self, file_id: str) -> str:
        """
        Obtiene la URL para descargar un archivo
        """
        response = requests.post(
            f"{self.base_url}/download/",
            json={'file_id': file_id}
        )
        response.raise_for_status()
        result = response.json()
        return result.get('download_url')
    
    def get_nodes(self) -> List[Dict]:
        """
        Obtiene la lista de nodos conectados
        """
        response = requests.get(f"{self.base_url}/search/nodes")
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas del sistema
        """
        response = requests.get(f"{self.base_url}/search/stats")
        response.raise_for_status()
        return response.json()

    # --- Centralized mode helpers ---
    def central_scan(self, folder: Optional[str] = None) -> Dict:
        """Escanea la carpeta central y reindexa archivos."""
        payload = {"folder": folder} if folder else {}
        response = requests.post(f"{self.base_url}/central/scan", json=payload)
        response.raise_for_status()
        return response.json()

    def get_mode(self) -> Dict:
        """Obtiene estado de modos centralizado/distribuido."""
        response = requests.get(f"{self.base_url}/central/mode")
        response.raise_for_status()
        return response.json()
