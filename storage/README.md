# Módulo Storage - Almacenamiento Distribuido

## 📋 Descripción

Sistema de almacenamiento para documentos e índices invertidos en DistriSearch.

## 📁 Estructura

```
storage/
├── __init__.py           # Exports públicos
├── document.py           # Documentos y DocumentStore
├── inverted_index.py     # Índice invertido con TF-IDF
├── tokenizer.py          # Tokenización y stopwords
└── persistence.py        # Persistencia en disco
```

## 🎯 Componentes

### 1. `document.py`
**Gestión de documentos:**
- `Document`: Dataclass con doc_id, content, metadata
- `DocumentStore`: Almacén local de documentos
  - `add()`, `get()`, `update()`, `delete()`
  - Serialización a/desde JSON

### 2. `inverted_index.py`
**Índice invertido:**
- Estructura: `término → {doc_ids}`
- Búsqueda por términos (`search()`)
- Búsqueda AND (`search_all()`)
- **Ranking TF-IDF**:
  - `compute_tf_idf()`: Score de relevancia
  - `rank_documents()`: Ordenar por relevancia

### 3. `tokenizer.py`
**Procesamiento de texto:**
- `tokenize()`: Texto → tokens (palabras)
- `remove_stopwords()`: Filtrado de stopwords (ES + EN)
- `compute_term_frequency()`: Frecuencia de términos

### 4. `persistence.py`
**Persistencia:**
- `PersistenceManager`: Guardar/cargar JSON
- `save_json()`, `load_json()`
- `snapshot()`: Crear snapshots
- `list_files()`, `clear_directory()`

## 🔧 Uso

### Almacenar Documentos

```python
from storage import Document, DocumentStore

store = DocumentStore()

doc = Document(
    doc_id="doc1",
    content="Distributed systems are complex",
    metadata={"author": "Alice"}
)

store.add(doc)
print(f"Total docs: {store.count()}")
```

### Índice Invertido

```python
from storage import InvertedIndex, tokenize_and_filter

index = InvertedIndex()

# Añadir documento al índice
content = "Raft consensus algorithm"
terms = tokenize_and_filter(content)
index.add_document("doc1", terms)

# Buscar
query_terms = tokenize_and_filter("consensus algorithm")
doc_ids = index.search(query_terms)

# Ranking TF-IDF
ranked = index.rank_documents(doc_ids, query_terms)
for doc_id, score in ranked:
    print(f"{doc_id}: {score:.2f}")
```

### Tokenización

```python
from storage.tokenizer import tokenize, remove_stopwords

text = "The distributed system uses Raft consensus"
tokens = tokenize(text)
# ['the', 'distributed', 'system', 'uses', 'raft', 'consensus']

filtered = remove_stopwords(tokens)
# ['distributed', 'system', 'uses', 'raft', 'consensus']
```

### Persistencia

```python
from storage.persistence import PersistenceManager

pm = PersistenceManager("data/node_0")

# Guardar documentos
pm.save_json("documents.json", store.to_dict())

# Guardar índice
pm.save_json("index.json", index.to_dict())

# Cargar
docs_data = pm.load_json("documents.json")
store.from_dict(docs_data)

# Snapshot
pm.snapshot("backup_2024", {
    "documents": store.to_dict(),
    "index": index.to_dict()
})
```

## 📊 TF-IDF Ranking

**Term Frequency (TF)**: Frecuencia del término en el documento

**Inverse Document Frequency (IDF)**:
```
IDF = log(N / DF)
```
donde:
- N = total de documentos
- DF = documentos que contienen el término

**TF-IDF Score**:
```
Score = TF * IDF
```

Documentos con mayor score son más relevantes.

## 🎛️ Stopwords

El módulo incluye **150+ stopwords** en español e inglés:
- ES: "el", "la", "de", "que", "y", ...
- EN: "the", "a", "an", "is", "are", ...

Se pueden especificar stopwords personalizados:
```python
custom_stops = {"custom", "stop", "word"}
tokens = remove_stopwords(tokens, custom_stops)
```

## 📈 Optimizaciones

1. **Índice eficiente**: Sets para O(1) lookup
2. **Lazy evaluation**: Solo calcula TF-IDF cuando se rankea
3. **Persistencia incremental**: Solo guarda cambios
4. **Tokenización regex**: Rápida y eficiente

## ✅ Serialización

Todos los componentes son **serializables a JSON**:
```python
# DocumentStore
data = store.to_dict()
store.from_dict(data)

# InvertedIndex
data = index.to_dict()
index.from_dict(data)
```

## 🚀 Integración

```python
from storage import (
    Document, DocumentStore,
    InvertedIndex,
    tokenize_and_filter,
    PersistenceManager
)

# Setup
store = DocumentStore()
index = InvertedIndex()
persistence = PersistenceManager("data/node_0")

# Añadir documento
doc = Document("doc1", "Distributed consensus")
store.add(doc)

terms = tokenize_and_filter(doc.content)
index.add_document(doc.doc_id, terms)

# Guardar
persistence.save_json("documents.json", store.to_dict())
persistence.save_json("index.json", index.to_dict())
```
