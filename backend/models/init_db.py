from sqlalchemy.ext.asyncio import AsyncSession
from models.base import Base, engine, SessionLocal
from models.user_model import User
from shared.enums import UserRole, ConfidentialityLevel
from passlib.context import CryptContext
from sqlalchemy import select

# Configuration du hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def init_db():
    # Créer les tables si elles n'existent pas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Créer les tables si elles n'existent pas

    # Créer une session
    async with SessionLocal() as db:
        try:
            # Vérifier si l'utilisateur master admin existe déjà
            result = await db.execute(select(User).where(User.username == "staleb"))
            master_admin = result.scalar_one_or_none()

            if not master_admin:
                # Créer l'utilisateur master admin
                master_admin = User(
                    username="staleb",
                    hashed_password=pwd_context.hash("ol"),
                    role=UserRole.MASTER_ADMIN,
                    allowed_confidentiality=[ConfidentialityLevel.PUBLIC.value, ConfidentialityLevel.PRIVE.value]
                )

                # Ajouter l'utilisateur à la base de données
                db.add(master_admin)
                await db.commit()
                print("Utilisateur master admin créé :")
                print(f"Username: staleb")
                print(f"Password: ol")
                print(f"Rôle: master_admin")
                print(f"Niveaux de confidentialité: public, privé")
            else:
                print("L'utilisateur master admin existe déjà.")

        except Exception as e:
            print(f"Erreur lors de l'initialisation : {e}")
            await db.rollback()

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db()) 