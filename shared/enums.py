from enum import Enum

class ConfidentialityLevel(str, Enum):
    PUBLIC = "public"
    INTERNE = "interne"
    SECRET = "secret"

class UserRole(str, Enum):
    ADMIN = "admin"
    STANDARD = "standard"