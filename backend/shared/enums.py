from enum import Enum

class UserRole(str, Enum):
    MASTER_ADMIN = "master_admin"
    ADMIN = "admin"
    STANDARD = "standard"

class ConfidentialityLevel(str, Enum):
    PUBLIC = "public"
    PRIVE = "privé"