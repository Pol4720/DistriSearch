"""
Authentication API Router
Handles user registration, login, and token management for DistriSearch

Uses SQLite UserRepository (Raft-replicated for high availability)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime, timedelta
import logging
import re
import aiohttp
import asyncio

from ..middleware.auth import jwt_handler, require_auth
from ..storage.sqlite_user_repository import SQLiteUserRepository
from ..storage.models import UserModel, UserStatus, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Dependency to get user repository
_user_repository: Optional[SQLiteUserRepository] = None


def set_sqlite_user_repository(repo: SQLiteUserRepository) -> None:
    """Set the SQLite user repository instance."""
    global _user_repository
    _user_repository = repo


async def get_user_repository() -> SQLiteUserRepository:
    """Get user repository dependency."""
    if _user_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User repository not initialized"
        )
    return _user_repository


async def _sync_user_to_peers(user: UserModel) -> None:
    """
    Synchronize a user to all known peer nodes.
    
    This is called after a user is created locally to ensure
    the user exists on all nodes in the cluster.
    """
    from .dependencies import get_cluster_peers
    
    peers = get_cluster_peers()
    if not peers:
        logger.debug("No peers to sync user to")
        return
    
    sync_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "password_hash": user.password_hash,
        "salt": user.salt,
        "role": user.role,
        "status": user.status.value if hasattr(user.status, 'value') else str(user.status),
        "full_name": user.full_name,
    }
    
    async def sync_to_peer(peer_id: str, peer_address: str):
        """Sync user to a single peer."""
        try:
            url = f"http://{peer_address}/api/v1/internal/sync/user"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=sync_data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(f"Synced user {user.username} to {peer_id}: {result.get('status')}")
                    else:
                        logger.warning(f"Failed to sync user to {peer_id}: status {resp.status}")
        except Exception as e:
            logger.warning(f"Error syncing user to {peer_id}: {e}")
    
    # Sync to all peers in parallel
    tasks = [sync_to_peer(pid, addr) for pid, addr in peers.items()]
    await asyncio.gather(*tasks, return_exceptions=True)


# Request/Response Models
class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., description="Username or email")
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserResponse(BaseModel):
    """Public user response."""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    status: str
    created_at: str


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True


# Constants
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
ACCESS_TOKEN_EXPIRE_MINUTES = 60


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Invalid input or user already exists"},
    }
)
async def register(
    request: RegisterRequest,
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Register a new user account.
    
    Creates a new user with the provided credentials and returns
    access and refresh tokens for immediate authentication.
    """
    try:
        # Create user
        user = UserModel.create_user(
            username=request.username,
            email=request.email.lower(),
            password=request.password,
            full_name=request.full_name,
            status=UserStatus.ACTIVE
        )
        
        # Save to database
        created_user = await user_repo.create(user)
        
        # Sync user to all peers (non-blocking in background)
        asyncio.create_task(_sync_user_to_peers(created_user))
        
        # Generate tokens
        token_data = {
            "sub": created_user.id,
            "username": created_user.username,
            "email": created_user.email,
            "roles": [created_user.role]
        }
        
        access_token = jwt_handler.create_access_token(token_data)
        refresh_token = jwt_handler.create_refresh_token(token_data)
        
        # Store refresh token
        await user_repo.update_refresh_token(created_user.id, refresh_token)
        
        logger.info(f"User registered: {created_user.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=created_user.to_public_dict()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login user",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        423: {"description": "Account locked"},
    }
)
async def login(
    request: LoginRequest,
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Authenticate user and return tokens.
    
    Accepts username or email for authentication.
    Account will be locked after multiple failed attempts.
    """
    # Find user by username or email
    user = await user_repo.find_by_username_or_email(request.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.now():
        remaining = (user.locked_until - datetime.now()).seconds // 60
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining} minutes."
        )
    
    # Check if account is active
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Account is {user.status}. Please contact support."
        )
    
    # Verify password
    if not user.verify_password(request.password):
        # Increment failed attempts
        attempts = await user_repo.increment_failed_login(user.id)
        
        if attempts >= MAX_LOGIN_ATTEMPTS:
            lockout_until = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            await user_repo.lock_account(user.id, lockout_until)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to too many failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes."
            )
        
        remaining = MAX_LOGIN_ATTEMPTS - attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid username or password. {remaining} attempts remaining.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Update last login
    await user_repo.update_last_login(user.id)
    
    # Generate tokens
    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "roles": [user.role]
    }
    
    access_token = jwt_handler.create_access_token(token_data)
    refresh_token = jwt_handler.create_refresh_token(token_data)
    
    # Store refresh token
    await user_repo.update_refresh_token(user.id, refresh_token)
    
    logger.info(f"User logged in: {user.username}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user.to_public_dict()
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid refresh token"},
    }
)
async def refresh_token(
    request: RefreshTokenRequest,
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Refresh access token using refresh token.
    
    Returns new access and refresh tokens.
    """
    try:
        # Validate refresh token
        payload = jwt_handler.verify_token_type(request.refresh_token, "refresh")
        user_id = payload.get("sub")
        
        # Get user
        user = await user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Verify refresh token matches stored token
        if user.refresh_token != request.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check user status
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is not active"
            )
        
        # Generate new tokens
        token_data = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "roles": [user.role]
        }
        
        access_token = jwt_handler.create_access_token(token_data)
        new_refresh_token = jwt_handler.create_refresh_token(token_data)
        
        # Update refresh token
        await user_repo.update_refresh_token(user.id, new_refresh_token)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user.to_public_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    responses={
        200: {"description": "Logged out successfully"},
    }
)
async def logout(
    current_user: dict = Depends(require_auth),
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Logout user and invalidate refresh token.
    """
    await user_repo.update_refresh_token(current_user["user_id"], None)
    logger.info(f"User logged out: {current_user['username']}")
    
    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    responses={
        200: {"description": "Current user information"},
        401: {"description": "Not authenticated"},
    }
)
async def get_current_user(
    current_user: dict = Depends(require_auth),
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Get current authenticated user's information.
    
    Falls back to JWT data if user not found in local DB (cluster failover support).
    """
    user = await user_repo.find_by_id(current_user["user_id"])
    
    if user:
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            status=user.status,
            created_at=user.created_at.isoformat() if user.created_at else ""
        )
    
    # Fallback to JWT data if user not in local DB (supports cluster failover)
    # The JWT is still valid, so we can trust the data in it
    logger.warning(f"User {current_user['user_id']} not found in local DB, using JWT data")
    return UserResponse(
        id=current_user.get("user_id", current_user.get("sub", "")),
        username=current_user.get("username", "unknown"),
        email=current_user.get("email", ""),
        full_name=current_user.get("full_name"),
        role=current_user.get("roles", ["user"])[0] if current_user.get("roles") else "user",
        status="active",
        created_at=""
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "Invalid current password"},
    }
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(require_auth),
    user_repo: SQLiteUserRepository = Depends(get_user_repository)
):
    """
    Change current user's password.
    """
    user = await user_repo.find_by_id(current_user["user_id"])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not user.verify_password(request.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    import secrets
    new_salt = secrets.token_hex(32)
    new_hash = UserModel.hash_password(request.new_password, new_salt)
    
    # Update password
    await user_repo.change_password(user.id, new_hash, new_salt)
    
    # Invalidate refresh token to force re-login
    await user_repo.update_refresh_token(user.id, None)
    
    logger.info(f"Password changed for user: {user.username}")
    
    return MessageResponse(message="Password changed successfully. Please login again.")


@router.get(
    "/verify",
    response_model=MessageResponse,
    summary="Verify token validity",
    responses={
        200: {"description": "Token is valid"},
        401: {"description": "Invalid token"},
    }
)
async def verify_token(
    current_user: dict = Depends(require_auth)
):
    """
    Verify if the current access token is valid.
    """
    return MessageResponse(
        message=f"Token valid for user: {current_user['username']}"
    )
