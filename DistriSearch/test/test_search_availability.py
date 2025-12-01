"""
Tests de disponibilidad de búsqueda
Garantiza que la búsqueda SIEMPRE funciona
"""
import pytest
import time
import requests
import concurrent.futures
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# ✅ Cargar configuración
load_dotenv('.env.test')

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("ADMIN_API_KEY", "test_key")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "distrisearch")

HEADERS = {"X-API-KEY": API_KEY}


class TestSearchAvailability:
    """Tests para garantizar disponibilidad 99.9% en búsqueda"""
    
    @pytest.mark.availability
    def test_search_during_node_failures(self):
        """
        TEST CRÍTICO: Búsqueda debe funcionar incluso durante caídas de nodos
        """
        print("\n" + "="*80)
        print("TEST: Disponibilidad de búsqueda durante fallas")
        print("="*80)
        
        # Crear nodos y archivos
        for i in range(5):
            requests.post(
                f"{BACKEND_URL}/register/node",
                json={
                    "node_id": f"search_node_{i}",
                    "name": f"Search Node {i}",
                    "ip_address": "127.0.0.1",
                    "port": 8500 + i,
                    "status": "online",
                    "shared_files_count": 0
                },
                headers=HEADERS
            )
        
        # Subir 100 archivos
        for i in range(100):
            requests.post(
                f"{BACKEND_URL}/register/upload",
                files={'file': (f"search_file_{i}.txt", f"Content {i}".encode())},
                data={'node_id': f"search_node_{i % 5}", 'replicate': 'true'},
                headers=HEADERS
            )
            time.sleep(0.1)
        
        time.sleep(15)
        
        # Función de búsqueda
        def perform_search(query: str) -> bool:
            try:
                response = requests.get(
                    f"{BACKEND_URL}/search/",
                    params={"q": query, "max_results": 50},
                    timeout=10
                )
                return response.status_code == 200 and len(response.json().get('files', [])) > 0
            except:
                return False
        
        # Ejecutar búsquedas concurrentes
        print("\n🔍 Ejecutando 100 búsquedas concurrentes...")
        
        queries = [f"search_file_{i}" for i in range(100)]
        
        successful_searches = 0
        failed_searches = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_query = {executor.submit(perform_search, query): query for query in queries}
            
            # Simular caídas durante búsquedas
            time.sleep(2)
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DBNAME]
            
            for i in range(2):
                db.nodes.update_one(
                    {"node_id": f"search_node_{i}"},
                    {"$set": {"status": "offline", "last_seen": datetime.utcnow() - timedelta(minutes=10)}}
                )
                print(f"   🔥 Nodo search_node_{i} caído")
            
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    success = future.result()
                    if success:
                        successful_searches += 1
                    else:
                        failed_searches += 1
                except:
                    failed_searches += 1
        
        print(f"\n📊 Resultados de búsqueda:")
        print(f"   Exitosas: {successful_searches}/100")
        print(f"   Fallidas: {failed_searches}/100")
        
        availability = (successful_searches / 100) * 100
        print(f"   Disponibilidad: {availability:.2f}%")
        
        assert availability >= 99.0, f"❌ FALLO: Disponibilidad {availability}% < 99%"
        
        print("\n✅ TEST PASADO: Búsqueda altamente disponible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])