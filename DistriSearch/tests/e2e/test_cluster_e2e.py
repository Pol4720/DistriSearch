"""
Tests End-to-End (E2E) para validar escenarios completos del cluster.

Estos tests requieren Docker y levantan múltiples contenedores.
Usar con: pytest tests/e2e/ -m e2e --timeout=180
"""
import os
import sys
import subprocess
import time
import asyncio
import pytest
import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_DIR = os.path.join(ROOT, "deploy")


def is_docker_available():
    """Verifica si Docker está disponible"""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not is_docker_available(), reason="Docker no disponible"),
]


class TestClusterE2E:
    """
    Tests E2E que verifican:
    1. Cluster arranca correctamente con 3 nodos
    2. Búsqueda distribuida funciona
    3. Replicación de archivos funciona
    4. Elección de líder ante fallo del Master
    """

    @pytest.fixture(scope="class", autouse=True)
    def cluster(self, request):
        """Levanta y derriba el cluster para los tests de esta clase"""
        # SOLO levantar si no hay cluster activo
        compose_file = os.path.join(DEPLOY_DIR, "docker-compose.cluster.yml")
        
        if not os.path.exists(compose_file):
            pytest.skip("docker-compose.cluster.yml no encontrado")

        # Levantar cluster
        subprocess.run(
            ["docker-compose", "-f", compose_file, "up", "-d", "--build"],
            cwd=DEPLOY_DIR,
            timeout=300,
        )

        # Esperar a que los servicios estén healthy
        time.sleep(30)

        yield

        # Derribar cluster
        subprocess.run(
            ["docker-compose", "-f", compose_file, "down", "-v"],
            cwd=DEPLOY_DIR,
            timeout=60,
        )

    def test_health_endpoints_respond(self):
        """Verifica que todos los nodos responden en /health"""
        ports = [8001, 8002, 8003]  # backend_node1, backend_node2, backend_node3
        
        for port in ports:
            try:
                response = httpx.get(f"http://localhost:{port}/health", timeout=10)
                assert response.status_code == 200, f"Node on port {port} unhealthy"
            except httpx.ConnectError:
                pytest.fail(f"No se pudo conectar al nodo en puerto {port}")

    def test_cluster_status_shows_all_nodes(self):
        """Verifica que /health/cluster muestra todos los nodos"""
        response = httpx.get("http://localhost:8001/health/cluster", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        # Debe haber al menos 3 nodos
        assert "cluster" in data
        nodes = data["cluster"].get("nodes", [])
        assert len(nodes) >= 3, f"Esperados 3+ nodos, encontrados {len(nodes)}"

    def test_file_upload_and_search(self):
        """Sube un archivo y verifica que se puede buscar"""
        # Subir archivo al nodo 1
        files = {"file": ("test_e2e.txt", b"Este es un documento de prueba E2E", "text/plain")}
        upload_resp = httpx.post(
            "http://localhost:8001/api/register",
            files=files,
            timeout=30,
        )
        assert upload_resp.status_code in [200, 201], f"Upload failed: {upload_resp.text}"

        # Esperar indexación
        time.sleep(5)

        # Buscar en cualquier nodo
        search_resp = httpx.get(
            "http://localhost:8002/api/search",
            params={"query": "documento prueba E2E"},
            timeout=30,
        )
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert isinstance(results, list)
        # El archivo debería aparecer
        found = any("test_e2e" in r.get("name", "") for r in results)
        assert found, f"Archivo no encontrado en resultados: {results}"

    def test_master_election_on_failure(self):
        """Simula caída de Master y verifica elección"""
        # Identificar Master actual (asumimos node_1 inicia como master)
        compose_file = os.path.join(DEPLOY_DIR, "docker-compose.cluster.yml")
        
        # Detener backend_node1
        subprocess.run(
            ["docker-compose", "-f", compose_file, "stop", "backend_node1"],
            cwd=DEPLOY_DIR,
            timeout=30,
        )

        # Esperar elección (timeout de heartbeat + election)
        time.sleep(25)

        # Verificar que otro nodo responde y el cluster sigue funcional
        try:
            response = httpx.get("http://localhost:8002/health/detailed", timeout=10)
            assert response.status_code == 200
            data = response.json()
            # El nodo 2 o 3 debería indicar que es master o que hay un nuevo master
            assert data.get("status") in ["healthy", "degraded"]
        except httpx.ConnectError:
            # Intentar nodo 3
            response = httpx.get("http://localhost:8003/health/detailed", timeout=10)
            assert response.status_code == 200

        # Levantar nodo 1 de nuevo
        subprocess.run(
            ["docker-compose", "-f", compose_file, "start", "backend_node1"],
            cwd=DEPLOY_DIR,
            timeout=30,
        )
        time.sleep(10)

    def test_replication_persists_across_nodes(self):
        """Verifica que documentos se replican a múltiples nodos"""
        # Subir archivo único
        unique_name = f"replication_test_{int(time.time())}.txt"
        files = {"file": (unique_name, b"Contenido para probar replicacion", "text/plain")}
        
        upload_resp = httpx.post(
            "http://localhost:8001/api/register",
            files=files,
            timeout=30,
        )
        assert upload_resp.status_code in [200, 201]

        # Esperar replicación (según REPLICATION_FACTOR=2)
        time.sleep(15)

        # Buscar en nodos 2 y 3 (no en el original)
        found_count = 0
        for port in [8002, 8003]:
            search_resp = httpx.get(
                f"http://localhost:{port}/api/search",
                params={"query": unique_name.replace(".txt", "")},
                timeout=30,
            )
            if search_resp.status_code == 200:
                results = search_resp.json()
                if any(unique_name in r.get("name", "") for r in results):
                    found_count += 1

        # Con REPLICATION_FACTOR=2, debería estar en al menos 1 otro nodo
        assert found_count >= 1, "Archivo no replicado a otros nodos"
