from sqlalchemy import Column, String, DateTime, Text, Enum as SqlEnum
from datetime import datetime
from shared.enums import UserRole, ConfidentialityLevel
from .db import Base
import json
from typing import List

class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SqlEnum(UserRole), nullable=False)

    # Liste d'enums stockée en JSON
    allowed_confidentiality = Column(Text, nullable=False)

    def set_confidentiality(self, levels: List[ConfidentialityLevel]):
        self.allowed_confidentiality = json.dumps([lvl.value for lvl in levels])

    def get_confidentiality(self) -> List[ConfidentialityLevel]:
        return [ConfidentialityLevel(lvl) for lvl in json.loads(self.allowed_confidentiality)]
