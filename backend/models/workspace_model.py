from sqlalchemy import Column, String
from models.base import Base

class Workspace(Base):
    __tablename__ = "workspaces"
    name = Column(String, primary_key=True)
