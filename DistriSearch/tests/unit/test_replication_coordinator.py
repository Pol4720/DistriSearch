import sys
import os

# Setup path para imports directos (evitar __init__.py que tiene imports relativos)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import asyncio

import httpx
import numpy as np
import pytest

# Importar directamente sin pasar por master/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "replication_coordinator",
    os.path.join(ROOT, "master", "replication_coordinator.py")
)
repl_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repl_module)
ReplicationCoordinator = repl_module.ReplicationCoordinator
ReplicationStatus = repl_module.ReplicationStatus


class DummyLocationIndex:
    def __init__(self, choices):
        self.choices = choices

    def select_replica_nodes(self, source_node, document_embedding, replication_factor):
        return [c for c in self.choices if c != source_node][:replication_factor]


class DummyResponse:
    def __init__(self, status_code=200, content=b"payload", headers=None):
        self.status_code = status_code
        self.content = content
        self._headers = headers or {}

    @property
    def headers(self):
        return self._headers

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = {"get": [], "post": []}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        self.calls["get"].append(url)
        return DummyResponse(headers={"content-disposition": "file.txt"})

    async def post(self, url, files=None, data=None):
        self.calls["post"].append((url, files, data))
        return DummyResponse()


def test_select_target_nodes_uses_semantic_index(monkeypatch):
    index = DummyLocationIndex(["node-b", "node-c"])
    coord = ReplicationCoordinator(replication_factor=2, location_index=index)
    coord.register_node("node-a", "http://a")
    coord.register_node("node-b", "http://b")
    coord.register_node("node-c", "http://c")

    targets = coord._select_target_nodes("node-a", document_embedding=np.ones(2))
    assert targets == ["node-b", "node-c"]


def test_replicate_document_without_targets_marks_completed():
    coord = ReplicationCoordinator(replication_factor=2)

    async def _run():
        return await coord.replicate_document("file-1", source_node="node-a")

    task = asyncio.run(_run())

    assert task.status == ReplicationStatus.COMPLETED
    assert task.target_nodes == []
    assert task.progress == 1.0


def test_replication_worker_happy_path(monkeypatch):
    dummy_client = DummyAsyncClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: dummy_client)

    coord = ReplicationCoordinator(replication_factor=1)
    coord.register_node("node-a", "http://node-a")
    coord.register_node("node-b", "http://node-b")

    async def _run():
        await coord.start()
        await coord.replicate_document("file-42", source_node="node-a")
        await asyncio.sleep(0.05)
        await coord.stop()
        return coord.get_task_status("file-42")

    task = asyncio.run(_run())
    assert task.status == ReplicationStatus.COMPLETED
    assert task.completed_nodes == {"node-b"}
    assert dummy_client.calls["get"] and dummy_client.calls["post"]
