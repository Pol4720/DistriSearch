# 🔍 Análisis de los Volúmenes en DistriSearch

## ¿Son los volúmenes Docker una "trampa" en sistemas distribuidos?

**Respuesta corta: NO, son NECESARIOS y LEGÍTIMOS**

---

## Volúmenes que usa el sistema

En los scripts de despliegue (`05-deploy-nodes-ha.sh`), cada nodo usa:

```bash
# Para cada nodo i:
--mount type=volume,source="node${i}-mongo-data",target=/data/db     # MongoDB
--mount type=volume,source="node${i}-redis-data",target=/data        # Redis
--mount type=volume,source="node${i}-sqlite",target=/app/data/sqlite # SQLite
--mount type=volume,source="node${i}-data",target=/app/data          # Datos app
--mount type=volume,source="node${i}-docs",target=/app/data/documents # Documentos
```

---

## Propósito de cada volumen

| Volumen | Propósito | ¿Por qué es necesario? |
|---------|-----------|----------------------|
| `node${i}-mongo-data` | Datos de MongoDB | **Base de datos** - Sin esto, se perdería toda la data al reiniciar |
| `node${i}-redis-data` | Cache Redis | **Cache/coordinación** - Mantiene estado entre reinicios |
| `node${i}-sqlite` | Registry de usuarios | **Índice de documentos por usuario** - Para consistencia eventual |
| `node${i}-docs` | Archivos físicos | **Los PDFs, TXTs subidos** - Los archivos reales |

---

## ¿Cuándo sería "trampa"?

Sería trampa si:

- ❌ El volumen fuera **compartido entre nodos** (network volume como NFS) - haría la "distribución" falsa
- ❌ Usaran almacenamiento **externo centralizado** (S3, MinIO compartido) - no habría distribución real
- ❌ Todos los nodos escribieran al **mismo volumen** - sería un sistema centralizado disfrazado

---

## ¿Por qué NO es trampa en DistriSearch?

✅ **Cada nodo tiene sus propios volúmenes locales** (`node1-mongo-data`, `node2-mongo-data`, etc.)

✅ **Los datos se replican mediante el código** (gossip protocol, replication factor k=2)

✅ **Si un nodo se desconecta, sus datos están en SU volumen local** - puede seguir funcionando independientemente

✅ **La sincronización es programática**, no por compartir almacenamiento

✅ **Cada máquina física tiene su stack completo aislado**

---

## Diagrama de arquitectura de almacenamiento

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLUSTER DISTRISEARCH                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│   │     HOST A       │  │     HOST B       │  │     HOST C       │  │
│   │                  │  │                  │  │                  │  │
│   │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │
│   │ │   Node 1     │ │  │ │   Node 2     │ │  │ │   Node 3     │ │  │
│   │ │  DistriSearch│ │  │ │  DistriSearch│ │  │ │  DistriSearch│ │  │
│   │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │
│   │        │         │  │        │         │  │        │         │  │
│   │        ▼         │  │        ▼         │  │        ▼         │  │
│   │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │
│   │ │node1-mongodb │ │  │ │node2-mongodb │ │  │ │node3-mongodb │ │  │
│   │ │   VOLUMEN    │ │  │ │   VOLUMEN    │ │  │ │   VOLUMEN    │ │  │
│   │ │   LOCAL      │ │  │ │   LOCAL      │ │  │ │   LOCAL      │ │  │
│   │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │
│   │                  │  │                  │  │                  │  │
│   │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │
│   │ │ node1-docs   │ │  │ │ node2-docs   │ │  │ │ node3-docs   │ │  │
│   │ │   VOLUMEN    │ │  │ │   VOLUMEN    │ │  │ │   VOLUMEN    │ │  │
│   │ │   LOCAL      │ │  │ │   LOCAL      │ │  │ │   LOCAL      │ │  │
│   │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                      │
│   ════════════════════════════════════════════════════════════════   │
│   REPLICACIÓN VÍA SOFTWARE (Gossip Protocol, HTTP, k=2)              │
│   NO hay volúmenes compartidos entre hosts                           │
│   ════════════════════════════════════════════════════════════════   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Analogía simple

> Es como si cada servidor de Google tuviera su propio disco duro. Los datos se copian entre servidores mediante software, no porque compartan el mismo disco. Los volúmenes Docker son equivalentes a "discos duros locales" de cada nodo.

---

## Mecanismos de replicación en DistriSearch

La distribución de datos se logra mediante **código**, no mediante almacenamiento compartido:

1. **Replicación de documentos** (`cluster_manager.replicate_document`)
   - Cuando se sube un documento, se replica a k-1 nodos adicionales
   - La replicación es via HTTP POST con el contenido del documento y archivo

2. **Gossip Protocol** (`UserDocumentRegistry`)
   - Cada nodo mantiene registro de qué documentos pertenecen a qué usuarios
   - Se sincroniza periódicamente con otros nodos via HTTP

3. **Sincronización post-partición**
   - Cuando los nodos se reconectan, intercambian registros
   - Vector clocks resuelven conflictos
   - Deduplicación por content_hash evita duplicados

---

## Conclusión

**Los volúmenes son infraestructura necesaria, no trampa.**

Lo que hace "distribuido" al sistema es:
- La **replicación programática** de datos entre nodos
- El **protocolo gossip** para sincronización
- La **tolerancia a particiones** donde cada nodo funciona independientemente
- La **reconciliación automática** cuando se restaura conectividad

Los volúmenes simplemente proporcionan **persistencia local** a cada nodo, exactamente igual que un disco duro en un servidor físico.
