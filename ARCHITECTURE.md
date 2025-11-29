# Arquitectura de DistriSearch

## 📐 Visión General

DistriSearch es un buscador distribuido que combina:
- Topología de **hipercubo lógico** para organización de nodos
- **Data Balancer replicado** para coordinar metadatos de términos
- **Elección de líder** automática (algoritmo Bully)
- **Índices invertidos locales** en cada nodo
- **Ruteo XOR-based** para comunicación entre nodos

## 🏗️ Componentes Principales

### 1. Nodo Distribuido (`node.py`)

Cada nodo es autónomo y contiene:

```
┌─────────────────────────────────────────┐
│         Nodo Distribuido                │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │   API HTTP (aiohttp)            │   │
│  │   - POST /doc                   │   │
│  │   - GET /search                 │   │
│  │   - POST /route                 │   │
│  │   - GET /status                 │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │   Índice Invertido Local        │   │
│  │   término → {doc_id: score}     │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │   Módulo de Hipercubo           │   │
│  │   - ID binario                  │   │
│  │   - Lista de vecinos            │   │
│  │   - Ruteo XOR                   │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │   Elección de Líder (Bully)     │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │   Data Balancer (si es líder)   │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 2. Topología Hipercubo (`hypercube.py`)

El hipercubo organiza nodos en un espacio lógico d-dimensional:

```
Ejemplo: Hipercubo de 3 bits (8 nodos posibles)

        001 ─────── 101
       /│          /│
      / │         / │
    000─┼───────100 │
     │  011 ─────┼─111
     │ /         │ /
     │/          │/
    010 ─────── 110

Vecinos del nodo 000:
- Bit 0: 001 (flip bit 0)
- Bit 1: 010 (flip bit 1)
- Bit 2: 100 (flip bit 2)
```

**Algoritmo de Ruteo:**
1. Calcular XOR entre nodo actual y destino
2. Elegir bit más significativo diferente
3. Si el vecino existe, enviar mensaje
4. Si no, usar greedy: elegir vecino que minimice distancia XOR

### 3. Índice Invertido (`storage.py`)

Estructura de datos local en cada nodo:

```
Índice Invertido:
┌──────────┬────────────────────┐
│ Término  │ Postings           │
├──────────┼────────────────────┤
│ python   │ {doc1: 3.0,        │
│          │  doc3: 1.0}        │
├──────────┼────────────────────┤
│ java     │ {doc2: 2.0}        │
└──────────┴────────────────────┘

Documentos:
┌────────┬─────────────────────────┐
│ Doc ID │ Contenido               │
├────────┼─────────────────────────┤
│ doc1   │ "Python programming..." │
│ doc2   │ "Java development..."   │
└────────┴─────────────────────────┘
```

### 4. Data Balancer (`databalancer.py`)

Mantiene índice global de términos:

```
Índice Global (en líder):
┌──────────┬─────────────────────┐
│ Término  │ Nodos que lo tienen │
├──────────┼─────────────────────┤
│ python   │ {0, 2, 4}           │
│ java     │ {1, 3}              │
│ docker   │ {0, 1, 2}           │
└──────────┴─────────────────────┘

Metadatos de Nodos:
┌─────────┬──────────┬──────────────┐
│ Node ID │ Endpoint │ Última HB    │
├─────────┼──────────┼──────────────┤
│ 0       │ :8000    │ 1234567890.1 │
│ 1       │ :8001    │ 1234567889.5 │
└─────────┴──────────┴──────────────┘
```

### 5. Elección de Líder (`election.py`)

Algoritmo Bully adaptado:

```
Escenario: Nodo 3 detecta fallo del líder (nodo 7)

Paso 1: Nodo 3 envía ELECTION a nodos con ID mayor
        3 → ELECTION → [4, 5, 6, 7]

Paso 2: Nodos vivos responden OK
        4 → OK → 3
        5 → OK → 3
        (6 y 7 no responden)

Paso 3: Nodo 3 espera que ellos se encarguen
        
Paso 4: Nodo 5 (mayor ID vivo) envía ELECTION a [6, 7]
        No recibe OK (timeout)

Paso 5: Nodo 5 se declara COORDINATOR
        5 → COORDINATOR → [todos]

Resultado: Nodo 5 es el nuevo líder
```

## 🔄 Flujos de Operación

### Flujo 1: Indexar Documento

```
1. Cliente → POST /doc → Nodo A
2. Nodo A: Tokeniza y añade a índice local
3. Nodo A: Guarda en disco
4. Nodo A → POST /update_index → Líder
   {node_id: A, terms_added: ["python", "java"]}
5. Líder: Actualiza índice global
   python → {A, ...}
   java → {A, ...}
6. Líder: Responde OK
7. Nodo A → Cliente: {status: ok}
```

### Flujo 2: Búsqueda Distribuida

```
1. Cliente → GET /search?q=python → Nodo A

2. Nodo A: Tokeniza "python" → ["python"]

3. Para cada término:
   Nodo A → GET /locate?q=python → Líder
   
4. Líder responde:
   {term: "python", nodes: [{node_id: 0, ...}, {node_id: 2, ...}]}

5. Nodo A consulta a cada nodo candidato:
   Nodo A → mensaje search_local → Nodo 0 (vía ruteo)
   Nodo A → mensaje search_local → Nodo 2 (vía ruteo)

6. Cada nodo responde con resultados locales:
   Nodo 0 → {results: [{doc1, score: 3.0}, ...]}
   Nodo 2 → {results: [{doc5, score: 1.5}, ...]}

7. Nodo A agrega y ordena:
   [doc1 (3.0), doc5 (1.5), ...]

8. Nodo A → Cliente: {query: "python", results: [...]}
```

### Flujo 3: Ruteo de Mensaje

```
Objetivo: Nodo 2 (010) quiere enviar a Nodo 7 (111)

Paso 1: Calcular XOR
  2 XOR 7 = 010 XOR 111 = 101
  Bits diferentes: 0, 2

Paso 2: Elegir bit más significativo (bit 2)
  Vecino candidato: 010 XOR 100 = 110 (Nodo 6)

Paso 3: ¿Nodo 6 está disponible?
  SÍ → Enviar a Nodo 6
  NO → Usar greedy: buscar vecino con menor XOR a destino

Paso 4: Nodo 6 recibe y reenvía
  6 (110) a 7 (111)
  XOR = 001, bit 0 diferente
  Vecino: 110 XOR 001 = 111 (Nodo 7)
  
Paso 5: Nodo 7 recibe mensaje (destino alcanzado)

Ruta total: 2 → 6 → 7 (2 saltos)
```

## 📊 Modelo de Datos

### Documento
```python
{
    "doc_id": "unique_id",
    "content": "texto del documento",
    "metadata": {
        "author": "usuario",
        "timestamp": 1234567890
    }
}
```

### Mensaje de Ruteo
```python
{
    "type": "route",
    "dest_id": 7,
    "hop_limit": 32,
    "payload": {
        "type": "ping",
        "sender_id": 2
    }
}
```

### Actualización de Índice
```python
{
    "node_id": 3,
    "terms_added": ["python", "docker"],
    "terms_removed": ["java"],
    "timestamp": 1234567890.5
}
```

## 🎯 Decisiones de Diseño

### ¿Por qué NO DHT?

- **Control centralizado (replicado)**: Data Balancer mantiene vista completa
- **Simplicidad**: Más fácil de entender y debuguear
- **Flexibilidad**: Políticas de replicación/balanceo personalizables
- **Trade-off**: Punto de fallo (mitigado por elección de líder)

### ¿Por qué Bully y no Raft?

- **Simplicidad**: Bully es más fácil de implementar
- **Suficiente para prototipo**: Demo funcional de elección
- **Limitación conocida**: No garantiza fuerte consistencia
- **Mejora futura**: Reemplazar por Raft para producción

### ¿Por qué Hipercubo?

- **Ruteo predecible**: O(log N) saltos máximo
- **Tolerancia a fallos**: Múltiples rutas alternativas
- **Escalabilidad**: Crecimiento exponencial
- **Eficiencia**: Bajo overhead de mantenimiento

## 🔐 Garantías y Limitaciones

### Garantías ✅
- Eventual consistency del índice global
- Elección de líder eventual
- Ruteo always-forward (reduce distancia XOR)
- Datos locales siempre accesibles

### Limitaciones ⚠️
- No hay strong consistency
- Pérdida de datos si nodo falla (no replicados)
- Líder único es bottleneck
- Network partitions no manejadas explícitamente

## 📈 Complejidad

| Operación              | Complejidad      | Notas                    |
|------------------------|------------------|--------------------------|
| Ruteo                  | O(d)             | d = dimensiones          |
| Búsqueda local         | O(log D)         | D = docs locales         |
| Búsqueda distribuida   | O(d + k·log D)   | k = nodos consultados    |
| Elección líder         | O(n²)            | n = nodos totales        |
| Update índice          | O(t)             | t = términos nuevos      |

## 🚀 Extensiones Posibles

1. **Replicación de datos**: Cada doc en k nodos
2. **Sharding del Data Balancer**: Particionar índice global
3. **Caching distribuido**: LRU cache en cada nodo
4. **Compresión**: Compresión de índices y documentos
5. **Ranking avanzado**: TF-IDF, BM25, word2vec
6. **Geo-awareness**: Ruteo consciente de latencia
7. **Multi-tenancy**: Aislamiento por namespace

---

**Nota**: Esta arquitectura prioriza simplicidad y educación sobre optimización extrema.
