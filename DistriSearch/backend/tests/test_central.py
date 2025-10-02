from fastapi.testclient import TestClient
import sys, os
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
from main import app
import tempfile
import pathlib
from models import FileMeta, NodeInfo, FileType, NodeStatus
import database
from datetime import datetime

client = TestClient(app)

def test_central_scan_creates_index():
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "demo.txt").write_text("hola central mode")
        resp = client.post("/central/scan", json={"folder": str(tmp)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed_files"] == 1
        search_resp = client.get("/search/", params={"q": "demo", "max_results": 10})
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert any(f["name"] == "demo.txt" for f in results["files"])

def test_central_rescan_updates_count():
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        (p / "a.txt").write_text("a")
        client.post("/central/scan", json={"folder": str(tmp)})
        (p / "b.txt").write_text("b")
        resp = client.post("/central/scan", json={"folder": str(tmp)})
        data = resp.json()
        assert data["indexed_files"] == 2

def test_central_and_distributed_coexist():
    # Simular un nodo distribuido registrando directamente (sin agente real)
    node = NodeInfo(
        node_id="node1",
        name="Nodo Distribuido",
        ip_address="127.0.0.1",
        port=9000,
        status=NodeStatus.ONLINE,
        shared_files_count=1,
    )
    database.register_node(node)
    file_meta = FileMeta(
        file_id="dummyhash123",
        name="recurso_distribuido.txt",
        path="recurso_distribuido.txt",
        size=5,
        mime_type="text/plain",
        type=FileType.DOCUMENT,
        node_id="node1",
        last_updated=datetime.now()
    )
    database.register_file(file_meta)
    # Hacer un scan central para asegurar coexistencia
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "central.txt").write_text("central")
        client.post("/central/scan", json={"folder": str(tmp)})
    # Verificar que ambos aparecen en estadísticas de modo
    mode_resp = client.get("/central/mode")
    assert mode_resp.status_code == 200
    mode = mode_resp.json()
    assert mode["centralized"] is True
    assert mode["distributed"] is True
