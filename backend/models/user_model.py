from sqlalchemy import Column, String, Enum, JSON
from shared.enums import UserRole, ConfidentialityLevel
from models.base import Base

class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    allowed_confidentiality = Column(JSON, nullable=False, default=list)

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}')>"

    def set_confidentiality(self, levels: list[ConfidentialityLevel]):
        self.allowed_confidentiality = [level.value for level in levels]

    def get_confidentiality(self) -> list[ConfidentialityLevel]:
        return [ConfidentialityLevel(level) for level in self.allowed_confidentiality]
