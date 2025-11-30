# Arquitectura Visual del Módulo Node

## 📐 Diagrama de Clases

```
┌─────────────────────────────────────────────────────────────────┐
│                      DistributedNode                             │
│                    (node/node.py)                                │
│                                                                  │
│  Orquestador principal que combina todos los mixins              │
│  mediante herencia múltiple                                      │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Hereda de (mixins)
             │
    ┌────────┴─────────┬──────────────┬──────────────┬──────────┐
    │                  │              │              │          │
    ▼                  ▼              ▼              ▼          ▼
┌─────────┐    ┌──────────────┐ ┌─────────────┐ ┌────────┐ ┌──────┐
│NodeCore │    │NodeMessaging │ │NodeReplication│ NodeSearch│NodeHTTP│
└─────────┘    └──────────────┘ └─────────────┘ └────────┘ └──────┘
```

## 🔄 Flujo de Datos

### 1. Añadir Documento
```
    Usuario
      │
      │ HTTP POST /doc
      ▼
┌──────────────┐
│  NodeHTTP    │ _http_add_document()
└──────┬───────┘
       │
       │ self.add_document()
       ▼
┌────────────────────┐
│ NodeReplication    │ add_document()
└──────┬─────────────┘
       │
       ├─► self.storage.add_document()  [NodeCore]
       │   (indexar localmente)
       │
       ├─► await self._replicate_document()
       │   (replicar a otros k-1 nodos)
       │   
       │   ┌──────────────┐
       │   │NodeMessaging │ route_message()
       │   └──────────────┘
       │
       └─► await self._notify_shard_coordinators()
           (notificar al Data Balancer)
           
           ┌──────────────┐
           │NodeMessaging │ _notify_shard_coordinators()
           └──────────────┘
```

### 2. Buscar Documento
```
    Usuario
      │
      │ HTTP GET /search?q=python
      ▼
┌──────────────┐
│  NodeHTTP    │ _http_search()
└──────┬───────┘
       │
       │ self.search()
       ▼
┌────────────┐
│ NodeSearch │ search()
└──────┬─────┘
       │
       ├─► await self._locate_term_nodes()
       │   (localizar nodos con término)
       │   
       │   ┌──────────────┐
       │   │NodeMessaging │ route_message() → shard coordinator
       │   └──────────────┘
       │
       ├─► await self._search_node()
       │   (buscar en nodos candidatos)
       │   
       │   ┌──────────────┐
       │   │NodeMessaging │ route_message() → nodos candidatos
       │   └──────────────┘
       │
       └─► self._aggregate_results()
           (agregar y ordenar)
```

### 3. Ruteo de Mensajes
```
    Nodo Origen
        │
        │ await route_message(dest_id=7, msg)
        ▼
┌──────────────────┐
│ NodeMessaging    │ route_message()
└───────┬──────────┘
        │
        ├─► ¿dest_id == self.node_id?
        │   
        │   SÍ  → self.handle_message(msg)
        │          └─► Despachar según msg['type']
        │
        │   NO  → Calcular next_hop (hipercubo)
        │          └─► self._send_to_node(next_hop)
        │                  │
        │                  │ self.network.send_message()
        │                  ▼
        │              Nodo Siguiente
        │                  │
        │                  │ (recursión hasta dest_id)
        │                  ▼
        │              Nodo Destino
        │                  │
        │                  └─► handle_message(msg)
```

## 🧩 Componentes de NodeCore

```
┌─────────────────────────────────────────────────────────┐
│                     NodeCore                            │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Hypercube   │  │   Storage    │  │  Consensus   │  │
│  │             │  │              │  │              │  │
│  │ - node_id   │  │ - index      │  │ - state      │  │
│  │ - neighbors │  │ - documents  │  │ - term       │  │
│  │ - dimensions│  │ - save()     │  │ - leader     │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Replication │  │   Security   │  │    Cache     │  │
│  │             │  │              │  │              │  │
│  │ - factor=3  │  │ - TLS        │  │ - max_size   │  │
│  │ - get_nodes │  │ - JWT        │  │ - get/put    │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │           DataBalancer                           │  │
│  │                                                  │  │
│  │  - is_leader                                     │  │
│  │  - shard_manager (16 shards)                     │  │
│  │  - global_index                                  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 📨 Tipos de Mensajes (NodeMessaging)

```
┌────────────────────────────────────────────────────────┐
│              handle_message()                          │
│                                                        │
│  switch (msg_type):                                    │
│                                                        │
│    ┌─────────────────┐                                │
│    │ 'route'         │ → _handle_route()              │
│    │ 'raft_message'  │ → _handle_raft_message()       │
│    │ 'search_local'  │ → handle_search_local()        │
│    │ 'replicate_doc' │ → handle_replicate_doc()       │
│    │ 'rollback_doc'  │ → handle_rollback_doc()        │
│    │ 'add_doc_primary'│ → handle_add_doc_primary()    │
│    │ 'update_shard'  │ → _handle_update_shard()       │
│    │ 'balancer_update'│ → _handle_balancer_update()   │
│    │ 'locate_term'   │ → _handle_locate_term()        │
│    │ 'ping'          │ → return pong                  │
│    │ 'cache_invalidate'│ → _handle_cache_invalidate() │
│    └─────────────────┘                                │
└────────────────────────────────────────────────────────┘
```

## 🔁 Ciclo de Vida del Nodo

```
┌────────────┐
│   START    │
└─────┬──────┘
      │
      │ node = DistributedNode(node_id, ...)
      ▼
┌─────────────────┐
│ __init__()      │ NodeCore.__init__()
│                 │   ├─► Crear hypercube
│                 │   ├─► Crear storage
│                 │   ├─► Crear consensus
│                 │   ├─► Crear replication
│                 │   ├─► Crear security
│                 │   ├─► Crear cache
│                 │   └─► Crear data_balancer
│                 │
│                 │ NodeHTTP.__init__()
│                 │   └─► app = None, runner = None
└─────┬───────────┘
      │
      │ await node.initialize(bootstrap_nodes)
      ▼
┌─────────────────────┐
│ initialize()        │ NodeCore.initialize()
│                     │   ├─► network.register_node()
│                     │   ├─► update_active_nodes()
│                     │   ├─► consensus.start()
│                     │   ├─► sleep(2.0)  # Esperar líder
│                     │   └─► Si líder: data_balancer.become_leader()
└─────┬───────────────┘
      │
      │ await node.start_http_server()
      ▼
┌──────────────────────┐
│ start_http_server()  │ NodeHTTP.start_http_server()
│                      │   ├─► create_http_app()
│                      │   ├─► setup runner
│                      │   └─► start site
└─────┬────────────────┘
      │
      │ ┌──────────────────────┐
      │ │   RUNNING STATE      │
      │ │                      │
      │ │ - Procesando requests│
      │ │ - Consenso activo    │
      │ │ - Replicando datos   │
      │ │ - Cache activo       │
      │ └──────────────────────┘
      │
      │ await node.shutdown()
      ▼
┌──────────────────┐
│ shutdown()       │ stop_http_server() → NodeHTTP
│                  │   └─► runner.cleanup()
│                  │
│                  │ NodeCore.shutdown()
│                  │   ├─► consensus.stop()
│                  │   ├─► data_balancer.shutdown()
│                  │   ├─► storage.save()
│                  │   └─► network.close()
└─────┬────────────┘
      │
      ▼
┌────────────┐
│    STOP    │
└────────────┘
```

## 🎯 Interacción Entre Módulos

```
                    ┌─────────────────┐
                    │  Usuario/API    │
                    └────────┬────────┘
                             │
                             ▼
         ┌───────────────────────────────────┐
         │          NodeHTTP                 │
         │  (Interfaz externa HTTP/REST)     │
         └───────────┬───────────────────────┘
                     │
        ┌────────────┴─────────────┐
        │                          │
        ▼                          ▼
┌──────────────┐           ┌──────────────┐
│NodeReplication│           │ NodeSearch   │
│(add_document) │           │  (search)    │
└───────┬───────┘           └───────┬──────┘
        │                           │
        │                           │
        └────────┬──────────────────┘
                 │
                 │ Ambos usan:
                 │
                 ▼
         ┌──────────────┐
         │NodeMessaging │
         │              │
         │ - route_message()
         │ - handle_message()
         │ - _notify_shard_coordinators()
         └──────┬────────┘
                │
                │ Accede a:
                │
                ▼
         ┌──────────────┐
         │  NodeCore    │
         │              │
         │ Todos los componentes:
         │ - hypercube
         │ - storage
         │ - consensus
         │ - replication
         │ - security
         │ - cache
         │ - data_balancer
         └──────────────┘
```

## 📊 Matriz de Dependencias

```
                  NodeCore  NodeMsg  NodeRepl  NodeSearch  NodeHTTP
NodeCore              -        -         -          -         -
NodeMessaging        ✓         -         -          -         -
NodeReplication      ✓         ✓         -          -         -
NodeSearch           ✓         ✓         -          -         -
NodeHTTP             ✓         ✓         ✓          ✓         -

Leyenda:
  -  : No depende
  ✓  : Depende (usa métodos/atributos)
  
Lectura:
  - NodeMessaging depende de NodeCore (usa self.network, self.consensus, etc.)
  - NodeReplication depende de NodeCore y NodeMessaging
  - NodeSearch depende de NodeCore y NodeMessaging
  - NodeHTTP depende de todos (orquesta)
```

## 🔐 Flujo de Seguridad

```
┌───────────────┐
│  Cliente      │
└───────┬───────┘
        │
        │ HTTPS (si TLS habilitado)
        ▼
┌────────────────────┐
│  NodeHTTP          │
│                    │
│  self.security     │ ← NodeCore
│    .get_ssl_context()
└────────┬───────────┘
         │
         │ JWT Token (si requerido)
         ▼
┌─────────────────────┐
│  NodeCore           │
│                     │
│  self.security      │
│    .verify_token()  │
└─────────────────────┘
```

## 📈 Escalabilidad del Diseño

```
Facilidad para añadir nuevos módulos:

1. Crear nuevo mixin:
   node/node_analytics.py
   
2. Añadir a DistributedNode:
   class DistributedNode(
       NodeCore,
       NodeMessaging,
       NodeReplication,
       NodeSearch,
       NodeHTTP,
       NodeAnalytics  # ← NUEVO
   ):

3. Usar inmediatamente:
   node = DistributedNode(...)
   stats = await node.get_query_stats()  # ← Método de NodeAnalytics
```

---

**Ventaja clave:** Cada módulo es independiente y puede evolucionar sin afectar a los demás. La herencia múltiple permite composición flexible.
