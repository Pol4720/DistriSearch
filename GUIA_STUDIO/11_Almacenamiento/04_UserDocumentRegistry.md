# UserDocumentRegistry

## Propósito
Mapear qué documentos pertenecen a qué usuario y en qué nodo están, permitiendo responder «qué documentos tiene el usuario X» desde cualquier nodo.

## Por qué no en MongoDB
Necesita acceso cross-partition: un usuario puede tener docs en varios nodos. Centralizar crearía SPOF.

## Modelo de datos
```python
@dataclass
class DocumentRegistryEntry:
    user_id: str
    document_id: str
    node_id: str
    title: Optional[str]
    is_deleted: bool
    vector_clock: Dict[str, int]
```

## Consistencia eventual (Gossip)
- Cada nodo mantiene su copia local en SQLite.
- Periódicamente intercambia entradas con peers aleatorios.
- Conflictos se resuelven por vector clocks (last-write-wins si empatan).

## Operaciones
| Método | Acción |
|--------|--------|
| `register_document` | Agrega entrada local y propaga |
| `unregister_document` | Soft-delete (tombstone) |
| `get_user_documents` | Lista docs de un usuario desde copia local |
| `sync_with_peer` | Intercambio Gossip |

## Beneficios
- Lectura local instantánea.
- Tolerante a particiones: eventualmente converge al reunirse.