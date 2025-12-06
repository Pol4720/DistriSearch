"""
DistriSearch Slave API - Main Application
==========================================
FastAPI application para nodos Slave.
Gestiona endpoints locales y comunicación con el Master.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import os
import sys
import httpx
import socket
from typing import Dict, Optional
from datetime import datetime

# Asegurar que backend esté en el path
_backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

# Imports desde backend (via path)
from backend import database
from backend.routes import search, register, download, auth, cluster, health
from backend.services import replication_service, node_service
from backend.services.dynamic_replication import get_replication_service
from backend.services.cluster_init import initialize_cluster, shutdown_cluster
from backend.services.reliability_metrics import get_reliability_metrics

# Imports desde core
from core.models import NodeInfo
from core.config import get_cluster_config

# Imports desde cluster (servicios compartidos)
from cluster import get_multicast_service, get_namespace, get_ip_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

cluster_initializer: Optional[object] = None


def get_local_ip() -> str:
    """Obtiene la IP local de la máquina."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación Slave"""
    config = get_cluster_config()
    
    # STARTUP
    logger.info("🚀 Inicializando DistriSearch Slave")
    
    # Verificar conexión a MongoDB
    try:
        database._client.admin.command('ping')
        logger.info("✅ Conexión a MongoDB establecida")
    except Exception as e:
        logger.error(f"❌ Error conectando a MongoDB: {e}")
        raise
    
    # Determinar IP del nodo
    backend_ip = config.external_ip or get_local_ip()
    backend_port = config.network.http_port
    node_id = config.node_id
    node_role = config.node_role.value
    
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
    logger.info(f"✅ Nodo registrado: {node_id} (rol: {node_role}) - {backend_ip}:{backend_port}")

    # Inicializar métricas de confiabilidad
    reliability_metrics = get_reliability_metrics()
    
    # Iniciar servicio de replicación dinámica
    repl_service = get_replication_service()
    
    async def _replication_loop():
        """Sincronización periódica de consistencia eventual"""
        interval = config.replication.sync_interval_seconds
        while True:
            try:
                await repl_service.synchronize_eventual_consistency()
            except Exception as e:
                logger.error(f"Error en sincronización: {e}")
            finally:
                await asyncio.sleep(interval)
    
    replication_task = asyncio.create_task(_replication_loop())

    async def _maintenance_loop():
        """Loop de mantenimiento: heartbeats, timeouts, recuperación"""
        interval = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "300"))
        
        while True:
            try:
                # Verificar timeouts
                timed_out_nodes = node_service.check_node_timeouts()
                
                # Mantener heartbeat de este nodo
                node_service.update_node_heartbeat(node_id)
                
                # Recuperación automática de nodos caídos
                if timed_out_nodes > 0:
                    logger.warning(f"⚠️ Detectados {timed_out_nodes} nodos caídos")
                    
                    offline_nodes = [
                        n for n in database.get_all_nodes() 
                        if n.get('status') == 'offline'
                    ]
                    
                    for node in offline_nodes:
                        try:
                            await reliability_metrics.record_failure(
                                node['node_id'],
                                failure_type="crash",
                                details={"reason": "heartbeat_timeout"}
                            )
                            
                            result = await repl_service.recover_from_node_failure(node['node_id'])
                            logger.info(f"📊 Recuperación de {node['node_id']}: {result}")
                            
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

    # Inicializar servicios de naming
    namespace = get_namespace()
    logger.info("✅ Namespace jerárquico inicializado")
    
    ip_cache = get_ip_cache()
    logger.info("✅ IP Cache inicializado")
    
    # Callbacks para multicast discovery
    async def on_node_discovered(node_info: Dict):
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
    
    async def on_node_lost(node_info: Dict):
        """Callback cuando se pierde un nodo"""
        logger.warning(f"⚠️ Nodo perdido: {node_info['node_id']}")
    
    multicast = await get_multicast_service(
        node_id,
        backend_port,
        backend_ip,
        on_node_discovered,
        on_node_lost
    )
    
    multicast_task = asyncio.create_task(multicast.start())
    logger.info("✅ Multicast discovery iniciado")
    
    background_tasks = [
        replication_task,
        maintenance_task,
        discovery_task,
        multicast_task,
    ]
    
    # Yield control (aplicación corriendo)
    yield
    
    # SHUTDOWN
    logger.info("🛑 Deteniendo DistriSearch Slave...")
    
    database.update_node_status(node_id, "offline")
    
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    await shutdown_cluster()
    multicast.stop()
    
    logger.info("✅ DistriSearch Slave detenido correctamente")


def create_app() -> FastAPI:
    """Factory function para crear la aplicación FastAPI."""
    application = FastAPI(
        title="DistriSearch Slave API",
        description="API para nodo Slave - Búsqueda distribuida con MongoDB",
        version="3.0.0",
        lifespan=lifespan
    )
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Registrar routers
    application.include_router(auth.router)
    application.include_router(search.router)
    application.include_router(register.router)
    application.include_router(download.router)
    application.include_router(cluster.router)
    application.include_router(health.router)
    
    @application.get("/")
    async def root():
        return {
            "message": "DistriSearch Slave API",
            "version": "3.0.0",
            "architecture": "Master-Slave"
        }
    
    return application


# App singleton
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_cluster_config()
    ssl_enabled = config.security.enable_ssl
    
    host = config.network.host
    port = config.network.http_port
    local_ip = get_local_ip()
    protocol = "https" if ssl_enabled else "http"
    
    logger.info("=" * 60)
    logger.info("DistriSearch Slave v3.0 - MASTER-SLAVE ARCHITECTURE")
    logger.info("=" * 60)
    logger.info(f"Node ID: {config.node_id}")
    logger.info(f"Role: {config.node_role.value}")
    logger.info(f"Protocolo: {protocol.upper()}")
    logger.info(f"Host: {host}")
    logger.info(f"Puerto: {port}")
    logger.info(f"IP Local: {local_ip}")
    logger.info(f"MongoDB: {config.database.uri}")
    logger.info("-" * 60)
    logger.info(f"API: {protocol}://{local_ip}:{port}")
    logger.info(f"Docs: {protocol}://{local_ip}:{port}/docs")
    logger.info("=" * 60)
    
    uvicorn_config = {
        "app": "slave.api.main:app",
        "host": host,
        "port": port,
        "reload": os.getenv("RELOAD", "false").lower() in {"true", "1", "yes"},
    }
    
    if ssl_enabled:
        cert_file = config.security.ssl_cert_file
        key_file = config.security.ssl_key_file
        if os.path.exists(cert_file) and os.path.exists(key_file):
            uvicorn_config["ssl_certfile"] = cert_file
            uvicorn_config["ssl_keyfile"] = key_file
    
    uvicorn.run(**uvicorn_config)
