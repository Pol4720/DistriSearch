# Trade-offs de Diseño en DistriSearch

## Decisiones clave
| Decisión | Razón |
|----------|-------|
| SQLite + Raft para usuarios | Consistencia fuerte evita credenciales divergentes |
| MongoDB local | Disponibilidad; sin SPOF |
| Gossip para registry | Baja latencia de lectura, tolerancia a particiones |
| Replicación por afinidad | Copias en nodos con docs similares para búsquedas rápidas |

## Consistencia vs latencia
- Escritura de usuario: espera commit Raft (~50–100 ms con mayoría local).
- Subida de documento: respuesta inmediata tras guardar local; replicación async.
- Búsqueda: lee caché/índice local; resultados en <100 ms típicamente.

## Recuperación tras partición
1. Raft detecta nuevo quorum y elige líder (si cambió).
2. Gossip sincroniza UserDocumentRegistry.
3. Re-replicación de documentos si alguna réplica se perdió.
4. VP-Tree actualiza con nodos disponibles.

## Garantías ofrecidas
- Documentos subidos nunca se pierden si al menos un nodo con copia sobrevive.
- Usuarios autenticados en cualquier nodo que tenga la copia SQLite.
- Búsquedas devuelven resultados del subconjunto accesible.