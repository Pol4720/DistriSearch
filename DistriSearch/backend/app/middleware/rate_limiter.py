"""
Rate Limiter Middleware
Request rate limiting for DistriSearch API
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Dict, Optional, Callable, Awaitable
from datetime import datetime
from collections import defaultdict
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting"""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit


class TokenBucket:
    """
    Token bucket rate limiter implementation.
    
    Allows burst traffic while maintaining an average rate limit.
    """
    
    def __init__(
        self,
        rate: float,  # tokens per second
        capacity: int  # max burst size
    ):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
        
        Returns:
            True if tokens were acquired, False if rate limited
        """
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on time elapsed
            elapsed = now - self.last_update
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # Try to acquire tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens (may be stale)"""
        elapsed = time.time() - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class SlidingWindowCounter:
    """
    Sliding window counter rate limiter.
    
    More accurate than fixed window, tracks requests over a sliding time window.
    """
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size  # in seconds
        self.max_requests = max_requests
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if a request is allowed.
        
        Args:
            key: Identifier for the client (e.g., IP address)
        
        Returns:
            Tuple of (allowed, remaining_requests)
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Remove old requests
            self.requests[key] = [
                ts for ts in self.requests[key] if ts > window_start
            ]
            
            current_count = len(self.requests[key])
            remaining = self.max_requests - current_count
            
            if current_count < self.max_requests:
                self.requests[key].append(now)
                return True, remaining - 1
            
            return False, 0
    
    async def cleanup(self):
        """Clean up old entries to prevent memory leak"""
        async with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            keys_to_remove = []
            for key in self.requests:
                self.requests[key] = [
                    ts for ts in self.requests[key] if ts > window_start
                ]
                if not self.requests[key]:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.requests[key]


class RateLimiter:
    """
    Combined rate limiter using both token bucket and sliding window.
    
    Token bucket handles burst traffic, sliding window ensures long-term limits.
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        
        # Per-client rate limiters
        self.buckets: Dict[str, TokenBucket] = {}
        self.counters: Dict[str, SlidingWindowCounter] = {}
        
        # Default counters
        self.minute_counter = SlidingWindowCounter(60, self.config.requests_per_minute)
        self.hour_counter = SlidingWindowCounter(3600, self.config.requests_per_hour)
        
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(
        self,
        key: str,
        endpoint: Optional[str] = None
    ) -> tuple[bool, Dict[str, int]]:
        """
        Check if a request is within rate limits.
        
        Args:
            key: Client identifier (e.g., IP address)
            endpoint: Optional endpoint-specific limit
        
        Returns:
            Tuple of (allowed, headers_dict)
        """
        # Get or create token bucket for client
        async with self._lock:
            if key not in self.buckets:
                self.buckets[key] = TokenBucket(
                    rate=self.config.requests_per_minute / 60.0,
                    capacity=self.config.burst_limit
                )
        
        bucket = self.buckets[key]
        
        # Check token bucket (for burst protection)
        if not await bucket.acquire():
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60),
                "Retry-After": "1"
            }
        
        # Check minute limit
        minute_allowed, minute_remaining = await self.minute_counter.is_allowed(key)
        if not minute_allowed:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60),
                "Retry-After": "60"
            }
        
        # Check hour limit
        hour_allowed, hour_remaining = await self.hour_counter.is_allowed(key)
        if not hour_allowed:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_hour),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 3600),
                "Retry-After": "3600"
            }
        
        return True, {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(minute_remaining),
            "X-RateLimit-Reset": str(int(time.time()) + 60)
        }


# Global rate limiter instance
_rate_limiter = RateLimiter()


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10
):
    """
    Decorator for rate limiting specific endpoints.
    
    Args:
        requests_per_minute: Max requests per minute
        requests_per_hour: Max requests per hour
        burst_limit: Max burst size
    
    Usage:
        @app.get("/api/search")
        @rate_limit(requests_per_minute=30)
        async def search():
            ...
    """
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_limit=burst_limit
    )
    limiter = RateLimiter(config)
    
    def decorator(func: Callable[..., Awaitable]):
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = _get_client_ip(request)
            allowed, headers = await limiter.check_rate_limit(client_ip)
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers=headers
                )
            
            response = await func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, Response):
                for key, value in headers.items():
                    response.headers[key] = value
            
            return response
        
        return wrapper
    return decorator


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Applies rate limiting to all requests based on client IP.
    """
    
    # Endpoints with custom rate limits
    ENDPOINT_LIMITS = {
        "/api/v1/search": RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=500,
            burst_limit=5
        ),
        "/api/v1/documents/upload": RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_limit=3
        ),
        "/api/v1/cluster/rebalance": RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=20,
            burst_limit=1
        )
    }
    
    # Endpoints exempt from rate limiting
    EXEMPT_ENDPOINTS = [
        "/",
        "/ping",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/ws"
    ]
    
    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.default_limiter = RateLimiter(config or RateLimitConfig())
        self.endpoint_limiters: Dict[str, RateLimiter] = {
            endpoint: RateLimiter(limit_config)
            for endpoint, limit_config in self.ENDPOINT_LIMITS.items()
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and apply rate limiting."""
        
        path = request.url.path
        
        # Skip exempt endpoints
        if self._is_exempt(path):
            return await call_next(request)
        
        # Get client identifier
        client_ip = _get_client_ip(request)
        
        # Get appropriate rate limiter
        limiter = self._get_limiter(path)
        
        # Check rate limit
        allowed, headers = await limiter.check_rate_limit(client_ip, path)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate Limit Exceeded",
                    "message": "Too many requests. Please try again later."
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
    
    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        for exempt in self.EXEMPT_ENDPOINTS:
            if path == exempt or path.startswith(exempt + "/"):
                return True
        return False
    
    def _get_limiter(self, path: str) -> RateLimiter:
        """Get the appropriate rate limiter for the path."""
        for endpoint, limiter in self.endpoint_limiters.items():
            if path.startswith(endpoint):
                return limiter
        return self.default_limiter


def _get_client_ip(request: Request) -> str:
    """
    Get the client IP address from the request.
    
    Handles X-Forwarded-For header for proxied requests.
    """
    # Check X-Forwarded-For header (from reverse proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"
