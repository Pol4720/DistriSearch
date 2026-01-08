# Endpoints Principales

## Documentos
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /api/v1/upload | Subir documento (multipart, hasta **500MB**, cualquier tipo) |
| GET | /api/v1/documents | Listar docs del usuario |
| GET | /api/v1/documents/{id} | Obtener metadatos del documento |
| GET | /api/v1/documents/{id}/download | **Descargar archivo original** |
| DELETE | /api/v1/documents/{id} | Eliminar documento |

### Tipos de archivo soportados
- **Texto/Código**: TXT, MD, JSON, XML, CSV, PY, JS, TS, HTML, CSS, etc.
- **Documentos**: PDF, DOCX, XLSX, PPTX
- **Binarios**: Cualquier tipo (búsqueda por nombre de archivo)

### Límites
- Tamaño máximo: **500 MB** por archivo
- Archivos binarios sin contenido extraíble: indexación por nombre de archivo

## Búsqueda
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /api/v1/search?q=... | Búsqueda semántica |
| POST | /api/v1/search | Búsqueda con filtros avanzados |

### Búsqueda en archivos binarios
Para archivos sin contenido textual, la búsqueda se realiza sobre:
- Nombre del archivo
- Extensión
- Metadatos (fecha, tamaño, propietario)

## Cluster (admin)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /api/v1/cluster/nodes | Lista nodos |
| GET | /api/v1/cluster/partitions | Particiones VP-Tree |
| POST | /api/v1/cluster/rebalance | Disparar rebalanceo |

## Health
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /health | Liveness simple |
| GET | /api/v1/health/live | Health check para Docker/Swarm |
| GET | /api/v1/health | Detallado (DB, Redis) |

## WebSocket
- `/ws/dashboard`: eventos de cluster en tiempo real.
