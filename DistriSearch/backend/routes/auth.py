from fastapi import APIRouter, HTTPException, status, Depends
from models import UserCreate, UserLogin, Token
import database
from auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user
from datetime import timedelta
from services.dynamic_replication import get_replication_service
from security import require_api_key

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    """Registro de usuario usando MongoDB."""
    # Verificar si usuario ya existe
    if database.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if database.get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Crear usuario
    hashed_password = get_password_hash(user.password)
    db_user = database.create_user(user.email, user.username, hashed_password)
    
    # Generar token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": db_user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: UserLogin):
    """Login usando MongoDB."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/replication/status")
async def get_replication_status(_: None = Depends(require_api_key)):
    """Obtiene el estado de la replicación dinámica"""
    service = get_replication_service()
    return service.get_replication_status()

@router.post("/replication/sync")
async def trigger_sync(_: None = Depends(require_api_key)):
    """Fuerza una sincronización inmediata"""
    service = get_replication_service()
    result = await service.synchronize_eventual_consistency()
    return {"status": "completed", **result}