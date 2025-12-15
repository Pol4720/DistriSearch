"""
DistriSearch Main Application
FastAPI application entry point for the distributed search system
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import os
import time

from .config import Settings, get_settings
from .api.router import api_router
from .api.dependencies import init_dependencies, shutdown_dependencies
from .api.websocket import router as websocket_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting DistriSearch application...")
    settings = get_settings()
    
    try:
        # Initialize all dependencies
        await init_dependencies(settings)
        logger.info(f"Node {settings.node_id} started as {settings.node_role}")
        logger.info(f"API server running on {settings.api_host}:{settings.api_port}")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down DistriSearch application...")
        await shutdown_dependencies()
        logger.info("Shutdown complete")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    settings = get_settings()
    
    app = FastAPI(
        title="DistriSearch API",
        description="""
        DistriSearch is a distributed document search system that provides:
        
        * **Document Management**: Upload, store, and manage documents across a distributed cluster
        * **Adaptive Vectorization**: TF-IDF, MinHash, and LDA for semantic document representation
        * **Distributed Search**: Fast hybrid search using VP-Tree partitioning
        * **Cluster Management**: Automatic leader election, rebalancing, and fault tolerance
        * **Real-time Updates**: WebSocket support for live dashboard updates
        
        ## Architecture
        
        - **Master Node**: Coordinates the cluster, handles VP-Tree indexing
        - **Slave Nodes**: Store documents and process search queries
        - **MongoDB**: Persistent document and metadata storage
        - **Raft-Lite**: Consensus protocol for master election
        
        ## Authentication
        
        API endpoints are secured using JWT tokens. Include the token in the Authorization header:
        ```
        Authorization: Bearer <token>
        ```
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Add middleware
    configure_middleware(app, settings)
    
    # Add exception handlers
    configure_exception_handlers(app)
    
    # Include routers
    app.include_router(api_router)
    app.include_router(websocket_router)
    
    return app


def configure_middleware(app: FastAPI, settings: Settings):
    """Configure application middleware"""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://dashboard:3000",
            "http://frontend:3000",
            "*"  # In production, restrict this
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"]
    )
    
    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"[{request_id}]"
        )
        response = await call_next(request)
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"status={response.status_code} [{request_id}]"
        )
        return response


def configure_exception_handlers(app: FastAPI):
    """Configure exception handlers"""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, 
        exc: RequestValidationError
    ):
        """Handle request validation errors"""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "message": "Invalid request parameters",
                "details": [
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                        "code": error["type"]
                    }
                    for error in exc.errors()
                ]
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unhandled exceptions"""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "details": []
            }
        )


# Create the application instance
app = create_application()


# Health check endpoint at root level (no prefix)
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint returning basic API information.
    """
    return {
        "name": "DistriSearch",
        "description": "Distributed Document Search System",
        "version": get_settings().app_version,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.get("/ping", tags=["root"])
async def ping():
    """Simple ping endpoint for load balancer health checks."""
    return {"status": "ok"}
