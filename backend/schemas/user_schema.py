from typing import List
from pydantic import BaseModel
from shared.enums import UserRole, ConfidentialityLevel

class UserBase(BaseModel):
    username: str
    role: UserRole
    allowed_confidentiality: List[ConfidentialityLevel]

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: UserRole
    allowed_confidentiality: List[ConfidentialityLevel]

class UserResponse(BaseModel):
    username: str
    role: UserRole
    confidentiality: List[ConfidentialityLevel]