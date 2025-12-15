"""
Authentication Middleware
JWT-based authentication for DistriSearch API
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import logging
import os

logger = logging.getLogger(__name__)


class JWTHandler:
    """
    Handler for JWT token generation and validation.
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 7
    ):
        self.secret_key = secret_key or os.getenv("JWT_SECRET", "distrisearch-secret-key-change-in-production")
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a new access token.
        
        Args:
            data: Payload data to encode in the token
            expires_delta: Custom expiration time
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create a new refresh token.
        
        Args:
            data: Payload data to encode in the token
        
        Returns:
            Encoded JWT refresh token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload
        
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def verify_token_type(self, token: str, expected_type: str) -> Dict[str, Any]:
        """
        Verify token and check its type.
        
        Args:
            token: JWT token string
            expected_type: Expected token type ('access' or 'refresh')
        
        Returns:
            Decoded payload
        """
        payload = self.decode_token(token)
        
        if payload.get("type") != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {expected_type}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return payload


# Global JWT handler instance
jwt_handler = JWTHandler()

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Dependency to get the current authenticated user.
    
    Args:
        credentials: HTTP Bearer credentials from the request
    
    Returns:
        User information from the token, or None if not authenticated
    """
    if credentials is None:
        return None
    
    payload = jwt_handler.decode_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "roles": payload.get("roles", []),
        "node_id": payload.get("node_id")
    }


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> Dict[str, Any]:
    """
    Dependency that requires authentication.
    
    Raises HTTPException if not authenticated.
    """
    payload = jwt_handler.decode_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "roles": payload.get("roles", []),
        "node_id": payload.get("node_id")
    }


def require_role(required_roles: list):
    """
    Dependency factory that requires specific roles.
    
    Args:
        required_roles: List of roles that are allowed
    
    Returns:
        Dependency function
    """
    async def role_checker(
        user: Dict[str, Any] = Depends(require_auth)
    ) -> Dict[str, Any]:
        user_roles = user.get("roles", [])
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return user
    
    return role_checker


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for FastAPI.
    
    Checks JWT tokens for protected routes and adds user info to request state.
    """
    
    # Routes that don't require authentication
    PUBLIC_ROUTES = [
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
    
    def __init__(self, app, jwt_handler: JWTHandler = None):
        super().__init__(app)
        self.jwt_handler = jwt_handler or JWTHandler()
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and check authentication."""
        
        # Skip auth for public routes
        if self._is_public_route(request.url.path):
            return await call_next(request)
        
        # Skip auth if disabled
        if os.getenv("AUTH_DISABLED", "false").lower() == "true":
            return await call_next(request)
        
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            # Allow unauthenticated requests for now (configurable)
            if os.getenv("AUTH_REQUIRED", "false").lower() != "true":
                return await call_next(request)
            
            return self._unauthorized_response("Missing authorization header")
        
        # Extract token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return self._unauthorized_response("Invalid authentication scheme")
        except ValueError:
            return self._unauthorized_response("Invalid authorization header format")
        
        # Validate token
        try:
            payload = self.jwt_handler.decode_token(token)
            request.state.user = {
                "user_id": payload.get("sub"),
                "username": payload.get("username"),
                "roles": payload.get("roles", []),
                "node_id": payload.get("node_id")
            }
        except HTTPException as e:
            return self._unauthorized_response(e.detail)
        
        return await call_next(request)
    
    def _is_public_route(self, path: str) -> bool:
        """Check if the route is public (doesn't require auth)."""
        # Exact match
        if path in self.PUBLIC_ROUTES:
            return True
        
        # Prefix match for some routes
        for route in self.PUBLIC_ROUTES:
            if route.endswith("*") and path.startswith(route[:-1]):
                return True
        
        return False
    
    def _unauthorized_response(self, detail: str):
        """Create an unauthorized response."""
        from fastapi.responses import JSONResponse
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Unauthorized", "message": detail},
            headers={"WWW-Authenticate": "Bearer"}
        )


class NodeAuthHandler:
    """
    Handler for node-to-node authentication.
    
    Used for authenticating internal cluster communication.
    """
    
    def __init__(self, cluster_secret: Optional[str] = None):
        self.cluster_secret = cluster_secret or os.getenv(
            "CLUSTER_SECRET",
            "distrisearch-cluster-secret"
        )
    
    def create_node_token(self, node_id: str) -> str:
        """
        Create a token for node-to-node communication.
        
        Args:
            node_id: ID of the node requesting the token
        
        Returns:
            JWT token for internal communication
        """
        handler = JWTHandler(secret_key=self.cluster_secret)
        return handler.create_access_token(
            data={
                "sub": node_id,
                "type": "node",
                "node_id": node_id
            },
            expires_delta=timedelta(hours=24)
        )
    
    def verify_node_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a node authentication token.
        
        Args:
            token: JWT token from the node
        
        Returns:
            Decoded payload with node information
        """
        handler = JWTHandler(secret_key=self.cluster_secret)
        payload = handler.decode_token(token)
        
        if payload.get("type") != "node":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid node token"
            )
        
        return payload


# Global node auth handler
node_auth_handler = NodeAuthHandler()
