"""
Tests de consistencia de replicación
Valida que el sistema mantiene consistencia eventual
"""
import pytest
import time
import requests
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# ✅ Cargar configuración
load_dotenv('.env.test')

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("ADMIN_API_KEY", "test_key")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "distrisearch")

HEADERS = {"X-API-KEY": API_KEY}


class TestReplicationConsistency:
    """Tests de consistencia de réplicas"""
    
    @pytest.mark.consistency
    def test_eventual_consistency_after_concurrent_writes(self):
        """
        TEST: Escrituras concurrentes deben converger a estado consistente
        """
        print("\n" + "="*80)
        print("TEST: Consistencia eventual tras escrituras concurrentes")
        print("="*80)
        
        # Crear nodos
        for i in range(3):
            requests.post(
                f"{BACKEND_URL}/register/node",
                json={
                    "node_id": f"consistency_node_{i}",
                    "name": f"Node {i}",
                    "ip_address": "127.0.0.1",
                    "port": 8300 + i,
                    "status": "online",
                    "shared_files_count": 0
                },
                headers=HEADERS
            )
        
        # Escritura 1
        file_content_v1 = "Version 1 of file"
        response1 = requests.post(
            f"{BACKEND_URL}/register/upload",
            files={'file': ('conflict_file.txt', file_content_v1.encode())},
            data={'node_id': 'consistency_node_0', 'replicate': 'true'},
            headers=HEADERS
        )
        
        time.sleep(1)
        
        # Escritura 2 (más reciente - debe ganar)
        file_content_v2 = "Version 2 of file (should win)"
        response2 = requests.post(
            f"{BACKEND_URL}/register/upload",
            files={'file': ('conflict_file.txt', file_content_v2.encode())},
            data={'node_id': 'consistency_node_1', 'replicate': 'true'},
            headers=HEADERS
        )
        
        # Esperar sincronización
        print("⏳ Esperando sincronización (60s)...")
        time.sleep(60)
        
        # Verificar consistencia
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DBNAME]
        
        replicas = list(db.files.find({"name": "conflict_file.txt"}))
        
        print(f"\nRéplicas encontradas: {len(replicas)}")
        
        unique_hashes = set(r.get('content_hash') for r in replicas if r.get('content_hash'))
        
        print(f"Hashes únicos: {len(unique_hashes)}")
        
        assert len(unique_hashes) == 1, f"❌ FALLO: Inconsistencia - {len(unique_hashes)} versiones"
        
        print("✅ Consistencia eventual lograda")
    
    @pytest.mark.replication
    def test_replication_factor_maintained(self):
        """
        TEST: Factor de replicación debe mantenerse en k=3
        """
        print("\n" + "="*80)
        print("TEST: Mantenimiento de factor de replicación K=3")
        print("="*80)
        
        # Crear 5 nodos
        for i in range(5):
            requests.post(
                f"{BACKEND_URL}/register/node",
                json={
                    "node_id": f"repl_node_{i}",
                    "name": f"Replication Node {i}",
                    "ip_address": "127.0.0.1",
                    "port": 8400 + i,
                    "status": "online",
                    "shared_files_count": 0
                },
                headers=HEADERS
            )
        
        # Subir archivo
        response = requests.post(
            f"{BACKEND_URL}/register/upload",
            files={'file': ('replication_test.txt', b'Test content for replication')},
            data={'node_id': 'repl_node_0', 'replicate': 'true'},
            headers=HEADERS
        )
        
        assert response.status_code == 200
        file_id = response.json()['file_id']
        
        time.sleep(10)
        
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DBNAME]
        
        replicas_count = db.files.count_documents({"file_id": file_id})
        
        print(f"Réplicas creadas: {replicas_count}")
        
        expected_replicas = 3
        
        assert replicas_count >= expected_replicas, f"❌ FALLO: Solo {replicas_count} réplicas"
        
        print("✅ Factor de replicación correcto")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])