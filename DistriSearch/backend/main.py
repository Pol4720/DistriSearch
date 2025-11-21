from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import socket
from routes import search, register, download, auth
from services import replication_service
from services.dynamic_replication import get_replication_service
from services import node_service
import database  # MongoDB únicamente
import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DistriSearch API",
    description="API para búsqueda distribuida de archivos con MongoDB",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(register.router)
app.include_router(download.router)

@app.on_event("startup")
async def on_startup():
    """Inicialización - Solo MongoDB, sin SQLite."""
    logger.info("🚀 Inicializando DistriSearch con MongoDB")
    
    # Verificar conexión a MongoDB
    try:
        database._client.admin.command('ping')
        logger.info("✅ Conexión a MongoDB establecida")
    except Exception as e:
        logger.error(f"❌ Error conectando a MongoDB: {e}")
        raise
    
    # Iniciar servicio de replicación dinámica
    repl_service = get_replication_service()
    
    async def _replication_loop():
        """Sincronización periódica de consistencia eventual"""
        interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
        while True:
            try:
                await repl_service.synchronize_eventual_consistency()
            except Exception as e:
                logger.error(f"Error en sincronización: {e}")
            finally:
                await asyncio.sleep(interval)
    
    asyncio.create_task(_replication_loop())

    async def _maintenance_loop():
        interval = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "300"))
        while True:
            try:
                node_service.check_node_timeouts()
                replication_service.replicate_missing_files(batch=50)
            except Exception as e:
                logger.error(f"Error en mantenimiento: {e}")
            finally:
                await asyncio.sleep(interval)
    
    asyncio.create_task(_maintenance_loop())
    
    async def _node_discovery_loop():
        """Descubre nodos dinámicamente."""
        interval = int(os.getenv("NODE_DISCOVERY_INTERVAL", "30"))
        while True:
            try:
                node_service.check_node_timeouts()
                await _probe_unknown_nodes()
            except Exception as e:
                logger.error(f"Error en discovery loop: {e}")
            finally:
                await asyncio.sleep(interval)
    
    asyncio.create_task(_node_discovery_loop())

    async def _probe_unknown_nodes():
        """Intenta contactar nodos con estado 'unknown'."""
        unknown_nodes = [n for n in database.get_all_nodes() 
                        if n.get("status") == "unknown"]
        
        for node in unknown_nodes:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    url = f"http://{node['ip_address']}:{node['port']}/health"
                    response = await client.get(url)
                    if response.status_code == 200:
                        node_service.update_node_heartbeat(node["node_id"])
                        logger.info(f"Nodo {node['node_id']} descubierto como ONLINE")
            except Exception:
                pass

@app.get("/")
async def root():
    return {"message": "DistriSearch API - MongoDB + Replicación Dinámica", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "distributed", "database": "mongodb"}

def get_local_ip():
    """Obtiene la IP local de la máquina."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ssl_enabled = os.getenv("ENABLE_SSL", "false").lower() in {"true", "1", "yes"}
    ssl_certfile = os.getenv("SSL_CERT_FILE", "../certs/distrisearch.crt")
    ssl_keyfile = os.getenv("SSL_KEY_FILE", "../certs/distrisearch.key")
    
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    
    local_ip = get_local_ip()
    protocol = "https" if ssl_enabled else "http"
    
    logger.info("=" * 60)
    logger.info("DistriSearch Backend v2.0 - MONGODB + REPLICACIÓN DINÁMICA")
    logger.info("=" * 60)
    logger.info(f"Protocolo: {protocol.upper()}")
    logger.info(f"Host: {host}")
    logger.info(f"Puerto: {port}")
    logger.info(f"IP Local (LAN): {local_ip}")
    logger.info(f"Base de Datos: MongoDB (URI: {os.getenv('MONGO_URI', 'mongodb://localhost:27017')})")
    
    if ssl_enabled:
        logger.info(f"SSL Habilitado: ✓")
        if not os.path.exists(ssl_certfile):
            logger.warning(f"⚠ Certificado no encontrado: {ssl_certfile}")
        if not os.path.exists(ssl_keyfile):
            logger.warning(f"⚠ Clave privada no encontrada: {ssl_keyfile}")
    else:
        logger.info(f"SSL Habilitado: ✗")
    
    logger.info("-" * 60)
    logger.info(f"Acceso Local: {protocol}://localhost:{port}")
    logger.info(f"Acceso Red (LAN): {protocol}://{local_ip}:{port}")
    logger.info(f"Documentación: {protocol}://localhost:{port}/docs")
    logger.info("=" * 60)
    
    uvicorn_config = {
        "app": "main:app",
        "host": host,
        "port": port,
        "reload": os.getenv("RELOAD", "false").lower() in {"true", "1", "yes"},
    }
    
    if ssl_enabled and os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        uvicorn_config["ssl_certfile"] = ssl_certfile
        uvicorn_config["ssl_keyfile"] = ssl_keyfile
    
    uvicorn.run(**uvicorn_config)
