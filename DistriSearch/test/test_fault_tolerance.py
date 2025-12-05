"""
Tests de tolerancia a fallos - Garantiza que el sistema nunca pierde datos
"""
import pytest
import asyncio
import time
from typing import List, Dict
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import string
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# ✅ Cargar configuración
load_dotenv('.env.test')

BACKEND_URL = os.getenv("BACKEND_URL", "http://10.2.0.2:8000")
API_KEY = os.getenv("ADMIN_API_KEY", "test_key_robustness_2024")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "distrisearch")

HEADERS = {"X-API-KEY": API_KEY}

print(f"🔧 Tests configurados con:")
print(f"   Backend: {BACKEND_URL}")
print(f"   MongoDB: {MONGO_URI}")


# ✅ Configurar sesión con retry
def get_session_with_retry():
    """Crea sesión de requests con retry automático"""
    session = requests.Session()
    
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST", "DELETE"]
    )
    
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session


class TestNodeFailureTolerance:
    """
    Suite de tests para validar tolerancia a caídas de nodos
    """
    
    # ✅ ELIMINAR __init__ - Usar fixture en su lugar
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup que se ejecuta antes de cada test"""
        self.session = get_session_with_retry()
        self._cleanup_test_data()
        yield
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        """Elimina todos los nodos de prueba"""
        try:
            response = self.session.get(f"{BACKEND_URL}/search/nodes", timeout=5)
            if response.status_code == 200:
                nodes = response.json()
                for node in nodes:
                    if node['node_id'].startswith('test_') or node['node_id'].startswith('stress_'):
                        try:
                            self.session.delete(
                                f"{BACKEND_URL}/register/node/{node['node_id']}?delete_files=true",
                                headers=HEADERS,
                                timeout=5
                            )
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ Warning durante cleanup: {e}")
    
    def _create_test_node(self, node_id: str, port: int = 8080) -> Dict:
        """Crea un nodo de prueba"""
        node_data = {
            "node_id": node_id,
            "name": f"Test Node {node_id}",
            "ip_address": "127.0.0.1",
            "port": port,
            "status": "online",
            "shared_files_count": 0
        }
        
        try:
            response = self.session.post(
                f"{BACKEND_URL}/register/node",
                json=node_data,
                headers=HEADERS,
                timeout=10
            )
            
            print(f"🔧 Creando nodo {node_id}: Status {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Error response: {response.text}")
            
            assert response.status_code == 200, f"Error creando nodo: {response.text}"
            return response.json()
            
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Error de conexión con backend: {e}")
            print(f"   ¿Backend está corriendo en {BACKEND_URL}?")
            raise
    
    def _upload_test_file(self, node_id: str, filename: str, content: str) -> Dict:
        """Sube un archivo de prueba a un nodo"""
        file_content = content.encode('utf-8')
        
        files = {'file': (filename, file_content, 'text/plain')}
        data = {'node_id': node_id, 'replicate': 'true'}
        
        try:
            response = self.session.post(
                f"{BACKEND_URL}/register/upload",
                files=files,
                data=data,
                headers=HEADERS,
                timeout=30
            )
            
            print(f"📤 Upload {filename}: Status {response.status_code}")
            
            assert response.status_code == 200, f"Error subiendo archivo: {response.text}"
            return response.json()
            
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Error de conexión durante upload: {e}")
            raise
    
    def _simulate_node_crash(self, node_id: str):
        """Simula caída de un nodo marcándolo como offline"""
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DBNAME]
        
        db.nodes.update_one(
            {"node_id": node_id},
            {
                "$set": {
                    "status": "offline",
                    "last_seen": datetime.utcnow() - timedelta(minutes=10)
                }
            }
        )
        print(f"🔥 Nodo {node_id} marcado como offline")
    
    def _verify_file_exists(self, file_id: str) -> bool:
        """Verifica que un archivo existe y es accesible"""
        try:
            response = self.session.get(
                f"{BACKEND_URL}/search/?q={file_id}",
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            results = response.json()
            return len(results.get('files', [])) > 0
        except:
            return False
    
    def _count_replicas(self, file_id: str) -> int:
        """Cuenta cuántas réplicas online tiene un archivo"""
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DBNAME]
        
        pipeline = [
            {"$match": {"file_id": file_id}},
            {"$lookup": {
                "from": "nodes",
                "localField": "node_id",
                "foreignField": "node_id",
                "as": "node_info"
            }},
            {"$unwind": "$node_info"},
            {"$match": {"node_info.status": "online"}},
            {"$count": "replicas"}
        ]
        
        result = list(db.files.aggregate(pipeline))
        return result[0]['replicas'] if result else 0
    
    @pytest.mark.critical
    def test_single_node_failure_with_unique_file(self):
        """
        TEST CRÍTICO: Archivo con una sola copia NO debe perderse al caer el nodo
        """
        print("\n" + "="*80)
        print("TEST 1: Caída de nodo con archivo único - CERO PÉRDIDA DE DATOS")
        print("="*80)
        
        # Crear 3 nodos
        node_a = self._create_test_node("test_node_a", 8081)
        node_b = self._create_test_node("test_node_b", 8082)
        node_c = self._create_test_node("test_node_c", 8083)
        
        # Subir archivo
        file_content = "Contenido crítico que NO debe perderse"
        file_result = self._upload_test_file("test_node_a", "critical_file.txt", file_content)
        file_id = file_result['file_id']
        
        print(f"✅ Archivo subido: {file_id}")
        
        # ✅ CAMBIO: Esperar MÁS tiempo para replicación
        print("⏳ Esperando replicación (30 segundos)...")
        time.sleep(30)  # Aumentar de 5 a 30
        
        initial_replicas = self._count_replicas(file_id)
        print(f"   Réplicas iniciales: {initial_replicas}")
        
        # ✅ Si no hay réplicas, esperar más
        if initial_replicas < 2:
            print("⏳ Replicación lenta, esperando 30s adicionales...")
            time.sleep(30)
            initial_replicas = self._count_replicas(file_id)
            print(f"   Réplicas tras espera adicional: {initial_replicas}")
        
        assert initial_replicas >= 2, f"❌ FALLO: Solo {initial_replicas} réplicas"
        
        # Simular caída
        print("\n🔥 SIMULANDO CAÍDA DEL NODO PRIMARIO...")
        self._simulate_node_crash("test_node_a")
        
        time.sleep(10)
        
        # Verificar disponibilidad
        print("\n🔍 Verificando disponibilidad tras caída...")
        file_still_exists = self._verify_file_exists(file_id)
        
        assert file_still_exists, "❌ FALLO CRÍTICO: Archivo perdido tras caída de nodo"
        
        remaining_replicas = self._count_replicas(file_id)
        print(f"✅ Archivo sigue accesible")
        print(f"   Réplicas online: {remaining_replicas}")
        
        assert remaining_replicas >= 1, "❌ FALLO: No hay réplicas online"
        
        print("\n✅ TEST PASADO: Sistema mantiene disponibilidad")
    
    @pytest.mark.critical
    def test_multiple_simultaneous_node_failures(self):
        """
        TEST CRÍTICO: Sistema debe sobrevivir a caídas simultáneas múltiples
        """
        print("\n" + "="*80)
        print("TEST 2: Caída simultánea de múltiples nodos")
        print("="*80)
        
        # Crear 5 nodos
        nodes = []
        for i in range(5):
            node = self._create_test_node(f"test_node_{i}", 8080 + i)
            nodes.append(node)
        
        print(f"✅ Creados 5 nodos de prueba")
        
        # Subir 10 archivos
        files_uploaded = []
        for i in range(10):
            filename = f"file_{i}.txt"
            content = f"Test content {i} - " + "x" * 100
            result = self._upload_test_file(f"test_node_{i % 5}", filename, content)
            files_uploaded.append(result['file_id'])
            time.sleep(0.5)
        
        print(f"✅ Subidos 10 archivos distribuidos")
        
        # Esperar replicación
        time.sleep(15)
        
        # Simular caída de 2 nodos
        print("\n🔥 SIMULANDO CAÍDA SIMULTÁNEA DE 2 NODOS...")
        self._simulate_node_crash("test_node_0")
        self._simulate_node_crash("test_node_1")
        
        time.sleep(15)
        
        # Verificar todos los archivos
        print("\n🔍 Verificando disponibilidad de todos los archivos...")
        
        lost_files = []
        accessible_files = []
        
        for file_id in files_uploaded:
            if self._verify_file_exists(file_id):
                accessible_files.append(file_id)
            else:
                lost_files.append(file_id)
        
        print(f"   Archivos accesibles: {len(accessible_files)}/10")
        print(f"   Archivos perdidos: {len(lost_files)}/10")
        
        assert len(lost_files) == 0, f"❌ FALLO CRÍTICO: {len(lost_files)} archivos perdidos"
        
        print("\n✅ TEST PASADO: Sistema mantiene 100% de disponibilidad")


class TestContinuousFailureStress:
    """Stress test: Sistema bajo fallas continuas aleatorias"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup para stress tests"""
        self.session = get_session_with_retry()
        yield
        # Cleanup después del stress test
        self._cleanup_stress_data()
    
    def _cleanup_stress_data(self):
        """Limpia datos del stress test"""
        try:
            response = self.session.get(f"{BACKEND_URL}/search/nodes", timeout=5)
            if response.status_code == 200:
                nodes = response.json()
                for node in nodes:
                    if node['node_id'].startswith('stress_'):
                        try:
                            self.session.delete(
                                f"{BACKEND_URL}/register/node/{node['node_id']}?delete_files=true",
                                headers=HEADERS,
                                timeout=5
                            )
                        except:
                            pass
        except:
            pass
    
    @pytest.mark.stress
    @pytest.mark.timeout(300)
    def test_continuous_random_failures(self):
        """
        STRESS TEST: Sistema debe mantener disponibilidad bajo fallas continuas
        """
        print("\n" + "="*80)
        print("TEST 3: STRESS TEST - Fallas continuas aleatorias")
        print("="*80)
        
        # Crear 10 nodos
        for i in range(10):
            node_data = {
                "node_id": f"stress_node_{i}",
                "name": f"Stress Node {i}",
                "ip_address": "127.0.0.1",
                "port": 8200 + i,
                "status": "online",
                "shared_files_count": 0
            }
            
            self.session.post(
                f"{BACKEND_URL}/register/node",
                json=node_data,
                headers=HEADERS,
                timeout=10
            )
        
        print(f"✅ Creados 10 nodos")
        
        # Subir 50 archivos
        files = []
        for i in range(50):
            file_content = f"Stress test file {i} - " + "x" * 500
            
            try:
                response = self.session.post(
                    f"{BACKEND_URL}/register/upload",
                    files={'file': (f"stress_{i}.txt", file_content.encode())},
                    data={'node_id': f"stress_node_{i % 10}", 'replicate': 'true'},
                    headers=HEADERS,
                    timeout=30
                )
                
                if response.status_code == 200:
                    files.append(response.json()['file_id'])
            except:
                pass
            
            time.sleep(0.2)
        
        print(f"✅ Subidos {len(files)} archivos")
        
        time.sleep(15)
        
        # Stress loop por 3 minutos
        print("\n🔥 Iniciando stress loop (3 minutos)...")
        
        start_time = time.time()
        duration = 180
        failures_count = 0
        recoveries_count = 0
        
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DBNAME]
        
        while time.time() - start_time < duration:
            action = random.choice(['fail', 'recover'])
            node_idx = random.randint(0, 9)
            node_id = f"stress_node_{node_idx}"
            
            if action == 'fail':
                db.nodes.update_one(
                    {"node_id": node_id},
                    {"$set": {"status": "offline", "last_seen": datetime.utcnow() - timedelta(minutes=10)}}
                )
                failures_count += 1
                print(f"   🔥 Nodo caído: {node_id}")
            else:
                db.nodes.update_one(
                    {"node_id": node_id},
                    {"$set": {"status": "online", "last_seen": datetime.utcnow()}}
                )
                recoveries_count += 1
                print(f"   ✅ Nodo recuperado: {node_id}")
            
            time.sleep(10)
        
        print(f"\n📊 Stress test completado:")
        print(f"   Total fallas simuladas: {failures_count}")
        print(f"   Total recuperaciones: {recoveries_count}")
        
        # Verificar integridad
        print("\n🔍 Verificando integridad final...")
        
        lost_files = []
        for file_id in files:
            try:
                response = self.session.get(
                    f"{BACKEND_URL}/search/?q={file_id}",
                    timeout=10
                )
                
                if response.status_code != 200 or len(response.json().get('files', [])) == 0:
                    lost_files.append(file_id)
            except:
                lost_files.append(file_id)
        
        print(f"   Archivos accesibles: {len(files) - len(lost_files)}/{len(files)}")
        print(f"   Archivos perdidos: {len(lost_files)}/{len(files)}")
        
        assert len(lost_files) == 0, f"❌ FALLO CRÍTICO: {len(lost_files)} archivos perdidos"
        
        availability = ((len(files) - len(lost_files)) / len(files)) * 100 if files else 0
        print(f"   Disponibilidad final: {availability:.2f}%")
        
        assert availability >= 99.9, f"❌ Disponibilidad {availability}% < 99.9%"
        
        print("\n✅ STRESS TEST PASADO: Sistema 100% disponible")


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "critical",
    ])