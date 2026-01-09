"""
SQLite User Repository for DistriSearch.

Implements user CRUD operations using SQLite instead of MongoDB.
This repository is replicated via Raft to all nodes, enabling
AP mode where any node can authenticate users during partitions.
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from .sqlite_client import SQLiteClient
from .models import UserModel, UserStatus, UserRole

logger = logging.getLogger(__name__)


class SQLiteUserRepository:
    """
    Repository for user operations using SQLite.
    
    Features:
    - Same interface as the original MongoDB UserRepository
    - Replicated via Raft for AP mode
    - Read replicas on slaves for local authentication
    """
    
    TABLE_NAME = "users"
    
    def __init__(self, client: SQLiteClient):
        """
        Initialize user repository.
        
        Args:
            client: SQLite client instance
        """
        self.client = client
    
    async def initialize(self) -> None:
        """Initialize repository (indexes created in schema)."""
        logger.info("SQLite User repository initialized")
    
    async def create(self, user: UserModel) -> UserModel:
        """
        Create a new user.
        
        Args:
            user: User model to create
            
        Returns:
            Created user model
            
        Raises:
            ValueError: If username or email already exists
        """
        # Check for existing username
        existing = await self.find_by_username(user.username)
        if existing:
            raise ValueError(f"Username '{user.username}' already exists")
        
        # Check for existing email
        existing = await self.find_by_email(user.email)
        if existing:
            raise ValueError(f"Email '{user.email}' already registered")
        
        # Insert user
        data = self._user_to_row(user)
        await self.client.insert(self.TABLE_NAME, data)
        
        logger.info(f"Created user: {user.username}")
        return user
    
    async def find_by_id(self, user_id: str) -> Optional[UserModel]:
        """
        Find user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User model or None
        """
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",
            (user_id,)
        )
        return self._row_to_user(row) if row else None
    
    async def find_by_username(self, username: str) -> Optional[UserModel]:
        """
        Find user by username.
        
        Args:
            username: Username
            
        Returns:
            User model or None
        """
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE username = ?",
            (username,)
        )
        return self._row_to_user(row) if row else None
    
    async def find_by_email(self, email: str) -> Optional[UserModel]:
        """
        Find user by email.
        
        Args:
            email: Email address
            
        Returns:
            User model or None
        """
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE email = ?",
            (email.lower(),)
        )
        return self._row_to_user(row) if row else None
    
    async def find_by_username_or_email(self, identifier: str) -> Optional[UserModel]:
        """
        Find user by username or email.
        
        Args:
            identifier: Username or email
            
        Returns:
            User model or None
        """
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE username = ? OR email = ?",
            (identifier, identifier.lower())
        )
        return self._row_to_user(row) if row else None
    
    async def find_by_refresh_token(self, token: str) -> Optional[UserModel]:
        """
        Find user by refresh token.
        
        Args:
            token: Refresh token
            
        Returns:
            User model or None
        """
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE refresh_token = ?",
            (token,)
        )
        return self._row_to_user(row) if row else None
    
    async def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[UserModel]:
        """
        Update user data.
        
        Args:
            user_id: User ID
            update_data: Fields to update
            
        Returns:
            Updated user or None if not found
        """
        # Convert complex types to JSON
        serialized = {}
        for key, value in update_data.items():
            if isinstance(value, (list, dict)):
                serialized[key] = json.dumps(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, bool):
                serialized[key] = 1 if value else 0
            else:
                serialized[key] = value
        
        success = await self.client.update(self.TABLE_NAME, user_id, serialized)
        
        if success:
            return await self.find_by_id(user_id)
        return None
    
    async def delete(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted
        """
        success = await self.client.delete(self.TABLE_NAME, user_id)
        if success:
            logger.info(f"Deleted user: {user_id}")
        return success
    
    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[UserStatus] = None,
        role_filter: Optional[UserRole] = None,
    ) -> List[UserModel]:
        """
        List users with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            status_filter: Filter by status
            role_filter: Filter by role
            
        Returns:
            List of users
        """
        conditions = []
        params = []
        
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter.value if hasattr(status_filter, 'value') else status_filter)
        
        if role_filter:
            conditions.append("role = ?")
            params.append(role_filter.value if hasattr(role_filter, 'value') else role_filter)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, skip])
        
        rows = await self.client.fetch_all(sql, tuple(params))
        return [self._row_to_user(row) for row in rows if row]
    
    async def count(
        self,
        status_filter: Optional[UserStatus] = None,
        role_filter: Optional[UserRole] = None,
    ) -> int:
        """
        Count users.
        
        Args:
            status_filter: Filter by status
            role_filter: Filter by role
            
        Returns:
            User count
        """
        conditions = []
        params = []
        
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter.value if hasattr(status_filter, 'value') else status_filter)
        
        if role_filter:
            conditions.append("role = ?")
            params.append(role_filter.value if hasattr(role_filter, 'value') else role_filter)
        
        where_clause = " AND ".join(conditions) if conditions else ""
        
        return await self.client.fetch_count(self.TABLE_NAME, where_clause, tuple(params))
    
    async def update_login_attempt(
        self,
        user_id: str,
        success: bool,
        locked_until: Optional[datetime] = None,
    ) -> None:
        """
        Update login attempt tracking.
        
        Args:
            user_id: User ID
            success: Whether login was successful
            locked_until: Lock expiration time (if locking)
        """
        if success:
            await self.update(user_id, {
                "failed_login_attempts": 0,
                "locked_until": None,
                "last_login": datetime.now().isoformat(),
            })
        else:
            user = await self.find_by_id(user_id)
            if user:
                await self.update(user_id, {
                    "failed_login_attempts": user.failed_login_attempts + 1,
                    "locked_until": locked_until.isoformat() if locked_until else None,
                })

    async def increment_failed_login(self, user_id: str) -> int:
        """
        Increment failed login attempts counter.
        
        Args:
            user_id: User ID
            
        Returns:
            New count of failed attempts
        """
        user = await self.find_by_id(user_id)
        if user:
            new_count = user.failed_login_attempts + 1
            await self.update(user_id, {"failed_login_attempts": new_count})
            return new_count
        return 0

    async def lock_account(self, user_id: str, until: datetime) -> None:
        """
        Lock user account until specified time.
        
        Args:
            user_id: User ID
            until: Lock expiration datetime
        """
        await self.update(user_id, {"locked_until": until.isoformat()})

    async def update_refresh_token(
        self,
        user_id: str,
        refresh_token: Optional[str],
    ) -> None:
        """
        Update user's refresh token.
        
        Args:
            user_id: User ID
            refresh_token: New refresh token (or None to clear)
        """
        await self.update(user_id, {"refresh_token": refresh_token})
    
    async def set_password_reset_token(
        self,
        user_id: str,
        token: str,
        expires: datetime,
    ) -> None:
        """
        Set password reset token.
        
        Args:
            user_id: User ID
            token: Reset token
            expires: Token expiration
        """
        await self.update(user_id, {
            "password_reset_token": token,
            "password_reset_expires": expires.isoformat(),
        })
    
    async def clear_password_reset_token(self, user_id: str) -> None:
        """
        Clear password reset token.
        
        Args:
            user_id: User ID
        """
        await self.update(user_id, {
            "password_reset_token": None,
            "password_reset_expires": None,
        })
    
    async def update_password(
        self,
        user_id: str,
        password_hash: str,
        salt: str,
    ) -> None:
        """
        Update user password.
        
        Args:
            user_id: User ID
            password_hash: New password hash
            salt: New salt
        """
        await self.update(user_id, {
            "password_hash": password_hash,
            "salt": salt,
            "last_password_change": datetime.now().isoformat(),
            "password_reset_token": None,
            "password_reset_expires": None,
        })

    async def update_last_login(self, user_id: str) -> None:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID
        """
        await self.update(user_id, {
            "last_login": datetime.now().isoformat(),
            "failed_login_attempts": 0,
            "locked_until": None,
        })

    def _user_to_row(self, user: UserModel) -> Dict[str, Any]:
        """Convert UserModel to SQLite row dictionary."""
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email.lower(),
            "password_hash": user.password_hash,
            "salt": user.salt,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "permissions": json.dumps(user.permissions),
            "status": user.status.value if hasattr(user.status, 'value') else user.status,
            "email_verified": 1 if user.email_verified else 0,
            "failed_login_attempts": user.failed_login_attempts,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "last_password_change": user.last_password_change.isoformat() if user.last_password_change else None,
            "refresh_token": user.refresh_token,
            "password_reset_token": user.password_reset_token,
            "password_reset_expires": user.password_reset_expires.isoformat() if user.password_reset_expires else None,
            "created_at": user.created_at.isoformat() if user.created_at else datetime.now().isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else datetime.now().isoformat(),
        }
    
    def _row_to_user(self, row: Dict[str, Any]) -> UserModel:
        """Convert SQLite row to UserModel."""
        if row is None:
            return None
        
        # Parse JSON fields
        permissions = row.get("permissions", "[]")
        if isinstance(permissions, str):
            try:
                permissions = json.loads(permissions)
            except json.JSONDecodeError:
                permissions = []
        
        # Parse datetime fields
        def parse_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        
        return UserModel(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            salt=row["salt"],
            full_name=row.get("full_name"),
            avatar_url=row.get("avatar_url"),
            role=UserRole(row.get("role", "user")),
            permissions=permissions,
            status=UserStatus(row.get("status", "active")),
            email_verified=bool(row.get("email_verified", 0)),
            failed_login_attempts=row.get("failed_login_attempts", 0),
            locked_until=parse_datetime(row.get("locked_until")),
            last_login=parse_datetime(row.get("last_login")),
            last_password_change=parse_datetime(row.get("last_password_change")),
            refresh_token=row.get("refresh_token"),
            password_reset_token=row.get("password_reset_token"),
            password_reset_expires=parse_datetime(row.get("password_reset_expires")),
            created_at=parse_datetime(row.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(row.get("updated_at")) or datetime.now(),
        )
