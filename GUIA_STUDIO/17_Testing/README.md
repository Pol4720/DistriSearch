# Testing en DistriSearch

La suite de pruebas cubre desde unidades pequeñas hasta escenarios distribuidos complejos.

## Estructura
```
tests/
├── unit/           # Pruebas unitarias (funciones, clases)
├── integration/    # Pruebas de integración (API, DB)
└── distributed/    # Pruebas de cluster (Raft, rebalanceo)
```

## Herramientas
| Herramienta | Uso |
|-------------|-----|
| pytest | Runner principal |
| pytest-asyncio | Tests async |
| pytest-cov | Cobertura |
| httpx | Cliente async para API |
| testcontainers | MongoDB/Redis en contenedor |

## Ejecución
```bash
pytest tests/unit -v
pytest tests/integration -v --cov=backend/app
pytest tests/distributed -v -x  # falla rápido
```

## Configuración
- `pytest.ini`: markers, opciones por defecto.
- `conftest.py`: fixtures compartidas (app, client, db).

Detalles en los siguientes archivos.