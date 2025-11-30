# Módulo Node - Arquitectura Modular

## 📁 Estructura de Archivos

```
node/
├── __init__.py              # Exporta DistributedNode
├── node.py                  # Clase principal (orquestador)
├── node_core.py            # Inicialización y componentes básicos
├── node_messaging.py       # Ruteo y manejo de mensajes
├── node_replication.py     # Lógica de replicación de documentos
├── node_search.py          # Lógica de búsqueda distribuida
└── node_http.py            # API HTTP/REST
```

## 🎯 Responsabilidades de Cada Módulo

### `node.py` - Orquestador Principal
**Rol:** Clase fachada que combina todos los mixins.

**Contiene:**
- Clase `DistributedNode` (hereda de todos los mixins)
- Constructor que inicializa todos los componentes
- Método `shutdown()` que coordina el apagado

**Uso:**
```python
from node import DistributedNode

node = DistributedNode(node_id=5, port=8005)
await node.initialize([0, 1, 2, 3, 4])
await node.start_http_server()
```

---

### `node_core.py` - Componentes Básicos
**Rol:** Inicialización y gestión de componentes fundamentales.

**Contiene:**
- Clase `NodeCore` (mixin base)
- Inicialización de:
  - Hipercubo (topología)
  - Storage (índice invertido)
  - Consenso Raft
  - Replicación
  - Seguridad (TLS/JWT)
  - Cache
  - Data Balancer
- Método `initialize()` para setup de red
- Método `get_status()` para estado del nodo
- Método `shutdown()` para apagado limpio

**Componentes gestionados:**
```python
self.hypercube          # Topología hipercubo
self.storage            # Índice invertido local
self.consensus          # Consenso Raft
self.replication        # Gestor de réplicas
self.security           # TLS + JWT
self.cache              # Cache distribuido
self.data_balancer      # Balanceador con sharding
```

---

### `node_messaging.py` - Mensajería y Ruteo
**Rol:** Manejo de comunicación entre nodos.

**Contiene:**
- Clase `NodeMessaging` (mixin)
- `route_message()`: Ruteo por hipercubo
- `handle_message()`: Despacho de mensajes
- Handlers para cada tipo de mensaje:
  - `_handle_route()`: Ruteo multi-hop
  - `_handle_raft_message()`: Consenso
  - `_handle_update_shard()`: Actualización de shards
  - `_handle_balancer_update()`: Actualización al líder
  - `_handle_locate_term()`: Localización de términos
  - `_handle_cache_invalidate()`: Invalidación de cache
- `_notify_shard_coordinators()`: Notificación de cambios

**Tipos de mensajes soportados:**
```python
'route'              # Ruteo multi-hop
'raft_message'       # Consenso Raft
'search_local'       # Búsqueda local
'replicate_doc'      # Replicación de documento
'rollback_doc'       # Rollback de replicación
'add_doc_primary'    # Redirección a primario
'update_shard'       # Actualización de shard
'balancer_update'    # Actualización al líder
'locate_term'        # Localización de término
'ping'               # Ping/pong
'cache_invalidate'   # Invalidar cache
```

---

### `node_replication.py` - Replicación de Documentos
**Rol:** Replicación distribuida con quorum.

**Contiene:**
- Clase `NodeReplication` (mixin)
- `add_document()`: Añade documento con replicación k=3
- `_replicate_document()`: Replica a nodo específico
- `_rollback_replication()`: Rollback si no hay quorum
- `_send_rollback()`: Envía rollback a réplica
- Handlers:
  - `handle_replicate_doc()`: Recibe replicación
  - `handle_rollback_doc()`: Recibe rollback
  - `handle_add_doc_primary()`: Redirección a primario

**Algoritmo de replicación:**
```
1. Determinar k=3 nodos réplica (consistent hashing)
2. Si soy réplica: indexar localmente
3. Si no soy réplica: redirigir a primario
4. Replicar en paralelo a otros k-1 nodos
5. Esperar quorum (k/2 + 1 = 2)
6. Si no hay quorum: rollback
7. Notificar al Data Balancer (solo primario)
```

**Garantías:**
- ✅ Quorum writing (2/3 réplicas mínimo)
- ✅ Rollback automático si falla quorum
- ✅ Redirección automática al nodo primario
- ✅ Timeout de 5s por replicación

---

### `node_search.py` - Búsqueda Distribuida
**Rol:** Búsqueda en múltiples nodos con tolerancia a fallos.

**Contiene:**
- Clase `NodeSearch` (mixin)
- `search()`: Búsqueda distribuida principal
- `_search_local()`: Búsqueda en este nodo
- `_search_node()`: Búsqueda en nodo remoto
- `_search_replicas()`: Fallback a réplicas
- `_locate_term_nodes()`: Localiza nodos con término (usa sharding)
- `_aggregate_results()`: Agrega y ordena resultados
- `handle_search_local()`: Handler de búsqueda local

**Algoritmo de búsqueda:**
```
1. Tokenizar consulta
2. Localizar nodos para cada término (con cache)
3. Buscar en paralelo en nodos candidatos
4. Si algún nodo falla (timeout 5s):
   → Intentar réplicas alternativas (timeout 3s)
5. Agregar resultados por doc_id (sumar scores)
6. Ordenar por score descendente
7. Retornar top-k
```

**Optimizaciones:**
- ✅ Cache de ubicaciones de términos (evita consultar líder)
- ✅ Búsquedas en paralelo (asyncio.gather)
- ✅ Fallback automático a réplicas
- ✅ Agregación de scores de múltiples nodos
- ✅ Timeouts configurables (5s normal, 3s réplicas)

---

### `node_http.py` - API HTTP/REST
**Rol:** Servidor web y endpoints REST.

**Contiene:**
- Clase `NodeHTTP` (mixin)
- `create_http_app()`: Crea aplicación aiohttp
- `start_http_server()`: Inicia servidor (soporta TLS)
- `stop_http_server()`: Detiene servidor
- Endpoints:
  - `POST /doc`: Añadir documento
  - `GET /search?q={query}&top_k={n}`: Buscar
  - `POST /route`: Rutear mensaje
  - `GET /status`: Estado del nodo
  - `GET /neighbors`: Vecinos del nodo
  - `GET /metrics`: Métricas Prometheus
  - `POST /register_node`: Registrar nodo (Data Balancer)
  - `POST /update_index`: Actualizar índice (Data Balancer)
  - `GET /locate?term={term}`: Localizar término (Data Balancer)
  - `POST /heartbeat`: Heartbeat (Data Balancer)

**Ejemplos de uso:**
```bash
# Añadir documento
curl -X POST http://localhost:8000/doc \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "doc1", "content": "Python programming"}'

# Buscar
curl "http://localhost:8000/search?q=python&top_k=10"

# Estado
curl "http://localhost:8000/status"

# Métricas Prometheus
curl "http://localhost:8000/metrics"
```

---

## 🔄 Flujo de Interacción Entre Módulos

### 1. Añadir Documento
```
Usuario
  ↓ POST /doc
NodeHTTP._http_add_document()
  ↓ await self.add_document()
NodeReplication.add_document()
  ↓ self.storage.add_document()  [NodeCore]
  ↓ await self._replicate_document()
NodeMessaging.route_message()
  ↓ await self._notify_shard_coordinators()
NodeMessaging._notify_shard_coordinators()
```

### 2. Buscar Documento
```
Usuario
  ↓ GET /search?q=python
NodeHTTP._http_search()
  ↓ await self.search()
NodeSearch.search()
  ↓ await self._locate_term_nodes()
  ↓   → NodeMessaging.route_message() al shard coordinator
  ↓ await self._search_node()
  ↓   → NodeMessaging.route_message() a nodos candidatos
  ↓ self._aggregate_results()
```

### 3. Inicialización
```
main.py
  ↓ node = DistributedNode(node_id=5)
node.py.__init__()
  ↓ NodeCore.__init__()  [crea todos los componentes]
  ↓ NodeHTTP.__init__()  [inicializa servidor web]
  ↓
  ↓ await node.initialize()
NodeCore.initialize()
  ↓ await self.network.register_node()
  ↓ await self.consensus.start()
  ↓ self.data_balancer.become_leader()  [si es líder]
  ↓
  ↓ await node.start_http_server()
NodeHTTP.start_http_server()
```

---

## 🧩 Ventajas de la Arquitectura Modular

### 1. **Separación de Responsabilidades**
Cada módulo tiene una función clara y única:
- `node_core`: Setup y configuración
- `node_messaging`: Comunicación
- `node_replication`: Persistencia distribuida
- `node_search`: Consultas
- `node_http`: Interfaz externa

### 2. **Facilita el Testing**
```python
# Test solo de replicación
from node.node_replication import NodeReplication

class MockNode(NodeCore, NodeMessaging, NodeReplication):
    pass

node = MockNode(node_id=1)
result = await node.add_document("doc1", "content")
assert result['status'] == 'ok'
```

### 3. **Facilita el Debugging**
```python
# Logs específicos por módulo
logger = logging.getLogger(__name__)  # En cada módulo

# Configurar niveles diferentes
logging.getLogger('node.node_replication').setLevel(logging.DEBUG)
logging.getLogger('node.node_http').setLevel(logging.INFO)
```

### 4. **Permite Extensiones Fáciles**
```python
# Nuevo módulo para ML features
class NodeML:
    async def recommend_documents(self, user_id: str):
        # Implementación de recomendaciones
        pass

# Añadir a DistributedNode
class DistributedNode(
    NodeCore,
    NodeMessaging,
    NodeReplication,
    NodeSearch,
    NodeHTTP,
    NodeML  # ← Nueva funcionalidad
):
    pass
```

### 5. **Reduce Complejidad Cognitiva**
- Archivo original: **791 líneas** 😵
- Módulos separados: 
  - `node_core.py`: **~230 líneas** ✅
  - `node_messaging.py`: **~270 líneas** ✅
  - `node_replication.py`: **~230 líneas** ✅
  - `node_search.py`: **~290 líneas** ✅
  - `node_http.py`: **~260 líneas** ✅
  - `node.py`: **~120 líneas** ✅

---

## 📝 Convenciones de Código

### Métodos Públicos
Métodos que pueden ser llamados externamente:
```python
async def add_document(...)      # NodeReplication
async def search(...)            # NodeSearch
async def route_message(...)     # NodeMessaging
async def initialize(...)        # NodeCore
def get_status(...)              # NodeCore
```

### Métodos Privados (prefijo `_`)
Métodos internos del módulo:
```python
async def _replicate_document(...)    # NodeReplication
async def _search_node(...)           # NodeSearch
async def _send_to_node(...)          # NodeMessaging
def _update_known_neighbors(...)      # NodeCore
```

### Handlers (prefijo `handle_` o `_http_`)
Manejadores de eventos/mensajes:
```python
async def handle_message(...)         # NodeMessaging
async def handle_replicate_doc(...)   # NodeReplication
async def _http_add_document(...)     # NodeHTTP
async def _handle_update_shard(...)   # NodeMessaging
```

---

## 🚀 Ejemplo Completo de Uso

```python
import asyncio
from node import DistributedNode

async def main():
    # 1. Crear nodos
    nodes = [
        DistributedNode(node_id=i, port=8000+i)
        for i in range(5)
    ]
    
    # 2. Inicializar red
    all_node_ids = [0, 1, 2, 3, 4]
    for node in nodes:
        await node.initialize(bootstrap_nodes=all_node_ids)
    
    # 3. Iniciar servidores HTTP
    for node in nodes:
        await node.start_http_server()
    
    # 4. Añadir documentos (se replican automáticamente)
    await nodes[0].add_document(
        "doc1", 
        "Python is a great programming language"
    )
    
    # 5. Buscar desde cualquier nodo
    results = await nodes[2].search("Python programming")
    print(f"Encontrados: {results['total_results']} documentos")
    
    # 6. Ver estado
    status = nodes[0].get_status()
    print(f"Líder: {status['current_leader']}")
    print(f"Estado Raft: {status['raft_state']}")
    
    # 7. Apagar
    for node in nodes:
        await node.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔍 Debugging Tips

### Ver qué módulo maneja cada operación
```python
import logging

# Habilitar logs detallados
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

# Verás logs como:
# node.node_replication - INFO - Nodo 1: Añadiendo documento doc1
# node.node_messaging - DEBUG - Ruteo de 1 a 3 vía 2
# node.node_search - INFO - Nodo 2: Búsqueda distribuida: 'Python'
# node.node_http - INFO - Nodo 0: servidor HTTP en http://localhost:8000
```

### Inspeccionar componentes
```python
node = DistributedNode(node_id=5)

# Componentes de NodeCore
print(node.hypercube.binary_address)
print(node.storage.get_stats())
print(node.consensus.state)

# Componentes de NodeHTTP
print(node.app.router._resources)

# Componentes de NodeReplication
print(node.replication.replication_factor)
```

---

## ✅ Checklist de Mantenimiento

Antes de modificar un módulo, pregúntate:

- [ ] ¿Este cambio afecta a otros módulos?
- [ ] ¿Necesito actualizar tests?
- [ ] ¿La interfaz pública se mantiene igual?
- [ ] ¿Los logs son suficientemente descriptivos?
- [ ] ¿Hay documentación en docstrings?

---

¡Arquitectura modular completa! 🎉
