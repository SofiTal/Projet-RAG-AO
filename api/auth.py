from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import jwt
from models.user_model import User
from shared.enums import ConfidentialityLevel
from .user_manager import get_user, verify_password, check_user_access
from models.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# Configuration
SECRET_KEY = "mysecretkey"  # À stocker dans des variables d'environnement en production !
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        user = await get_user(username, db)
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await get_user(form_data.username, db)
    if user is None or not await verify_password(user.hashed_password, form_data.password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Dépendance pour obtenir l'utilisateur courant à partir du token
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    return await get_user_from_token(token, db)

# Vérifie si l'utilisateur est admin
async def require_admin_role(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès interdit. Vous n'êtes pas administrateur.")
    return user

# Vérifie l'accès à un niveau de confidentialité
async def check_confidentiality_access(user: User = Depends(get_current_user), confidentiality: ConfidentialityLevel = None):
    if not check_user_access(user, confidentiality):
        raise HTTPException(status_code=403, detail="Accès interdit à ce niveau de confidentialité")
    return True
