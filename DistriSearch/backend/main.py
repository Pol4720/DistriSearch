from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import os
import httpx
from typing import Dict, Optional
from datetime import datetime

from routes import search, register, download, auth, cluster, health
from services import replication_service, node_service
from services.dynamic_replication import get_replication_service
from services.naming.multicast_discovery import get_multicast_service
from services.naming.hierarchical_naming import get_namespace
from services.naming.ip_cache import get_ip_cache
from services.cluster_init import initialize_cluster, shutdown_cluster
from models import NodeInfo
import database
import uvicorn
import socket
from services.reliability_metrics import get_reliability_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ NUEVO: Lifespan context manager
cluster_initializer: Optional[object] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # STARTUP
    logger.info("🚀 Inicializando DistriSearch")
    
    # Verificar conexión a MongoDB
    try:
        database._client.admin.command('ping')
        logger.info("✅ Conexión a MongoDB establecida")
    except Exception as e:
        logger.error(f"❌ Error conectando a MongoDB: {e}")
        raise
    
    # Auto-registrar este nodo en el cluster
    backend_ip = os.getenv("EXTERNAL_IP")
    if not backend_ip:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            backend_ip = s.getsockname()[0]
            s.close()
        except Exception:
            backend_ip = "127.0.0.1"
    
    backend_port = int(os.getenv("BACKEND_PORT", "8000"))
    node_id = os.getenv("NODE_ID", "node_1")
    node_role = os.getenv("NODE_ROLE", "slave")
    
    # Registrar este nodo en el cluster
    this_node = NodeInfo(
        node_id=node_id,
        name=f"Node {node_id}",
        ip_address=backend_ip,
        port=backend_port,
        status="online",
        last_seen=datetime.now(),
        shared_files_count=0
    )
    
    database.register_node(this_node)
    logger.info(f"✅ Nodo registrado en cluster: {node_id} (rol: {node_role}) - {backend_ip}:{backend_port}")

    # Inicializar métricas de confiabilidad
    reliability_metrics = get_reliability_metrics()
    
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
    
    replication_task = asyncio.create_task(_replication_loop())

    async def _maintenance_loop():
        interval = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "300"))
        
        while True:
            try:
                # Verificar timeouts
                timed_out_nodes = node_service.check_node_timeouts()
                
                # Mantener heartbeat de este nodo
                node_service.update_node_heartbeat(node_id)
                
                # ✅ NUEVO: Recuperación automática de nodos caídos
                if timed_out_nodes > 0:
                    logger.warning(f"⚠️ Detectados {timed_out_nodes} nodos caídos - Iniciando recuperación")
                    
                    # Obtener nodos offline
                    offline_nodes = [
                        n for n in database.get_all_nodes() 
                        if n.get('status') == 'offline'
                    ]
                    
                    for node in offline_nodes:
                        try:
                            # Registrar falla
                            await reliability_metrics.record_failure(
                                node['node_id'],
                                failure_type="crash",  # Timeout = crash failure
                                details={"reason": "heartbeat_timeout"}
                            )
                            
                            # Recuperar archivos
                            result = await repl_service.recover_from_node_failure(node['node_id'])
                            logger.info(f"📊 Recuperación de {node['node_id']}: {result}")
                            
                            # Registrar MTTR
                            if result.get('duration_seconds'):
                                await reliability_metrics.record_recovery(
                                    node['node_id'],
                                    result['duration_seconds']
                                )
                            
                        except Exception as e:
                            logger.error(f"Error recuperando {node['node_id']}: {e}")
                
                # Replicación preventiva
                replication_service.replicate_missing_files(batch=50)
                
            except Exception as e:
                logger.error(f"Error en mantenimiento: {e}")
            finally:
                await asyncio.sleep(interval)
    
    maintenance_task = asyncio.create_task(_maintenance_loop())
    
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
    
    discovery_task = asyncio.create_task(_node_discovery_loop())

    # Inicializar cluster Master-Slave (Heartbeat + Bully election)
    global cluster_initializer
    cluster_initializer = await initialize_cluster()

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

    # Inicializar namespace jerárquico
    namespace = get_namespace()
    logger.info("✅ Namespace jerárquico inicializado")
    
    # Inicializar IP cache
    ip_cache = get_ip_cache()
    logger.info("✅ IP Cache inicializado")
    
    # Inicializar multicast discovery
    async def on_node_discovered_callback(node_info: Dict):
        """Callback cuando se descubre un nodo nuevo"""
        try:
            node_data = {
                "node_id": node_info['node_id'],
                "ip_address": node_info['ip_address'],
                "port": node_info['port'],
                "status": "online"
            }
            
            node_service.register_node(NodeInfo(**node_data))
            logger.info(f"✅ Nodo auto-registrado vía multicast: {node_info['node_id']}")
            
        except Exception as e:
            logger.error(f"Error registrando nodo descubierto: {e}")
    
    async def on_node_lost_callback(node_info: Dict):
        """Callback cuando se pierde un nodo"""
        logger.warning(f"⚠️ Nodo perdido: {node_info['node_id']}")
    
    multicast = await get_multicast_service(
        node_id,
        backend_port,
        backend_ip,
        on_node_discovered_callback,
        on_node_lost_callback
    )
    
    # Iniciar multicast discovery
    multicast_task = asyncio.create_task(multicast.start())
    logger.info("✅ Multicast discovery iniciado")
    
    # Consolidar tareas para shutdown limpio
    background_tasks = [
        replication_task,
        maintenance_task,
        discovery_task,
        multicast_task,
    ]
    
    # ✅ Yield control (aplicación corriendo)
    yield
    
    # SHUTDOWN
    logger.info("🛑 Deteniendo DistriSearch...")
    
    # Marcar este nodo como offline antes de detener
    database.update_node_status(node_id, "offline")
    
    # Cancelar todas las tareas
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Detener servicios del cluster
    await shutdown_cluster()

    # Detener multicast
    multicast.stop()
    
    logger.info("✅ DistriSearch detenido correctamente")


# ✅ Crear app con lifespan
app = FastAPI(
    title="DistriSearch API",
    description="API para búsqueda distribuida de archivos con MongoDB",
    version="2.0.0",
    lifespan=lifespan  # ✅ NUEVO: Usar lifespan en lugar de on_event
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
app.include_router(cluster.router)  # Nuevos endpoints del cluster Master-Slave
app.include_router(health.router)  # Health check endpoints

@app.get("/")
async def root():
    return {"message": "DistriSearch API - MongoDB + Replicación Dinámica", "version": "2.0.0"}

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
