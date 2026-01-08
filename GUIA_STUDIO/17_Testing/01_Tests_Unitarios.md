# Tests Unitarios

## Objetivo
Probar funciones y clases de forma aislada, sin dependencias externas.

## Ejemplos
```python
def test_vectorizer_tfidf():
    vec = TFIDFVectorizer()
    vector = vec.vectorize("documento de prueba")
    assert vector.shape[0] > 0

def test_vp_tree_insert():
    tree = VPTree()
    tree.insert(doc_id="1", vector=[0.1, 0.2])
    assert tree.size() == 1
```

## Mocking
Usar `unittest.mock` o `pytest-mock` para aislar dependencias:
```python
def test_search_service(mocker):
    mocker.patch('app.storage.mongodb.find', return_value=[...])
    results = search_service.search("query")
    assert len(results) == 3
```

## Ubicación
`tests/unit/` con archivos `test_<modulo>.py`.

## Cobertura mínima sugerida
- Vectorizadores: 90%
- Particionamiento: 85%
- Utilidades: 80%