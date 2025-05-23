from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.base import get_db
from models.user_model import User
from models.workspace_model import Workspace as WorkspaceModel
from .dependencies import get_current_user
from typing import List
from pydantic import BaseModel

router = APIRouter()

class WorkspaceCreate(BaseModel):
    name: str

@router.get("/workspaces")
async def get_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(WorkspaceModel))
    workspaces = result.scalars().all()
    return [ws.name for ws in workspaces]

@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Vérifier si le workspace existe déjà
    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.name == workspace_data.name))
    existing_workspace = result.scalar_one_or_none()
    
    if existing_workspace:
        return {"name": existing_workspace.name}

    new_workspace = WorkspaceModel(name=workspace_data.name)
    db.add(new_workspace)
    await db.commit()
    return {"name": new_workspace.name}

async def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":  # Ne vérifie que "admin", pas "master_admin"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def check_confidentiality_access(user: User, confidentiality: str) -> None:
    if confidentiality == "privé" and user.role != "admin":  # Ne vérifie que "admin", pas "master_admin"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access private content"
        )