# Almacenamiento en DistriSearch

DistriSearch usa una estrategia de almacenamiento multi-capa diseñada para disponibilidad y tolerancia a particiones (AP).

## Capas de almacenamiento
| Capa | Tecnología | Datos | Consistencia |
|------|------------|-------|--------------|
| Metadatos críticos | SQLite + Raft | Usuarios, nodos, particiones | Fuerte (mayoría) |
| Documentos | MongoDB local por nodo | Contenido, vectores | Local |
| Cache | Redis local | Resultados de búsqueda | Efímero |
| Registro usuario-docs | UserDocumentRegistry | Mapeo user→docs | Eventual (Gossip) |

## Por qué almacenamiento local
- Cada slave tiene su propio MongoDB: no hay punto único de fallo.
- Durante particiones, el nodo sigue sirviendo sus documentos.
- El VP-Tree del master decide la ubicación; la replicación crea copias en otros nodos.

En los siguientes archivos se profundiza cada componente.