# Tiempos de Sincronización y Replicación en DistriSearch

Este documento describe los intervalos de sincronización configurados en el sistema y las recomendaciones de tiempo de espera para diferentes escenarios.

## Intervalos de Sincronización Configurados

| Mecanismo | Intervalo | Archivo | Descripción |
|-----------|-----------|---------|-------------|
| **Gossip incremental** | 5 segundos | `user_document_registry.py` | Propaga cambios recientes del UserDocumentRegistry a los peers |
| **Full sync interno** | 30 segundos | `user_document_registry.py` | Sincronización completa del registro dentro del loop de gossip |
| **Periodic full sync** | 60 segundos | `dependencies.py` | Tarea externa que fuerza sincronización completa de usuarios y documentos |
| **Sync inicial de usuarios** | 10 segundos | `dependencies.py` | Después del arranque, sincroniza usuarios desde peers (delay inicial) |
| **Heartbeat** | 5 segundos | `heartbeat_service.py` | Verificación de nodos vivos |
| **Timeout de heartbeat** | 15 segundos | `heartbeat_service.py` | Tiempo para considerar un nodo como caído |

## Tiempos de Espera Recomendados por Escenario

### Escenario 1: Operaciones Normales

| Operación | Tiempo de Espera | Justificación |
|-----------|------------------|---------------|
| Después de crear/subir documento | **5-10 segundos** | 1-2 ciclos de gossip |
| Después de eliminar documento | **10-15 segundos** | Propagación de tombstone |
| Verificar listado de documentos | **5 segundos** | 1 ciclo de gossip |
| Búsqueda después de indexación | **5 segundos** | Índice local es inmediato |

### Escenario 2: Recuperación de Fallos

| Operación | Tiempo de Espera | Justificación |
|-----------|------------------|---------------|
| Después de reiniciar un nodo | **30-60 segundos** | Sync inicial + 1 full sync |
| Después de restaurar conectividad | **60-90 segundos** | 1-2 ciclos de full sync |
| Verificación de consistencia completa | **120 segundos** | 2 full syncs para garantizar convergencia |
| Nueva elección de líder | **15-30 segundos** | Timeout de heartbeat + elección Bully |

### Escenario 3: Partición de Red

| Fase | Tiempo de Espera | Descripción |
|------|------------------|-------------|
| Detección de partición | **15-20 segundos** | Heartbeat timeout |
| Durante partición | **Indefinido** | Cada isla funciona independientemente |
| Post-reconciliación | **90-120 segundos** | Full sync + resolución de conflictos |
| Verificación de deduplicación | **120 segundos** | Asegurar que content_hash eliminó duplicados |

## Arquitectura de Sincronización

```
┌─────────────────────────────────────────────────────────────────┐
│                    NODO DistriSearch                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │ UserDocument    │     │ Periodic Full   │                   │
│  │ Registry        │     │ Sync Task       │                   │
│  │                 │     │                 │                   │
│  │ • Gossip: 5s    │     │ • Interval: 60s │                   │
│  │ • Full: 30s     │     │ • Users + Docs  │                   │
│  └────────┬────────┘     └────────┬────────┘                   │
│           │                       │                             │
│           ▼                       ▼                             │
│  ┌─────────────────────────────────────────┐                   │
│  │         HTTP Sync Endpoints             │                   │
│  │  POST /api/v1/internal/sync/registry    │                   │
│  │  GET  /api/v1/internal/sync/registry/all│                   │
│  │  POST /api/v1/internal/sync/full        │                   │
│  └─────────────────────────────────────────┘                   │
│                       │                                         │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        ▼ HTTP a otros nodos
              ┌─────────────────┐
              │   Otros Nodos   │
              │   (Peers)       │
              └─────────────────┘
```

## Mecanismos de Consistencia

### Vector Clocks
El `UserDocumentRegistry` usa vector clocks para resolver conflictos:
- Cada entrada tiene un `vector_clock: Dict[str, int]`
- Al hacer merge, la entrada con vector clock "mayor" gana
- Si hay conflictos, se usa `updated_at` como desempate

### Content Hash (Deduplicación)
Para evitar documentos duplicados (especialmente post-partición):
- Se calcula `SHA256(title:content)` para documentos de texto
- Se calcula `SHA256(file_bytes)` para archivos subidos
- Antes de crear, se verifica si existe documento con mismo hash del mismo usuario

### Tombstones
Los documentos eliminados no se borran físicamente de inmediato:
- Se marcan con `is_deleted: true`
- Se propagan via gossip
- Permiten que eliminaciones se sincronicen correctamente

## Comportamiento Durante Particiones de Red

### Modo de Operación
DistriSearch opera en modo **AP** (Available + Partition tolerant) del teorema CAP:
- Durante partición, cada nodo sigue aceptando lecturas y escrituras
- La consistencia es eventual (se reconcilia al restaurar conectividad)

### Acceso Durante Partición

```
Escenario: 3 nodos, Nodo B pierde conectividad WiFi

ANTES:
  Usuario1 → [Nodo A] ←──WiFi──→ [Nodo B] ←──WiFi──→ [Nodo C] ← Usuario3
                                    ↑
                                 Usuario2

DURANTE PARTICIÓN:
  Usuario1 → [Nodo A] ←──WiFi──→ [Nodo C] ← Usuario3
  
  Usuario2 → [Nodo B] (accede via localhost:443 o 127.0.0.1:443)
             ↑
        (Funciona localmente, stack completo en cada nodo)

DESPUÉS (reconexión):
  [Nodo A] ←──WiFi──→ [Nodo B] ←──WiFi──→ [Nodo C]
              ↓
     Sincronización automática (60-90 segundos)
```

### Puntos Clave
1. **Cada nodo tiene stack completo**: MongoDB local, backend, frontend
2. **Sin red, el nodo sigue funcionando**: Los usuarios en esa máquina acceden via localhost
3. **Reconciliación automática**: Al restaurar red, gossip y full sync reconcilian datos
4. **Deduplicación**: Si se creó el mismo documento en ambos lados, content_hash evita duplicados

## Configuración de Tiempos (Personalización)

Para ajustar los tiempos de sincronización, modifica estos archivos:

### `backend/app/storage/user_document_registry.py`
```python
def __init__(
    self,
    node_id: str,
    sqlite_client: SQLiteClient,
    gossip_interval: float = 5.0,  # ← Cambiar aquí
    ...
):
```

### `backend/app/api/dependencies.py`
```python
# Sync inicial de usuarios
asyncio.create_task(_sync_users_from_peers_delayed(bully_peers, 10.0))  # ← delay inicial

# Periodic full sync
asyncio.create_task(_periodic_full_sync(bully_peers, interval=60.0))  # ← intervalo
```

## Scripts de Prueba

### Escenario 1: Operación Normal (3 nodos)
```bash
cd /path/to/DistriSearch
python scripts/test_scenario_1.py --base-url https://IP_SWARM_MANAGER:443
```

### Escenario 2: Partición de Red (Manual)

Dado que las particiones reales involucran desconectar WiFi, el test se ejecuta en fases:

```bash
# Fase 1: Preparación (desde máquina con acceso a todos los nodos)
python scripts/test_scenario_2.py --phase prepare

# Fase 2: Durante partición (ejecutar en cada nodo aislado)
# En Nodo A: 
python scripts/test_scenario_2.py --phase partition --node localhost

# En Nodo B (aislado):
python scripts/test_scenario_2.py --phase partition --node localhost

# Fase 3: Verificación post-reconexión
python scripts/test_scenario_2.py --phase verify
```

## Troubleshooting

### Los documentos no aparecen en el listado
1. Esperar 10-15 segundos (gossip + full sync)
2. Verificar logs: `docker service logs distrisearch_slave`
3. Forzar sync: `POST /api/v1/internal/sync/full`

### Documentos duplicados después de partición
1. Verificar que `content_hash` está implementado
2. Los duplicados exactos se detectan al crear, no retroactivamente
3. Si ya existen duplicados, eliminar manualmente el más reciente

### Nodo no se sincroniza después de reconexión
1. Verificar que el nodo detectó a los peers: revisar logs de gossip
2. Verificar endpoints de sync: `GET /api/v1/internal/sync/registry/all`
3. Reiniciar el servicio en ese nodo si persiste
