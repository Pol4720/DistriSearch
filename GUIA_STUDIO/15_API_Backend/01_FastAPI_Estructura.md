# Estructura FastAPI

## Entry point: main.py
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_dependencies(settings)
    yield
    await shutdown_dependencies()

app = FastAPI(title="DistriSearch API", lifespan=lifespan)
```
El lifespan inicializa conexiones a MongoDB, SQLite, Redis y registra el nodo en el cluster.

## Configuración: config.py
Usa `pydantic.BaseSettings` para cargar variables de entorno:
- `NODE_ROLE`, `NODE_ID`, `MONGODB_URI`, `REDIS_URL`, `MASTER_HOST`, etc.

## Routers
Cada módulo en `api/` define un `APIRouter`; se incluyen en `router.py`:
```python
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
```

## Middleware
- `CORSMiddleware`: permite orígenes configurables.
- `GZipMiddleware`: comprime respuestas >1 KB.
- Custom middleware para logging, timing, request-id.