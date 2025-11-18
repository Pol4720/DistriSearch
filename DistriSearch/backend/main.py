from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from routes import search, register, download
from routes import central  # nuevo router para modo centralizado
from routes import auth, tasks  # nuevos routers para autenticación y tareas
from services import central_service
from services import replication_service
from services import node_service
from user_database import init_user_db  # inicialización de la base de datos de usuarios
import asyncio

app = FastAPI(
    title="DistriSearch API",
    description="API centralizada para búsqueda distribuida de archivos",
    version="0.1.0"
)

# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limitar a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(search.router)
app.include_router(register.router)
app.include_router(download.router)
app.include_router(central.router)
app.include_router(auth.router)
app.include_router(tasks.router)

@app.on_event("startup")
async def on_startup():
    # Inicializar base de datos de usuarios
    init_user_db()

    # Auto-scan opcional del modo central si está habilitado por entorno
    if os.getenv("CENTRAL_AUTO_SCAN", "false").lower() in {"1", "true", "yes"}:
        try:
            central_service.index_central_folder(os.getenv("CENTRAL_SHARED_FOLDER"))
        except Exception:
            # Evitar que falle el arranque por problemas al escanear
            pass

    # Lanzar tareas de mantenimiento en segundo plano (replicación y timeouts)
    async def _maintenance_loop():
        interval = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "300"))  # 5 min por defecto
        while True:
            try:
                # Marcar nodos con timeout como offline
                try:
                    node_service.check_node_timeouts()
                except Exception:
                    pass
                # Ejecutar una pasada de replicación básica
                try:
                    replication_service.replicate_missing_files(batch=50)
                except Exception:
                    pass
            finally:
                await asyncio.sleep(interval)

    try:
        asyncio.create_task(_maintenance_loop())
    except Exception:
        pass

@app.get("/")
async def root():
    return {"message": "Bienvenido a DistriSearch API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # Configuración SSL para HTTPS
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")

    uvicorn_kwargs = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True
    }

    if ssl_keyfile and ssl_certfile:
        uvicorn_kwargs.update({
            "ssl_keyfile": ssl_keyfile,
            "ssl_certfile": ssl_certfile
        })
        print("Running with HTTPS enabled")
    else:
        print("Running with HTTP (set SSL_KEYFILE and SSL_CERTFILE env vars for HTTPS)")

    uvicorn.run(**uvicorn_kwargs)
