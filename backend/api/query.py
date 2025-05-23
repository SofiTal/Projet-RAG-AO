from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import get_db
from models.user_model import User
from shared.enums import ConfidentialityLevel, UserRole

from .dependencies import get_current_user, oauth2_scheme
from rag.rag_pipeline import poser_question

router = APIRouter()

# Modèle de requête
class QuestionRequest(BaseModel):
    question: str
    workspace_id: str

@router.post("/query")
async def query(
    request: Request,
    payload: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    vectorstore = request.app.state.vectorstore
    reranker_model = request.app.state.reranker_model
    llm = request.app.state.llm

    allowed_levels = current_user.allowed_confidentiality

    result = poser_question(
        payload.question,
        vectorstore,
        llm,
        payload.workspace_id,
        allowed_levels,
        reranker_model
    )

    return {
        "answer": result["response"],
        "sources": result["sources"]
    }
