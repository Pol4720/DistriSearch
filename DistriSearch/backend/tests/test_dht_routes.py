"""
Tests de integración para los endpoints DHT
"""
import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Añadir path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app


@pytest.fixture
def client():
    """Cliente de test para FastAPI"""
    return TestClient(app)


@pytest.fixture
def mock_dht_service():
    """Mock del servicio DHT"""
    with patch('routes.dht.dht_service') as mock:
        mock.service = Mock()
        yield mock


class TestDHTRoutes:
    """Tests de los endpoints DHT"""
    
    def test_start_endpoint(self, client, mock_dht_service):
        """Test: POST /dht/start"""
        mock_dht_service.service.start.return_value = None
        mock_dht_service.service.mode = "external"
        
        response = client.post("/dht/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["mode"] == "external"
        mock_dht_service.service.start.assert_called_once()
    
    def test_start_endpoint_error(self, client, mock_dht_service):
        """Test: Error al iniciar DHT"""
        mock_dht_service.service.start.side_effect = Exception("Port in use")
        
        response = client.post("/dht/start")
        
        assert response.status_code == 500
        assert "Port in use" in response.json()["detail"]
    
    def test_join_endpoint(self, client, mock_dht_service):
        """Test: POST /dht/join"""
        mock_dht_service.service.join.return_value = "Unión exitosa"
        
        response = client.post("/dht/join?seed_ip=192.168.1.10&seed_port=2000")
        
        assert response.status_code == 200
        data = response.json()
        assert "Unión exitosa" in data["result"]
        mock_dht_service.service.join.assert_called_once_with("192.168.1.10", 2000)
    
    def test_join_endpoint_no_port(self, client, mock_dht_service):
        """Test: Join sin especificar puerto (usa default)"""
        mock_dht_service.service.join.return_value = "OK"
        
        response = client.post("/dht/join?seed_ip=192.168.1.10")
        
        assert response.status_code == 200
        mock_dht_service.service.join.assert_called_once_with("192.168.1.10", None)
    
    def test_upload_endpoint(self, client, mock_dht_service):
        """Test: POST /dht/upload"""
        mock_dht_service.service.upload.return_value = "Archivo subido"
        
        response = client.post("/dht/upload?filename=test.txt&data=contenido")
        
        assert response.status_code == 200
        data = response.json()
        assert "Archivo subido" in data["result"]
        mock_dht_service.service.upload.assert_called_once_with("test.txt", "contenido")
    
    def test_upload_endpoint_special_chars(self, client, mock_dht_service):
        """Test: Upload con caracteres especiales"""
        mock_dht_service.service.upload.return_value = "OK"
        
        response = client.post("/dht/upload?filename=ñoño.txt&data=áéíóú")
        
        assert response.status_code == 200
    
    def test_download_endpoint(self, client, mock_dht_service):
        """Test: POST /dht/download"""
        mock_dht_service.service.download.return_value = "contenido del archivo"
        
        response = client.post("/dht/download?filename=test.txt")
        
        assert response.status_code == 200
        data = response.json()
        assert "contenido del archivo" in data["result"]
        mock_dht_service.service.download.assert_called_once_with("test.txt")
    
    def test_download_endpoint_not_found(self, client, mock_dht_service):
        """Test: Download de archivo inexistente"""
        mock_dht_service.service.download.side_effect = Exception("File not found")
        
        response = client.post("/dht/download?filename=noexiste.txt")
        
        assert response.status_code == 500
    
    def test_finger_endpoint(self, client, mock_dht_service):
        """Test: GET /dht/finger"""
        mock_finger = {
            "123": [456, ["192.168.1.10", 2000]],
            "234": [567, ["192.168.1.11", 2000]]
        }
        mock_dht_service.service.finger_table.return_value = mock_finger
        
        response = client.get("/dht/finger")
        
        assert response.status_code == 200
        data = response.json()
        assert "finger" in data
        assert data["finger"] == mock_finger
    
    def test_sucpred_endpoint(self, client, mock_dht_service):
        """Test: GET /dht/sucpred"""
        mock_sucpred = {
            "id": 789,
            "sucesor": ["192.168.1.11", 2000],
            "predecesor": ["192.168.1.9", 2000]
        }
        mock_dht_service.service.suc_pred.return_value = mock_sucpred
        
        response = client.get("/dht/sucpred")
        
        assert response.status_code == 200
        data = response.json()
        assert "sucpred" in data
        assert data["sucpred"] == mock_sucpred
    
    def test_all_endpoints_exist(self, client):
        """Test: Todos los endpoints DHT están registrados"""
        routes = [route.path for route in app.routes]
        
        assert "/dht/start" in routes
        assert "/dht/join" in routes
        assert "/dht/upload" in routes
        assert "/dht/download" in routes
        assert "/dht/finger" in routes
        assert "/dht/sucpred" in routes


class TestDHTRoutesValidation:
    """Tests de validación de parámetros"""
    
    def test_join_missing_seed_ip(self, client):
        """Test: Join sin seed_ip debe fallar"""
        # FastAPI debería rechazar la request
        response = client.post("/dht/join")
        # Puede ser 422 (validation error) o 500 dependiendo del handling
        assert response.status_code in [422, 500]
    
    def test_upload_missing_params(self, client):
        """Test: Upload sin parámetros debe fallar"""
        response = client.post("/dht/upload")
        assert response.status_code in [422, 500]
    
    def test_download_missing_filename(self, client):
        """Test: Download sin filename debe fallar"""
        response = client.post("/dht/download")
        assert response.status_code in [422, 500]


class TestDHTRoutesIntegration:
    """Tests de integración más complejos"""
    
    def test_workflow_start_join_upload_download(self, client, mock_dht_service):
        """Test: Flujo completo start -> join -> upload -> download"""
        mock_dht_service.service.mode = "inproc"
        mock_dht_service.service.start.return_value = None
        mock_dht_service.service.join.return_value = "Joined"
        mock_dht_service.service.upload.return_value = "Uploaded"
        mock_dht_service.service.download.return_value = "file content"
        
        # 1. Start
        resp1 = client.post("/dht/start")
        assert resp1.status_code == 200
        
        # 2. Join
        resp2 = client.post("/dht/join?seed_ip=192.168.1.10&seed_port=2000")
        assert resp2.status_code == 200
        
        # 3. Upload
        resp3 = client.post("/dht/upload?filename=test.txt&data=hello")
        assert resp3.status_code == 200
        
        # 4. Download
        resp4 = client.post("/dht/download?filename=test.txt")
        assert resp4.status_code == 200
        assert "file content" in resp4.json()["result"]
    
    def test_concurrent_uploads(self, client, mock_dht_service):
        """Test: Múltiples uploads concurrentes"""
        mock_dht_service.service.upload.return_value = "OK"
        
        responses = []
        for i in range(10):
            resp = client.post(f"/dht/upload?filename=file{i}.txt&data=content{i}")
            responses.append(resp)
        
        # Todos deben ser exitosos
        assert all(r.status_code == 200 for r in responses)
    
    def test_state_check_endpoints(self, client, mock_dht_service):
        """Test: Consultar estado múltiples veces"""
        mock_dht_service.service.finger_table.return_value = {}
        mock_dht_service.service.suc_pred.return_value = {"id": 123}
        
        # Finger table
        resp1 = client.get("/dht/finger")
        assert resp1.status_code == 200
        
        # Suc/Pred
        resp2 = client.get("/dht/sucpred")
        assert resp2.status_code == 200
        
        # Ambos deben ser idempotentes
        resp3 = client.get("/dht/finger")
        assert resp3.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
