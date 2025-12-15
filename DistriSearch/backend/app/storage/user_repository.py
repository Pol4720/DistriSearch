"""
User Repository for DistriSearch.

Handles all user-related database operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING

from .models import UserModel, UserStatus

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for user operations.
    
    Handles CRUD operations for users in MongoDB.
    """
    
    COLLECTION_NAME = "users"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize user repository.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
    
    async def initialize(self) -> None:
        """Create indexes for optimal query performance."""
        try:
            indexes = [
                IndexModel([("username", ASCENDING)], unique=True),
                IndexModel([("email", ASCENDING)], unique=True),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("role", ASCENDING)]),
                IndexModel([("created_at", ASCENDING)]),
            ]
            await self.collection.create_indexes(indexes)
            logger.info("User collection indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating user indexes: {e}")
    
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
        
        await self.collection.insert_one(user.to_dict())
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
        doc = await self.collection.find_one({"_id": user_id})
        return UserModel.from_dict(doc) if doc else None
    
    async def find_by_username(self, username: str) -> Optional[UserModel]:
        """
        Find user by username.
        
        Args:
            username: Username
            
        Returns:
            User model or None
        """
        doc = await self.collection.find_one({"username": username})
        return UserModel.from_dict(doc) if doc else None
    
    async def find_by_email(self, email: str) -> Optional[UserModel]:
        """
        Find user by email.
        
        Args:
            email: Email address
            
        Returns:
            User model or None
        """
        doc = await self.collection.find_one({"email": email.lower()})
        return UserModel.from_dict(doc) if doc else None
    
    async def find_by_username_or_email(self, identifier: str) -> Optional[UserModel]:
        """
        Find user by username or email.
        
        Args:
            identifier: Username or email
            
        Returns:
            User model or None
        """
        doc = await self.collection.find_one({
            "$or": [
                {"username": identifier},
                {"email": identifier.lower()}
            ]
        })
        return UserModel.from_dict(doc) if doc else None
    
    async def update(self, user_id: str, updates: Dict[str, Any]) -> Optional[UserModel]:
        """
        Update user.
        
        Args:
            user_id: User ID
            updates: Fields to update
            
        Returns:
            Updated user model or None
        """
        updates["updated_at"] = datetime.now()
        
        result = await self.collection.find_one_and_update(
            {"_id": user_id},
            {"$set": updates},
            return_document=True
        )
        
        if result:
            logger.info(f"Updated user: {user_id}")
            return UserModel.from_dict(result)
        return None
    
    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "last_login": datetime.now(),
                    "failed_login_attempts": 0,
                    "locked_until": None
                }
            }
        )
    
    async def increment_failed_login(self, user_id: str) -> int:
        """
        Increment failed login attempts.
        
        Returns:
            New count of failed attempts
        """
        result = await self.collection.find_one_and_update(
            {"_id": user_id},
            {"$inc": {"failed_login_attempts": 1}},
            return_document=True
        )
        return result.get("failed_login_attempts", 0) if result else 0
    
    async def lock_account(self, user_id: str, until: datetime) -> None:
        """Lock user account until specified time."""
        await self.collection.update_one(
            {"_id": user_id},
            {"$set": {"locked_until": until}}
        )
    
    async def update_refresh_token(self, user_id: str, token: Optional[str]) -> None:
        """Update user's refresh token."""
        await self.collection.update_one(
            {"_id": user_id},
            {"$set": {"refresh_token": token, "updated_at": datetime.now()}}
        )
    
    async def change_password(self, user_id: str, new_password_hash: str, new_salt: str) -> bool:
        """
        Change user password.
        
        Args:
            user_id: User ID
            new_password_hash: New password hash
            new_salt: New salt
            
        Returns:
            True if successful
        """
        result = await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "salt": new_salt,
                    "last_password_change": datetime.now(),
                    "updated_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    async def delete(self, user_id: str) -> bool:
        """
        Delete user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted
        """
        result = await self.collection.delete_one({"_id": user_id})
        if result.deleted_count > 0:
            logger.info(f"Deleted user: {user_id}")
            return True
        return False
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[UserStatus] = None
    ) -> List[UserModel]:
        """
        Find all users with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by status
            
        Returns:
            List of user models
        """
        query = {}
        if status:
            query["status"] = status.value
        
        cursor = self.collection.find(query).skip(skip).limit(limit)
        users = []
        async for doc in cursor:
            users.append(UserModel.from_dict(doc))
        return users
    
    async def count(self, status: Optional[UserStatus] = None) -> int:
        """
        Count users.
        
        Args:
            status: Filter by status
            
        Returns:
            Count of users
        """
        query = {}
        if status:
            query["status"] = status.value
        return await self.collection.count_documents(query)
