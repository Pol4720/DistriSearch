"""
Logging Middleware
Request/Response logging for DistriSearch API
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional, Callable, Awaitable
from datetime import datetime
import logging
import time
import json
import uuid

logger = logging.getLogger(__name__)


class RequestLogger:
    """
    Structured request logger for tracking API usage.
    """
    
    def __init__(
        self,
        logger_name: str = "distrisearch.requests",
        include_body: bool = False,
        max_body_length: int = 1000
    ):
        self.logger = logging.getLogger(logger_name)
        self.include_body = include_body
        self.max_body_length = max_body_length
    
    def log_request(
        self,
        request_id: str,
        method: str,
        path: str,
        client_ip: str,
        user_agent: Optional[str] = None,
        body: Optional[str] = None
    ):
        """Log an incoming request"""
        log_data = {
            "event": "request",
            "request_id": request_id,
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.include_body and body:
            log_data["body"] = body[:self.max_body_length]
        
        self.logger.info(json.dumps(log_data))
    
    def log_response(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        response_size: Optional[int] = None
    ):
        """Log an outgoing response"""
        log_data = {
            "event": "response",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if response_size is not None:
            log_data["response_size"] = response_size
        
        # Use different log levels based on status code
        if status_code >= 500:
            self.logger.error(json.dumps(log_data))
        elif status_code >= 400:
            self.logger.warning(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))
    
    def log_error(
        self,
        request_id: str,
        method: str,
        path: str,
        error: str,
        traceback: Optional[str] = None
    ):
        """Log an error during request processing"""
        log_data = {
            "event": "error",
            "request_id": request_id,
            "method": method,
            "path": path,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if traceback:
            log_data["traceback"] = traceback
        
        self.logger.error(json.dumps(log_data))


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logging middleware for FastAPI.
    
    Logs all requests and responses with timing information.
    """
    
    # Paths to exclude from logging
    EXCLUDED_PATHS = [
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/ping",
        "/favicon.ico"
    ]
    
    def __init__(
        self,
        app,
        logger: Optional[RequestLogger] = None,
        include_body: bool = False,
        slow_request_threshold_ms: float = 1000.0
    ):
        super().__init__(app)
        self.request_logger = logger or RequestLogger(include_body=include_body)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next):
        """Process the request with logging."""
        
        # Skip logging for excluded paths
        if self._should_skip(request.url.path):
            return await call_next(request)
        
        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Get client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        
        # Log request
        body = None
        if self.request_logger.include_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await self._get_request_body(request)
            except Exception:
                body = None
        
        self.request_logger.log_request(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=user_agent,
            body=body
        )
        
        # Process request with timing
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Get response size
            response_size = None
            if hasattr(response, "headers"):
                content_length = response.headers.get("Content-Length")
                if content_length:
                    response_size = int(content_length)
            
            # Log response
            self.request_logger.log_response(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=response_size
            )
            
            # Log slow requests
            if duration_ms > self.slow_request_threshold_ms:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration_ms:.2f}ms"
                )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            import traceback
            self.request_logger.log_error(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                traceback=traceback.format_exc()
            )
            
            raise
    
    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped from logging."""
        return path in self.EXCLUDED_PATHS
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Get request body for logging."""
        try:
            body = await request.body()
            return body.decode("utf-8")[:1000]
        except Exception:
            return None


class AccessLogger:
    """
    Access logger that writes logs in Apache/Nginx combined log format.
    """
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self.logger = logging.getLogger("distrisearch.access")
        
        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
    
    def log(
        self,
        client_ip: str,
        method: str,
        path: str,
        protocol: str,
        status_code: int,
        response_size: int,
        referer: Optional[str],
        user_agent: Optional[str],
        duration_ms: float
    ):
        """Log in combined log format"""
        timestamp = datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000")
        
        log_line = (
            f'{client_ip} - - [{timestamp}] "{method} {path} {protocol}" '
            f'{status_code} {response_size} "{referer or "-"}" '
            f'"{user_agent or "-"}" {duration_ms:.3f}'
        )
        
        self.logger.info(log_line)


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    json_format: bool = False
):
    """
    Set up application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string
        json_format: Use JSON format for logs
    """
    if format_string is None:
        if json_format:
            format_string = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        else:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
