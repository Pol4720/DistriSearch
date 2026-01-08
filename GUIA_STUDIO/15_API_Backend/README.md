# API Backend de DistriSearch

El backend está construido con **FastAPI** y expone endpoints REST para gestión de documentos, búsqueda, autenticación y administración del cluster.

## Características
- Async/await nativo para alta concurrencia.
- Documentación automática en `/docs` (Swagger) y `/redoc`.
- Validación con Pydantic.
- Middleware: CORS, GZip, rate limiting.
- WebSocket para actualizaciones en tiempo real.

## Estructura
```
backend/app/
├── main.py           # Entry point, lifespan
├── config.py         # Settings via env vars
├── api/
│   ├── router.py     # Agrupa todos los routers
│   ├── auth.py       # Login, registro, JWT
│   ├── documents.py  # CRUD documentos
│   ├── search.py     # Búsqueda semántica
│   ├── cluster.py    # Admin cluster
│   ├── health.py     # Health checks
│   └── websocket.py  # WS para dashboard
├── storage/          # MongoDB, SQLite, Redis
├── core/             # Vectorización, particionamiento
└── distributed/      # Raft, Gossip, comunicación
```

Detalles en los siguientes archivos.