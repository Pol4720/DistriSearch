import os
import tempfile
import sqlite3
import types
from fastapi.testclient import TestClient
from unittest.mock import patch

import DistriSearch.backend.database_viejo as database_viejo
from main import app
from models import FileMeta, NodeInfo, NodeStatus
from services.central_service import CENTRAL_NODE_ID, _instance_id

client = TestClient(app)

def _register_central_file(tmpdir: str) -> FileMeta:
	# Crear archivo
	path = os.path.join(tmpdir, 'test.txt')
	with open(path, 'w', encoding='utf-8') as f:
		f.write('contenido de prueba')
	# ID de instancia basado en nodo+path relativo
	rel_path = os.path.basename(path)
	file_id = _instance_id(CENTRAL_NODE_ID, rel_path)
	# Registrar nodo central y archivo
	node = NodeInfo(
		node_id=CENTRAL_NODE_ID,
		name='Central',
		ip_address='localhost',
		port=8000,
		status=NodeStatus.ONLINE,
		shared_files_count=1
	)
	database_viejo.register_node(node)
	fm = FileMeta(
		file_id=file_id,
		name='test.txt',
		path='test.txt',
		size=os.path.getsize(path),
		mime_type='text/plain',
		type='document',
		node_id=CENTRAL_NODE_ID,
		content_hash=None,
	)
	database_viejo.register_file(fm)
	return fm

def test_get_download_url_central(tmp_path, monkeypatch):
	# Asegurar carpeta central temporal
	monkeypatch.setenv('CENTRAL_SHARED_FOLDER', str(tmp_path))
	fm = _register_central_file(str(tmp_path))
	resp = client.post('/download/', json={'file_id': fm.file_id})
	assert resp.status_code == 200
	data = resp.json()
	assert data['download_url'].endswith(f'/download/file/{fm.file_id}')
	# Descargar vía proxy
	resp2 = client.get(data['download_url'])
	assert resp2.status_code == 200
	assert resp2.content.startswith(b'contenido')

def test_download_proxy_distributed(monkeypatch, tmp_path):
	# Crear archivo en carpeta externa simulada del nodo
	file_content = b'archivo remoto'
	import hashlib
	content_sha = hashlib.sha256(file_content).hexdigest()

	# Registrar nodo distribuido y archivo
	node = NodeInfo(
		node_id='n1',
		name='Nodo 1',
		ip_address='127.0.0.1',
		port=9000,
		status=NodeStatus.ONLINE,
		shared_files_count=1
	)
	database_viejo.register_node(node)
	fm = FileMeta(
		file_id=_instance_id('n1', 'remoto.bin'),
		name='remoto.bin',
		path='remoto.bin',
		size=len(file_content),
		mime_type='application/octet-stream',
		type='other',
		node_id='n1',
		content_hash=content_sha
	)
	database_viejo.register_file(fm)

	# Mockear httpx.AsyncClient.get para devolver contenido simulado
	class DummyResp:
		status_code = 200
		headers = {'content-disposition': 'attachment; filename="remoto.bin"', 'content-type': 'application/octet-stream'}
		content = file_content

	async def fake_get(self, url):
		assert str(9000) in url
		return DummyResp()

	with patch('httpx.AsyncClient.get', new=fake_get):
		r = client.post('/download/', json={'file_id': fm.file_id})
		assert r.status_code == 200
		url = r.json()['download_url']
		r2 = client.get(url)
		assert r2.status_code == 200
		assert r2.content == file_content

def test_download_not_found():
	r = client.post('/download/', json={'file_id': 'noexiste'})
	assert r.status_code == 404
