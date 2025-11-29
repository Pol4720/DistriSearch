# DistriSearch - Buscador Distribuido con Hipercubo

Prototipo funcional en Python de un buscador distribuido con arquitectura descentralizada basada en topología de hipercubo.

## 🎯 Características Principales

- **Arquitectura descentralizada**: Cada nodo tiene frontend HTTP y almacenamiento local (índice invertido)
- **Topología hipercubo**: Organización lógica de nodos con direcciones binarias y ruteo XOR
- **Data Balancer replicado**: Coordina localización de términos y gestiona índice global
- **Elección de líder automática**: Algoritmo Bully adaptado para recuperación ante fallos
- **Modo simulación y red real**: Desarrollo local y despliegue distribuido

## 📁 Estructura del Proyecto

```
DistriSearch/
├── hypercube.py          # Topología y ruteo en hipercubo
├── election.py           # Algoritmo Bully para elección de líder
├── storage.py            # Índice invertido local
├── network.py            # Abstracción de red (simulada/HTTP)
├── databalancer.py       # Líder replicado con índice global
├── node.py               # Nodo distribuido con API HTTP
├── simulator.py          # Simulador para demo local
├── tests/                # Tests unitarios (pytest)
│   ├── test_hypercube.py
│   ├── test_election.py
│   ├── test_storage.py
│   └── test_integration.py
├── requirements.txt      # Dependencias Python
├── Dockerfile            # Imagen Docker para nodos
├── docker-compose.yml    # Orquestación multi-nodo
└── README.md
```

## 🚀 Instalación

### Requisitos

- Python 3.11+
- pip

### Instalación de dependencias

```powershell
pip install -r requirements.txt
```

## 💻 Uso

### Modo Simulación (Recomendado para pruebas)

Ejecuta múltiples nodos en un solo proceso:

```powershell
# Demo automática con 5 nodos
python simulator.py --nodes 5 --auto

# Modo interactivo
python simulator.py --nodes 7

# Con debug activado
python simulator.py --nodes 5 --debug
```

### Modo Interactivo

Opciones disponibles:
1. Mostrar estado de la red
2. Demo: Operaciones básicas (indexado y búsqueda)
3. Demo: Ruteo en hipercubo
4. Demo: Elección de líder
5. Añadir documento personalizado
6. Buscar
0. Salir

### Modo HTTP (Red Real)

Cada nodo como proceso/contenedor independiente:

```powershell
# Nodo 0 (puerto 8000)
python -c "
import asyncio
from node import DistributedNode
from network import create_network

async def main():
    network = create_network('http')
    node = DistributedNode(node_id=0, dimensions=20, host='localhost', port=8000, network=network)
    await node.initialize(bootstrap_nodes=[0, 1, 2])
    await node.start_http_server()
    
    # Mantener activo
    await asyncio.Event().wait()

asyncio.run(main())
"
```

### Uso con Docker Compose

```powershell
# Iniciar 3 nodos
docker-compose up

# Escalar a 5 nodos
docker-compose up --scale node=5
```

## 🧪 Tests

Ejecutar tests unitarios:

```powershell
# Todos los tests
pytest

# Con verbosidad
pytest -v

# Solo tests de hipercubo
pytest tests/test_hypercube.py

# Con cobertura
pytest --cov=. --cov-report=html
```

## 📚 API HTTP

### Endpoints del Nodo

#### POST /doc
Añade un documento al índice local.

**Request:**
```json
{
  "doc_id": "doc1",
  "content": "Python es un lenguaje de programación",
  "metadata": {"author": "usuario"}
}
```

**Response:**
```json
{
  "status": "ok",
  "doc_id": "doc1",
  "terms_indexed": 3
}
```

#### GET /search?q={query}
Realiza búsqueda distribuida.

**Response:**
```json
{
  "query": "python",
  "total_results": 2,
  "results": [
    {
      "doc_id": "doc1",
      "score": 2.0,
      "snippet": "Python es un lenguaje...",
      "node_id": 0
    }
  ]
}
```

#### GET /status
Obtiene estado del nodo.

**Response:**
```json
{
  "node_id": 0,
  "binary_address": "00000000000000000000",
  "is_leader": true,
  "current_leader": 0,
  "known_neighbors": [1, 2, 4, 8, ...],
  "active_nodes": [0, 1, 2, 3, 4],
  "storage_stats": {
    "num_terms": 10,
    "num_documents": 3,
    "total_postings": 15
  }
}
```

#### GET /neighbors
Lista vecinos lógicos del hipercubo.

**Response:**
```json
{
  "node_id": 5,
  "neighbors": [4, 7, 1, 13, ...]
}
```

#### POST /route
Rutea mensaje a través del hipercubo (uso interno).

### Endpoints del Data Balancer (solo líder)

#### POST /register_node
Registra un nodo en el índice global.

```json
{
  "node_id": 1,
  "endpoint": "localhost:8001",
  "capacity": 100
}
```

#### POST /update_index
Actualiza índice global con términos del nodo.

```json
{
  "node_id": 1,
  "terms_added": ["python", "programming"],
  "terms_removed": ["java"]
}
```

#### GET /locate?q={term}
Localiza qué nodos contienen un término.

**Response:**
```json
{
  "term": "python",
  "nodes": [
    {"node_id": 0, "endpoint": "localhost:8000"},
    {"node_id": 2, "endpoint": "localhost:8002"}
  ]
}
```

#### POST /heartbeat
Heartbeat para mantener nodo activo.

```json
{
  "node_id": 1
}
```

## 🏗️ Arquitectura

### Topología Hipercubo

- Cada nodo tiene un ID de `d` bits (configurable, default: 20 bits)
- Vecinos lógicos: nodos que difieren en exactamente 1 bit
- Ruteo: bitflip del bit más significativo diferente, o greedy XOR si el vecino no existe
- Máximo `d` saltos para alcanzar cualquier destino (en hipercubo completo)

### Índice Invertido Local

- Estructura: `término → {doc_id: score}`
- Tokenización: lowercase, eliminación de stopwords
- Score: term frequency simple
- Persistencia: JSON (archivos `index.json` y `documents.json`)

### Data Balancer

- **Líder**: Mantiene índice global `término → set(node_ids)`
- **Followers**: Réplicas que sincronizan con el líder
- Heartbeat cada 2 segundos, timeout 6 segundos
- Snapshot del índice cada 30 segundos
- Notificaciones de actualización desde nodos cuando añaden/eliminan docs

### Elección de Líder (Bully)

- El nodo con mayor ID gana
- Mensajes: `ELECTION`, `OK`, `COORDINATOR`
- Timeout configurable (default: 3 segundos)
- Ruteo de mensajes a través del hipercubo

### Flujo de Búsqueda

1. Cliente envía `GET /search?q=term` a cualquier nodo
2. Nodo tokeniza la consulta
3. Nodo consulta al líder `GET /locate?q=term` por cada término
4. Líder retorna lista de nodos que contienen los términos
5. Nodo contacta a nodos candidatos para obtener resultados locales
6. Nodo agrega y ordena resultados por score
7. Retorna top-k resultados al cliente

## 🔧 Configuración

### Parámetros del Nodo

```python
node = DistributedNode(
    node_id=0,           # ID único del nodo
    dimensions=20,       # Bits del hipercubo (default: 20)
    host="localhost",    # Host del servidor HTTP
    port=8000,          # Puerto del servidor HTTP
    network=network     # Interfaz de red
)
```

### Red Simulada

```python
network = create_network(
    mode="simulated",
    latency_ms=10,      # Latencia simulada
    failure_rate=0.0    # Tasa de fallos (0.0 - 1.0)
)
```

## 📊 Ejemplos de Uso

### Ejemplo 1: Búsqueda básica

```python
import asyncio
from simulator import Simulator

async def demo():
    sim = Simulator(num_nodes=3)
    await sim.setup_nodes()
    
    # Añadir documentos
    await sim.nodes[0].add_document("doc1", "Python programming language")
    await sim.nodes[1].add_document("doc2", "Java programming language")
    
    # Buscar
    results = await sim.nodes[0].search("python")
    print(f"Encontrados {results['total_results']} resultados")
    
    await sim.cleanup()

asyncio.run(demo())
```

### Ejemplo 2: Simulación de fallo del líder

```python
async def demo_leader_failure():
    sim = Simulator(num_nodes=5)
    await sim.setup_nodes()
    
    # Obtener líder
    leader_id = sim.nodes[0].election.current_leader
    print(f"Líder actual: {leader_id}")
    
    # Simular fallo
    sim.network.simulate_node_failure(leader_id)
    
    # Nueva elección
    other_node = sim.nodes[0] if leader_id != 0 else sim.nodes[1]
    new_leader = await other_node.election.start_election()
    print(f"Nuevo líder: {new_leader}")
    
    await sim.cleanup()

asyncio.run(demo_leader_failure())
```

## ⚙️ Variables de Entorno (Docker)

```env
NODE_ID=0
DIMENSIONS=20
HOST=0.0.0.0
PORT=8000
BOOTSTRAP_NODES=node0:8000,node1:8000
```

## 🐛 Troubleshooting

### Problema: Elección de líder no converge

**Solución**: Verificar que todos los nodos conocen la lista completa de `active_nodes`. Aumentar timeout de elección.

### Problema: Búsqueda no encuentra resultados

**Solución**: Verificar que el líder está activo y que los nodos han enviado actualizaciones del índice. Revisar logs con `--debug`.

### Problema: Ruteo falla o hace loops

**Solución**: Asegurarse de que hay suficientes nodos activos para formar rutas válidas. Verificar cálculo de vecinos con `GET /neighbors`.

## 📈 Limitaciones Conocidas

- **No es DHT**: La localización de términos depende del Data Balancer centralizado (aunque replicado)
- **Elección simple**: Bully no garantiza fuerte consistencia como Raft/Paxos
- **Sin replicación de datos**: Cada documento existe solo en el nodo que lo indexó
- **Rendimiento**: Prototipo educativo, no optimizado para producción
- **Persistencia básica**: JSON files, no transaccional

## 🔮 Mejoras Futuras

- [ ] Implementar Raft en lugar de Bully para consenso robusto
- [ ] Replicación de documentos entre nodos
- [ ] Balanceo de carga dinámico
- [ ] Compresión del índice invertido
- [ ] Ranking avanzado (TF-IDF, BM25)
- [ ] Índice distribuido verdadero (DHT)
- [ ] Manejo de particiones de red
- [ ] Métricas y monitoreo (Prometheus)

## 📄 Licencia

MIT License - Proyecto educativo/prototipo

## 👥 Autor

Implementación de referencia para sistema de buscador distribuido con hipercubo.

---

**Nota**: Este es un prototipo funcional con fines educativos y de demostración. No está optimizado para producción.
