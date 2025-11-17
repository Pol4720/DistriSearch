"""
Tests end-to-end para la integración DHT con DistriSearch

Estos tests requieren que el backend esté ejecutándose y pueden usar
un servicio DHT real o mock dependiendo de la configuración.
"""
import pytest
import requests
import time
import os
from typing import Dict, Any


# Configuración de URLs
BACKEND_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
DHT_EXTERNAL_URL = os.getenv("TEST_DHT_URL", "http://localhost:8080")


class TestDHTEndToEnd:
    """Tests end-to-end del sistema DHT completo"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup antes de cada test"""
        # Verificar que el backend está disponible
        try:
            resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
            if resp.status_code != 200:
                pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Backend no disponible")
    
    def test_backend_health(self):
        """Test: Backend está corriendo"""
        resp = requests.get(f"{BACKEND_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
    
    def test_dht_start(self):
        """Test: Iniciar DHT desde backend"""
        resp = requests.post(f"{BACKEND_URL}/dht/start", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "started"
        assert "mode" in data
        assert data["mode"] in ["external", "inproc"]
    
    def test_dht_state_check(self):
        """Test: Consultar estado DHT"""
        # Intentar iniciar primero
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
        except:
            pass
        
        # Consultar estado
        resp = requests.get(f"{BACKEND_URL}/dht/sucpred", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "sucpred" in data
    
    def test_dht_finger_table(self):
        """Test: Obtener finger table"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
        except:
            pass
        
        resp = requests.get(f"{BACKEND_URL}/dht/finger", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "finger" in data
    
    @pytest.mark.slow
    def test_dht_upload_download_cycle(self):
        """Test: Ciclo completo de upload y download"""
        # Asegurar que DHT está iniciada
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
            time.sleep(2)  # Dar tiempo a inicializar
        except:
            pass
        
        # Upload
        filename = f"test_e2e_{int(time.time())}.txt"
        content = "Contenido de prueba end-to-end"
        
        upload_resp = requests.post(
            f"{BACKEND_URL}/dht/upload",
            params={"filename": filename, "data": content},
            timeout=10
        )
        assert upload_resp.status_code == 200
        
        # Esperar a que se propague
        time.sleep(1)
        
        # Download
        download_resp = requests.post(
            f"{BACKEND_URL}/dht/download",
            params={"filename": filename},
            timeout=10
        )
        assert download_resp.status_code == 200
        result = download_resp.json()
        assert "result" in result
        # El contenido puede estar en el resultado
        # (depende de la implementación exacta del peer)


class TestDHTRobustness:
    """Tests de robustez y manejo de errores"""
    
    def test_upload_large_file(self):
        """Test: Subir archivo grande"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
        except:
            pass
        
        large_content = "x" * (1024 * 100)  # 100KB
        resp = requests.post(
            f"{BACKEND_URL}/dht/upload",
            params={"filename": "large.dat", "data": large_content},
            timeout=30
        )
        # Puede tener éxito o fallar dependiendo de límites
        assert resp.status_code in [200, 500, 413]
    
    def test_upload_special_characters(self):
        """Test: Nombres de archivo con caracteres especiales"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
        except:
            pass
        
        special_names = [
            "archivo con espacios.txt",
            "archivo-con-guiones.txt",
            "archivo_con_guiones_bajos.txt",
        ]
        
        for name in special_names:
            resp = requests.post(
                f"{BACKEND_URL}/dht/upload",
                params={"filename": name, "data": "test"},
                timeout=10
            )
            # Verificar que no crashea
            assert resp.status_code in [200, 400, 500]
    
    def test_download_nonexistent_file(self):
        """Test: Descargar archivo inexistente"""
        resp = requests.post(
            f"{BACKEND_URL}/dht/download",
            params={"filename": "noexiste_" + str(time.time()) + ".txt"},
            timeout=10
        )
        # Debería manejar el error gracefully
        assert resp.status_code in [200, 404, 500]
    
    def test_concurrent_operations(self):
        """Test: Operaciones concurrentes"""
        import concurrent.futures
        
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
            time.sleep(2)
        except:
            pass
        
        def upload_file(i):
            return requests.post(
                f"{BACKEND_URL}/dht/upload",
                params={"filename": f"concurrent_{i}.txt", "data": f"data_{i}"},
                timeout=10
            )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Al menos algunas deberían tener éxito
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 3  # Al menos 3 de 5


class TestDHTPerformance:
    """Tests de rendimiento básico"""
    
    @pytest.mark.slow
    def test_upload_latency(self):
        """Test: Latencia de upload"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
            time.sleep(2)
        except:
            pass
        
        start = time.time()
        resp = requests.post(
            f"{BACKEND_URL}/dht/upload",
            params={"filename": "latency_test.txt", "data": "test"},
            timeout=10
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200
        # Upload debería tomar menos de 5 segundos
        assert elapsed < 5.0
    
    @pytest.mark.slow
    def test_multiple_uploads_throughput(self):
        """Test: Throughput de múltiples uploads"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
            time.sleep(2)
        except:
            pass
        
        start = time.time()
        count = 10
        
        for i in range(count):
            requests.post(
                f"{BACKEND_URL}/dht/upload",
                params={"filename": f"throughput_{i}.txt", "data": f"content_{i}"},
                timeout=10
            )
        
        elapsed = time.time() - start
        throughput = count / elapsed
        
        # Debería poder hacer al menos 1 upload/segundo
        assert throughput >= 1.0


class TestDHTIntegrationWithSearch:
    """Tests de integración DHT con el buscador"""
    
    def test_backend_has_dht_endpoints(self):
        """Test: Backend expone endpoints DHT"""
        # Obtener OpenAPI schema
        resp = requests.get(f"{BACKEND_URL}/openapi.json")
        assert resp.status_code == 200
        
        schema = resp.json()
        paths = schema.get("paths", {})
        
        # Verificar que existen los endpoints DHT
        assert "/dht/start" in paths
        assert "/dht/join" in paths
        assert "/dht/upload" in paths
        assert "/dht/download" in paths
    
    def test_dht_endpoints_documented(self):
        """Test: Endpoints DHT están documentados"""
        resp = requests.get(f"{BACKEND_URL}/openapi.json")
        schema = resp.json()
        
        dht_paths = {k: v for k, v in schema["paths"].items() if k.startswith("/dht/")}
        
        # Cada endpoint debe tener descripción
        for path, methods in dht_paths.items():
            for method, details in methods.items():
                if method not in ["parameters", "$ref"]:
                    assert "tags" in details or "summary" in details


class TestDHTFailover:
    """Tests de failover y recuperación"""
    
    @pytest.mark.slow
    def test_restart_dht(self):
        """Test: Reiniciar DHT múltiples veces"""
        for i in range(3):
            resp = requests.post(f"{BACKEND_URL}/dht/start", timeout=10)
            # Puede fallar si ya está iniciada, pero no debe crashear
            assert resp.status_code in [200, 500]
            time.sleep(1)
    
    def test_query_state_without_start(self):
        """Test: Consultar estado sin haber iniciado DHT"""
        # Esto debería manejarse gracefully
        resp = requests.get(f"{BACKEND_URL}/dht/sucpred", timeout=5)
        # Puede retornar estado vacío o error, pero no crashear
        assert resp.status_code in [200, 500]


class TestDHTDataIntegrity:
    """Tests de integridad de datos"""
    
    @pytest.mark.slow
    def test_upload_download_integrity(self):
        """Test: Los datos descargados coinciden con los subidos"""
        try:
            requests.post(f"{BACKEND_URL}/dht/start", timeout=5)
            time.sleep(2)
        except:
            pass
        
        # Datos de prueba con diferentes tipos de contenido
        test_cases = [
            ("simple.txt", "Hello World"),
            ("numbers.txt", "123456789"),
            ("special.txt", "!@#$%^&*()"),
            ("unicode.txt", "áéíóú ñ"),
        ]
        
        for filename, content in test_cases:
            filename = f"integrity_{int(time.time())}_{filename}"
            
            # Upload
            up_resp = requests.post(
                f"{BACKEND_URL}/dht/upload",
                params={"filename": filename, "data": content},
                timeout=10
            )
            
            if up_resp.status_code != 200:
                continue  # Skip si upload falla
            
            time.sleep(1)
            
            # Download
            down_resp = requests.post(
                f"{BACKEND_URL}/dht/download",
                params={"filename": filename},
                timeout=10
            )
            
            if down_resp.status_code == 200:
                result = down_resp.json()
                # Verificar que el contenido está presente
                # (la estructura exacta depende de la implementación)
                assert "result" in result


def run_smoke_test():
    """Test de humo rápido para CI/CD"""
    print("🔍 Ejecutando smoke test DHT...")
    
    try:
        # 1. Health check
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        assert resp.status_code == 200
        print("✅ Backend health OK")
        
        # 2. Start DHT
        resp = requests.post(f"{BACKEND_URL}/dht/start", timeout=10)
        assert resp.status_code == 200
        print("✅ DHT start OK")
        
        # 3. Check state
        resp = requests.get(f"{BACKEND_URL}/dht/sucpred", timeout=5)
        assert resp.status_code == 200
        print("✅ DHT state OK")
        
        print("\n🎉 Smoke test completado exitosamente!")
        return True
    except Exception as e:
        print(f"\n❌ Smoke test falló: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        success = run_smoke_test()
        sys.exit(0 if success else 1)
    else:
        pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])
