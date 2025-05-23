from sqlalchemy.ext.asyncio import AsyncSession
from shared.enums import UserRole, ConfidentialityLevel
from passlib.context import CryptContext
from models.user_model import User
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def create_master_admin(db: AsyncSession):
    result = await db.execute(select(User).where(User.username == "staleb"))
    master_admin = result.scalar_one_or_none()
    if master_admin:
        return master_admin

    user = User(
        username="staleb",
        hashed_password=get_password_hash("ol"),
        role=UserRole.MASTER_ADMIN
    )
    user.set_confidentiality([ConfidentialityLevel.PUBLIC, ConfidentialityLevel.PRIVE])

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
