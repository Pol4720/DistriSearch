from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from user_database import (
    create_task, get_tasks_by_user, update_task_status, delete_task, get_user_by_username
)
from routes.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Modelos Pydantic
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str

class TaskUpdate(BaseModel):
    status: str

# Endpoints
@router.post("/", response_model=TaskResponse)
async def create_new_task(
    task: TaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """Crea una nueva tarea para el usuario actual."""
    task_id = create_task(current_user["id"], task.title, task.description)
    # Obtener la tarea creada
    tasks = get_tasks_by_user(current_user["id"])
    new_task = next((t for t in tasks if t["id"] == task_id), None)
    if not new_task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return TaskResponse(**new_task)

@router.get("/", response_model=List[TaskResponse])
async def get_user_tasks(current_user: dict = Depends(get_current_user)):
    """Obtiene todas las tareas del usuario actual."""
    tasks = get_tasks_by_user(current_user["id"])
    return [TaskResponse(**task) for task in tasks]

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Actualiza el estado de una tarea."""
    # Verificar que la tarea pertenece al usuario
    tasks = get_tasks_by_user(current_user["id"])
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_task_status(task_id, task_update.status)

    # Obtener la tarea actualizada
    tasks = get_tasks_by_user(current_user["id"])
    updated_task = next((t for t in tasks if t["id"] == task_id), None)
    return TaskResponse(**updated_task)

@router.delete("/{task_id}")
async def delete_user_task(
    task_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Elimina una tarea del usuario actual."""
    # Verificar que la tarea pertenece al usuario
    tasks = get_tasks_by_user(current_user["id"])
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    delete_task(task_id)
    return {"message": "Task deleted successfully"}