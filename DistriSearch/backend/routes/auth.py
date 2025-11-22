from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from models import UserCreate, UserLogin, Token
from auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
import database
from services.dynamic_replication import get_replication_service
from security import require_api_key

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

@router.post("/register")
async def register(user: UserCreate):
    """Registra un nuevo usuario"""
    # Verificar si el usuario ya existe
    if database.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if database.get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Crear usuario
    hashed_password = get_password_hash(user.password)
    try:
        new_user = database.create_user(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        
        return {
            "message": "User created successfully",
            "username": new_user["username"],
            "email": new_user["email"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Inicia sesión y retorna token JWT"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    # Log activity
    database.log_activity(str(user["_id"]), "login", "User logged in")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Obtiene información del usuario actual"""
    return {
        "username": current_user["username"],
        "email": current_user["email"],
        "is_active": current_user.get("is_active", True),
        "created_at": current_user.get("created_at")
    }

@router.get("/activities")
async def get_my_activities(
    current_user: dict = Depends(get_current_active_user),
    limit: int = 50
):
    """Obtiene actividades del usuario actual"""
    activities = database.get_user_activities(str(current_user["_id"]), limit)
    return {"activities": activities, "count": len(activities)}

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