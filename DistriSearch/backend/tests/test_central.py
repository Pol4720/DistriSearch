from fastapi.testclient import TestClient
from main import app
import os
import tempfile
import pathlib

client = TestClient(app)

def test_central_scan_creates_index():
    # Crear carpeta temporal con un archivo
    with tempfile.TemporaryDirectory() as tmp:
        file_path = pathlib.Path(tmp) / "demo.txt"
        file_path.write_text("hola central mode")
        # Llamar endpoint
        resp = client.post("/central/scan", json={"folder": str(tmp)})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["indexed_files"] == 1
        # Buscar el archivo por nombre
        search_resp = client.get("/search/", params={"q": "demo", "max_results": 10})
        assert search_resp.status_code == 200, search_resp.text
        results = search_resp.json()
        assert results["total_count"] >= 1
        names = [f["name"] for f in results["files"]]
        assert "demo.txt" in names
