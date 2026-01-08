# Tests de Integración

## Objetivo
Verificar que los componentes interactúan correctamente (API ↔ DB ↔ servicios).

## Fixtures
```python
@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mongodb():
    with MongoDBContainer("mongo:6.0") as mongo:
        yield mongo.get_connection_url()
```

## Ejemplos
```python
async def test_upload_and_search(client, mongodb):
    # Subir documento
    resp = await client.post("/api/v1/upload", files={"file": ...})
    assert resp.status_code == 200
    doc_id = resp.json()["id"]
    
    # Buscar
    resp = await client.get("/api/v1/search?q=contenido")
    assert any(r["id"] == doc_id for r in resp.json())
```

## Base de datos de prueba
- Usar testcontainers o MongoDB en memoria.
- Limpiar datos entre tests con fixture `autouse`.

## Ubicación
`tests/integration/`