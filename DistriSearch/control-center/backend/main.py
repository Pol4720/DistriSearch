"""
Control Center Backend - Main Application
Centro de Control para DistriSearch: Monitoreo y gestión del sistema distribuido
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import os
from datetime import datetime

from routers import cluster, nodes, tests, metrics
from services.cluster_service import ClusterService
from services.docker_service import DockerService
from services.websocket_manager import WebSocketManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global services
cluster_service: ClusterService = None
docker_service: DockerService = None
ws_manager: WebSocketManager = None
background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global cluster_service, docker_service, ws_manager
    
    logger.info("🚀 Iniciando Control Center...")
    
    # Initialize services
    distrisearch_url = os.getenv("DISTRISEARCH_URL", "http://localhost:8000")
    docker_service = DockerService()
    cluster_service = ClusterService(distrisearch_url, docker_service)
    ws_manager = WebSocketManager()
    
    # Start background monitoring
    monitoring_task = asyncio.create_task(monitor_cluster())
    background_tasks.add(monitoring_task)
    monitoring_task.add_done_callback(background_tasks.discard)
    
    logger.info("✅ Control Center iniciado correctamente")
    
    yield
    
    # Cleanup
    logger.info("🛑 Deteniendo Control Center...")
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    logger.info("👋 Control Center detenido")


async def monitor_cluster():
    """Background task to monitor cluster status."""
    while True:
        try:
            if cluster_service and ws_manager:
                status = await cluster_service.get_cluster_status()
                if status:
                    await ws_manager.broadcast({
                        "type": "cluster_status",
                        "data": status,
                        "timestamp": datetime.utcnow().isoformat()
                    })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en monitoreo: {e}")
        
        await asyncio.sleep(2)  # Update every 2 seconds


# Create FastAPI app
app = FastAPI(
    title="DistriSearch Control Center",
    description="Centro de Control para monitoreo y pruebas del sistema distribuido DistriSearch",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cluster.router, prefix="/api/cluster", tags=["Cluster"])
app.include_router(nodes.router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(tests.router, prefix="/api/tests", tags=["Tests"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])


@app.get("/api/health")
async def health_check():
    """Health check del Control Center."""
    return {
        "status": "healthy",
        "service": "control-center",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para actualizaciones en tiempo real."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Recibir comandos desde el frontend
            data = await websocket.receive_json()
            
            if data.get("action") == "subscribe":
                logger.info(f"Cliente suscrito a: {data.get('channel')}")
            elif data.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# Dependency injection helpers
def get_cluster_service() -> ClusterService:
    return cluster_service


def get_docker_service() -> DockerService:
    return docker_service


def get_ws_manager() -> WebSocketManager:
    return ws_manager


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="info"
    )
