from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from schemas.user_schema import UserCreateRequest, UserResponse
from shared.enums import ConfidentialityLevel, UserRole
from models.user_model import User
from models.base import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from passlib.context import CryptContext
from .dependencies import get_current_user, require_admin_role

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    confidentiality: List[str]

class UserListResponse(BaseModel):
    username: str
    role: str
    confidentiality: List[str]

    class Config:
        from_attributes = True

class UpdateUserConfidentiality(BaseModel):
    confidentiality: List[str]

async def get_user(username: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: UserRole,
    allowed_confidentiality: list[ConfidentialityLevel]
) -> User:
    # Vérifier si l'utilisateur existe déjà
    existing_user = await get_user(username, db)
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet utilisateur existe déjà")

    # Créer le nouvel utilisateur
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        role=role
    )
    user.set_confidentiality(allowed_confidentiality)
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def create_master_admin(db: AsyncSession) -> User:
    # Vérifier si le master admin existe déjà
    master_admin = await get_user("staleb", db)
    if master_admin:
        return master_admin

    # Créer le master admin
    return await create_user(
        db=db,
        username="staleb",
        password="ol",
        role=UserRole.MASTER_ADMIN,
        allowed_confidentiality=[ConfidentialityLevel.PUBLIC, ConfidentialityLevel.PRIVE]
    )

def check_user_access(user: User, confidentiality: ConfidentialityLevel) -> bool:
    return confidentiality in user.get_confidentiality()

@router.get("/users", response_model=List[UserListResponse])
async def get_users(
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        {
            "username": user.username,
            "role": user.role.value,
            "confidentiality": [c.value for c in user.get_confidentiality()]
        }
        for user in users
    ]

@router.post("/create-user", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Vérifier si l'utilisateur existe déjà
        existing_user = await get_user(user_data.username, db)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cet utilisateur existe déjà"
            )
        
        # Convertir le rôle en enum
        try:
            role = UserRole(user_data.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rôle invalide"
            )
        
        # Convertir les niveaux de confidentialité en enum
        try:
            confidentiality_levels = [ConfidentialityLevel(c) for c in user_data.confidentiality]
            # Si "privé" est sélectionné, ajouter automatiquement "public"
            if ConfidentialityLevel.PRIVE in confidentiality_levels and ConfidentialityLevel.PUBLIC not in confidentiality_levels:
                confidentiality_levels.append(ConfidentialityLevel.PUBLIC)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Niveau de confidentialité invalide"
            )
        
        # Créer le nouvel utilisateur
        new_user = User(
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            role=role
        )
        new_user.set_confidentiality(confidentiality_levels)
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return {
            "username": new_user.username,
            "role": new_user.role.value,
            "confidentiality": [c.value for c in new_user.get_confidentiality()]
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de l'utilisateur: {str(e)}"
        )

@router.put("/users/{username}/confidentiality", response_model=UserResponse)
async def update_user_confidentiality(
    username: str,
    update_data: UpdateUserConfidentiality,
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db)
):
    # Vérifier si l'utilisateur existe
    user = await get_user(username, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    # Convertir les niveaux de confidentialité en enum
    try:
        confidentiality_levels = [ConfidentialityLevel(c) for c in update_data.confidentiality]
        # Si "privé" est sélectionné, ajouter automatiquement "public"
        if ConfidentialityLevel.PRIVE in confidentiality_levels and ConfidentialityLevel.PUBLIC not in confidentiality_levels:
            confidentiality_levels.append(ConfidentialityLevel.PUBLIC)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Niveau de confidentialité invalide"
        )
    
    # Mettre à jour les niveaux de confidentialité
    user.set_confidentiality(confidentiality_levels)
    
    await db.commit()
    await db.refresh(user)
    
    return {
        "username": user.username,
        "role": user.role.value,
        "confidentiality": [c.value for c in user.get_confidentiality()]
    }

@router.delete("/users/{username}", response_model=dict)
async def delete_user(
    username: str,
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db)
):
    # Vérifier si l'utilisateur existe
    user = await get_user(username, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    # Empêcher la suppression d'un master admin
    if user.role == UserRole.MASTER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Impossible de supprimer un master admin"
        )
    
    # Supprimer l'utilisateur
    await db.delete(user)
    await db.commit()
    
    return {"message": f"Utilisateur {username} supprimé avec succès"}

# @router.post("/create-user-form")
# async def create_user_form(
#     username: str = Form(...),
#     password: str = Form(...),
#     role: UserRole = Form(...),
#     allowed_confidentiality: List[ConfidentialityLevel] = Form(...),
#     db: AsyncSession = Depends(get_db),
# ):
#     try:
#         result = await db.execute(select(User).where(User.username == username))
#         existing_user = result.scalars().first()
#         if existing_user:
#             raise HTTPException(status_code=400, detail="Utilisateur déjà existant.")

#         hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

#         user = User(username=username, hashed_password=hashed_password, role=role)
#         user.set_confidentiality(allowed_confidentiality)

#         db.add(user)
#         await db.commit()
#         await db.refresh(user)

#         return {"message": f"✅ Utilisateur {user.username} créé avec succès."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
