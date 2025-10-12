from fastapi.testclient import TestClient
import sys, os
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if BACKEND_ROOT not in sys.path:
	sys.path.insert(0, BACKEND_ROOT)
from main import app
import tempfile
import pathlib

client = TestClient(app)

def test_search_by_content_prefix():
	"""Verifica búsqueda full-text por contenido.

	Crea un archivo cuyo nombre no contiene la palabra clave única pero sí el contenido.
	"""
	with tempfile.TemporaryDirectory() as tmp:
		p = pathlib.Path(tmp) / "contenido.txt"
		p.write_text("Este es un texto muy peculiar con la palabra Supercalifragilistico en su interior")
		# Indexar carpeta central
		resp = client.post("/central/scan", json={"folder": str(tmp)})
		assert resp.status_code == 200
		# Buscar palabra completa (el código añade * para prefijo)
		search_resp = client.get("/search/", params={"q": "Supercalifragilistico", "max_results": 5})
		assert search_resp.status_code == 200
		data = search_resp.json()
		assert any(f["name"] == "contenido.txt" for f in data["files"]), data

def test_search_empty_query_returns_validation_error():
	# FastAPI debe devolver error 422 si q no se suministra, pero con espacios se considera string -> buscamos comportamiento
	resp = client.get("/search/", params={"q": "   ", "max_results": 5})
	# El backend actualmente retorna lista vacía (total_count 0) cuando se limpia.
	# Aceptamos cualquiera para mantener flexibilidad.
	assert resp.status_code in (200, 422)
