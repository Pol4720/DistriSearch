# Análisis de Problemas de Replicación y Consistencia en DistriSearch

## Problemas Identificados

### 1. **Gossip Protocol NO está implementado realmente**

**Ubicación:** `backend/app/storage/user_document_registry.py` líneas 465-472

```python
async def _send_gossip(self) -> None:
    """Send pending updates to peers."""
    if not self._pending_updates:
        return
    
    updates = self._pending_updates.copy()
    self._pending_updates.clear()
    
    # In a real implementation, this would use HTTP/gRPC to send to peers
    # For now, log the intent
    logger.debug(f"Would gossip {len(updates)} updates to {len(self._peer_addresses)} peers")
```

**Impacto:** La información de qué documentos pertenecen a qué usuario NO se propaga entre nodos. Cada nodo solo conoce los documentos que él almacena localmente.

### 2. **`get_cluster_nodes()` no existe en ClusterManager**

**Ubicación:** `backend/app/api/documents.py` línea 380

El método `get_cluster_nodes()` se llama pero no existe. Debería usar `get_all_nodes()` o `get_healthy_nodes()`.

### 3. **Listado de documentos inestable**

El listado de documentos de un usuario depende de:
1. Documentos en el nodo local
2. Respuestas de otros nodos (que pueden fallar, timeout, o no responder)

Si un nodo no responde, los documentos ahí almacenados no aparecen. Si luego responde, aparecen. Esto causa la inconsistencia.

### 4. **UserDocumentRegistry no se inicia ni configura peers**

En `dependencies.py`, el `UserDocumentRegistry` se crea pero:
- Nunca se llama a `start()` (que inicia el gossip loop)
- Nunca se llama a `set_peers()` (que configura los nodos a los que hacer gossip)

### 5. **Replicación depende de nodos "healthy" que pueden no existir**

En `replicate_document()`, solo se replica a nodos que están en `get_healthy_nodes()`. Si el ClusterManager no tiene registrados los otros nodos (porque Bully no los ha propagado aún), la replicación falla silenciosamente.

### 6. **No hay endpoint para sincronización de registros de documentos**

No existe un endpoint `/internal/sync/registry` para que los nodos intercambien sus registros de documentos.

### 7. **No hay reconciliación post-partición**

Cuando dos particiones de red se reconectan, no hay mecanismo para:
- Sincronizar usuarios nuevos creados en cada partición
- Sincronizar documentos nuevos
- Detectar y deduplicar documentos idénticos
- Propagar eliminaciones

---

## Tiempos de Sincronización Esperados

### Escenario Normal (todos los nodos conectados):
- **Replicación de documentos:** Inmediata (síncrona al subir)
- **Sincronización de usuarios:** 10 segundos (delay inicial) + tiempo de propagación
- **Sincronización de registro de documentos:** NO FUNCIONA ACTUALMENTE

### Escenario Post-Partición:
- **Detección de reconexión:** 3-5 segundos (heartbeat de Bully)
- **Re-elección de líder:** 10-15 segundos
- **Sincronización completa:** NO IMPLEMENTADA

---

## Plan de Correcciones

### Fase 1: Arreglar infraestructura básica

1. **Implementar gossip real en UserDocumentRegistry**
   - Crear endpoint `/api/v1/internal/sync/registry`
   - Implementar `_send_gossip()` con HTTP calls
   - Recibir y mergear actualizaciones de otros nodos

2. **Arreglar get_cluster_nodes()**
   - Añadir método que devuelve lista de nodos con formato correcto

3. **Iniciar UserDocumentRegistry correctamente**
   - Llamar a `start()` en init_dependencies
   - Configurar peers con `set_peers()`

### Fase 2: Mejorar replicación

4. **Asegurar que ClusterManager conoce todos los nodos**
   - Registrar nodos al detectarlos por Bully
   - Mantener lista actualizada de peers

5. **Retry de replicación en background**
   - Si la replicación falla, encolar para reintento
   - Task periódica que verifica factor de replicación

### Fase 3: Reconciliación post-partición

6. **Implementar sync completo al reconectar**
   - Endpoint para obtener todos los usuarios
   - Endpoint para obtener todos los documentos de registro
   - Merge con vector clocks

7. **Deduplicación de documentos**
   - Hash de contenido para detectar duplicados
   - Preferir el más reciente o usar vector clock

---

## Escenarios de Prueba Requeridos

### Escenario 1: 3 nodos, operación normal
- Crear 3 usuarios (uno por nodo)
- Subir 3 documentos por usuario (9 total)
- Cada documento debe existir en 2 nodos (k=2)
- Buscar debe encontrar documentos de otros usuarios
- Swap de usuarios: listado debe ser consistente

### Escenario 2: 2 nodos, partición de red
- Crear 2 usuarios, subir documentos
- Desconectar ambas máquinas de la red (partición)
- Cada máquina debe funcionar independientemente
- Crear usuarios y subir docs en cada partición
- Reconectar: sincronizar todo
- Verificar: usuarios, documentos, búsquedas, no duplicados
