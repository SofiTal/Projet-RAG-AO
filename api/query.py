from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import List
from .auth import oauth2_scheme, get_user_from_token
from rag.rag_pipeline import poser_question
from shared.enums import ConfidentialityLevel, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from models.db import get_db

router = APIRouter()

# Requête unique
class QuestionRequest(BaseModel):
    question: str
    workspace_id: str

# Détermine les niveaux autorisés en fonction du rôle
# def get_max_conf_level(role: UserRole) -> List[ConfidentialityLevel]:
#     if role == UserRole.ADMIN:
#         return [ConfidentialityLevel.PUBLIC, ConfidentialityLevel.INTERNE, ConfidentialityLevel.SECRET]
#     elif role == UserRole.INTERNE:
#         return [ConfidentialityLevel.PUBLIC, ConfidentialityLevel.INTERNE]
#     elif role == UserRole.EXTERNE:
#         return [ConfidentialityLevel.PUBLIC]
    
@router.post("/query")
async def query(request: Request, payload: QuestionRequest, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    vectorstore = request.app.state.vectorstore
    reranker_model = request.app.state.reranker_model
    llm = request.app.state.llm
    user = await get_user_from_token(token, db)
    allowed_levels = user.allowed_confidentiality

    result = poser_question(payload.question, vectorstore, llm, payload.workspace_id, allowed_levels, reranker_model)
    return {
        "response": result["response"],
        "sources": result["sources"]
    }