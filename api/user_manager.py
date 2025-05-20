from typing import List
from fastapi import APIRouter, HTTPException, Depends
from schemas.user_schema import UserCreateRequest
from shared.enums import ConfidentialityLevel, UserRole
from models.user_model import User
from models.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import bcrypt
from fastapi import Form


router = APIRouter()

async def create_user(username: str, password: str, role: UserRole, allowed_confidentiality: List[ConfidentialityLevel], db: AsyncSession):
    # Vérifier si l'utilisateur existe déjà
    result = await db.execute(select(User).where(User.username == username))
    existing_user = result.scalars().first()
    if existing_user:
        raise ValueError(f"Utilisateur {username} existe déjà.")

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user = User(
        username=username,
        hashed_password=hashed_password,
        role=role,
    )
    user.set_confidentiality(allowed_confidentiality)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def verify_password(stored_hashed_password: bytes, password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password)

async def get_user(username: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()

async def check_user_access(username: str, confidentiality: ConfidentialityLevel, db: AsyncSession) -> bool:
    user = await get_user(username, db)
    if user:
        return confidentiality in user.allowed_confidentiality
    return False

@router.post("/create-user")
async def create_new_user(user_req: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(user_req.username, user_req.password, user_req.role, user_req.allowed_confidentiality, db)
        return {"message": f"Utilisateur {user.username} créé avec succès."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

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
