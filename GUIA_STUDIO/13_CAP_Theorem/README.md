# Teorema CAP en DistriSearch

El teorema CAP establece que un sistema distribuido sólo puede garantizar dos de tres propiedades simultáneamente:
- **C**onsistency: todos los nodos ven los mismos datos al mismo tiempo.
- **A**vailability: toda petición recibe respuesta (aunque no sea la más reciente).
- **P**artition tolerance: el sistema sigue funcionando pese a pérdida de mensajes entre nodos.

## Elección de DistriSearch: AP
DistriSearch prioriza **Disponibilidad** y **Tolerancia a particiones**:
- Un sistema de búsqueda debe responder aunque algunos nodos estén desconectados.
- Consistencia eventual es aceptable para documentos y resultados de búsqueda.
- Donde se requiere consistencia fuerte (usuarios, particiones) se usa Raft.

## Resumen por componente
| Componente | Modelo CAP | Justificación |
|------------|------------|---------------|
| SQLite + Raft | CP | Requiere mayoría para escribir |
| MongoDB local | AP | Cada nodo sirve sus datos |
| UserDocumentRegistry | AP | Gossip converge eventualmente |
| Búsqueda | AP | Responde con datos locales |

Detalles en los siguientes archivos.