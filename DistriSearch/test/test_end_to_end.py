from fastapi.testclient import TestClient
import os
import sys
import tempfile
import pathlib
from unittest.mock import patch

# Alinear con otros tests: añadir backend al sys.path e importar main
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'backend'))
if BACKEND_ROOT not in sys.path:
	sys.path.insert(0, BACKEND_ROOT)
from main import app


client = TestClient(app)


def test_e2e_centralized_flow(tmp_path, monkeypatch):
	# Preparar carpeta central temporal con dos archivos (mismo contenido, distinto nombre)
	central_dir = tmp_path / "central"
	central_dir.mkdir(parents=True, exist_ok=True)
	(central_dir / "doc1.txt").write_text("contenido unico e2e_central")
	(central_dir / "doc2.txt").write_text("contenido unico e2e_central")

	# Apuntar la variable de entorno y escanear
	monkeypatch.setenv("CENTRAL_SHARED_FOLDER", str(central_dir))
	resp = client.post("/central/scan", json={"folder": str(central_dir)})
	assert resp.status_code == 200, resp.text
	data = resp.json()
	assert data["indexed_files"] == 2

	# Buscar por el contenido
	search = client.get("/search/", params={"q": "contenido", "max_results": 10})
	assert search.status_code == 200, search.text
	sdata = search.json()
	names = [f["name"] for f in sdata["files"]]
	assert "doc1.txt" in names and "doc2.txt" in names

	# Descargar específicamente uno de los que acabamos de indexar
	first = next(f for f in sdata["files"] if f["name"] in ("doc1.txt", "doc2.txt"))
	dl_req = client.post("/download/", json={"file_id": first["file_id"]})
	assert dl_req.status_code == 200, dl_req.text
	dl_url = dl_req.json()["download_url"]
	file_resp = client.get(dl_url)
	assert file_resp.status_code == 200
	assert b"e2e_central" in file_resp.content


def test_e2e_distributed_flow(tmp_path, monkeypatch):
	# Configurar API key para usar endpoints protegidos
	monkeypatch.setenv("ADMIN_API_KEY", "testkey")
	headers = {"X-API-KEY": "testkey"}

	# Preparar carpetas de nodos
	n1 = tmp_path / "n1"
	n2 = tmp_path / "n2"
	n1.mkdir(parents=True, exist_ok=True)
	n2.mkdir(parents=True, exist_ok=True)

	# Crear archivos (con un término único en cada uno y uno compartido por ambos)
	(n1 / "remoto1.txt").write_text("palabra_unica_n1 e2e_distribuido")
	(n2 / "remoto2.txt").write_text("palabra_unica_n2 e2e_distribuido")
	shared_content = "contenido_compartido e2e_distribuido"
	(n1 / "compartidoA.txt").write_text(shared_content)
	(n2 / "compartidoB.txt").write_text(shared_content)

	# Registrar nodos vía API
	for node_id, port in (("n1", 9001), ("n2", 9002)):
		node_payload = {
			"node_id": node_id,
			"name": f"Nodo {node_id.upper()}",
			"ip_address": "127.0.0.1",
			"port": port,
			"status": "online",
			"shared_files_count": 0,
		}
		r = client.post("/register/node", json=node_payload, headers=headers)
		assert r.status_code == 200, r.text

	# Montar carpetas y escanear/importar
	r = client.post("/register/node/n1/mount", json={"folder": str(n1)}, headers=headers)
	assert r.status_code == 200, r.text
	r = client.post("/register/node/n2/mount", json={"folder": str(n2)}, headers=headers)
	assert r.status_code == 200, r.text

	r = client.post("/register/node/n1/scan-import", headers=headers)
	assert r.status_code == 200, r.text
	r = client.post("/register/node/n2/scan-import", headers=headers)
	assert r.status_code == 200, r.text

	# Buscar un término presente en ambos nodos
	search = client.get("/search/", params={"q": "distribuido", "max_results": 50})
	assert search.status_code == 200, search.text
	sdata = search.json()
	files = sdata["files"]
	# Verificar que aparecen archivos de ambos nodos
	node_ids = {f["node_id"] for f in files}
	assert {"n1", "n2"}.issubset(node_ids)

	# Probar descarga de un archivo remoto mockeando la respuesta del nodo
	# Elegimos un resultado de n1
	target = next(f for f in files if f["node_id"] == "n1")

	class DummyResp:
		status_code = 200
		headers = {
			"content-disposition": 'attachment; filename="remoto1.txt"',
			"content-type": "application/octet-stream",
		}
		content = b"contenido remoto e2e"

	async def fake_get(self, url):
		assert ":9001/" in url  # debe apuntar al puerto del nodo n1
		return DummyResp()

	with patch("httpx.AsyncClient.get", new=fake_get):
		dl_req = client.post("/download/", json={"file_id": target["file_id"]})
		assert dl_req.status_code == 200, dl_req.text
		dl_url = dl_req.json()["download_url"]
		file_resp = client.get(dl_url)
		assert file_resp.status_code == 200
		assert file_resp.content == DummyResp.content

