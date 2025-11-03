from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import socket
from routes import search, register, download
from routes import central  # nuevo router para modo centralizado
from routes import dht
from services import central_service
from services import replication_service
from services import node_service
from services import dht_service
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
app.include_router(dht.router)

@app.on_event("startup")
async def on_startup():
    # Auto-iniciar DHT si está habilitado por entorno
    if os.getenv("DHT_AUTO_START", "false").lower() in {"1", "true", "yes"}:
        try:
            logger.info("🧩 Iniciando DHT automáticamente (DHT_AUTO_START=true)...")
            dht_service.service.start()
            logger.info("✅ DHT iniciada en modo: %s", dht_service.service.mode)
            
            # Auto-join a seed si está configurado
            seed_ip = os.getenv("DHT_SEED_IP")
            if seed_ip:
                seed_port = int(os.getenv("DHT_SEED_PORT", "2000"))
                logger.info("🔗 Uniéndose a seed DHT: %s:%s", seed_ip, seed_port)
                try:
                    result = dht_service.service.join(seed_ip, seed_port)
                    logger.info("✅ Unión a red DHT completada: %s", result)
                except Exception as join_err:
                    logger.warning("⚠️ No se pudo unir a la red DHT: %s", join_err)
        except Exception as e:
            logger.warning("⚠️ Error al iniciar DHT automáticamente: %s", e)
    
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

def get_local_ip():
    """Obtiene la IP local de la máquina para acceso desde red externa."""
    try:
        # Crear un socket para obtener la IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    # Configuración SSL/TLS
    ssl_enabled = os.getenv("ENABLE_SSL", "false").lower() in {"true", "1", "yes"}
    ssl_certfile = os.getenv("SSL_CERT_FILE", "../certs/distrisearch.crt")
    ssl_keyfile = os.getenv("SSL_KEY_FILE", "../certs/distrisearch.key")
    
    # Configuración de host y puerto
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Información de red
    local_ip = get_local_ip()
    protocol = "https" if ssl_enabled else "http"
    
    logger.info("=" * 60)
    logger.info("DistriSearch Backend Iniciando")
    logger.info("=" * 60)
    logger.info(f"Protocolo: {protocol.upper()}")
    logger.info(f"Host: {host}")
    logger.info(f"Puerto: {port}")
    logger.info(f"IP Local (LAN): {local_ip}")
    
    if ssl_enabled:
        logger.info(f"SSL Habilitado: ✓")
        logger.info(f"Certificado: {ssl_certfile}")
        logger.info(f"Clave privada: {ssl_keyfile}")
        
        # Verificar que los archivos existen
        if not os.path.exists(ssl_certfile):
            logger.warning(f"⚠ Certificado no encontrado: {ssl_certfile}")
            logger.warning("Ejecuta: python scripts/generate_ssl_certs.ps1")
        if not os.path.exists(ssl_keyfile):
            logger.warning(f"⚠ Clave privada no encontrada: {ssl_keyfile}")
    else:
        logger.info(f"SSL Habilitado: ✗ (Para habilitar: ENABLE_SSL=true)")
    
    logger.info("-" * 60)
    logger.info(f"Acceso Local: {protocol}://localhost:{port}")
    logger.info(f"Acceso Red (LAN): {protocol}://{local_ip}:{port}")
    logger.info(f"Documentación: {protocol}://localhost:{port}/docs")
    logger.info("=" * 60)
    
    # Configuración de uvicorn
    uvicorn_config = {
        "app": "main:app",
        "host": host,
        "port": port,
        "reload": os.getenv("RELOAD", "false").lower() in {"true", "1", "yes"},
    }
    
    # Agregar SSL si está habilitado
    if ssl_enabled and os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        uvicorn_config["ssl_certfile"] = ssl_certfile
        uvicorn_config["ssl_keyfile"] = ssl_keyfile
    
    uvicorn.run(**uvicorn_config)
