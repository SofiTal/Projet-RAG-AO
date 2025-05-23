from fastapi import APIRouter, Request, UploadFile, File, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_db
from .auth import require_admin_role
from models.user_model import User
from rag.loader import load_document_with_hash, index_documents, split_documents
from shared.enums import ConfidentialityLevel
from typing import List
import os
import tempfile

router = APIRouter()

@router.post("/ingest")
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    workspace_id: str = None,
    confidentiality: str = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_role)
):
    try:
        contents = await file.read()

        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, file.filename)

        with open(temp_file_path, "wb") as f:
            f.write(contents)

        vectorstore = request.app.state.vectorstore
        llm = request.app.state.llm

        result = await load_document_with_hash(file.filename, contents, workspace_id, confidentiality, vectorstore, llm)
        if result is None:
            os.remove(temp_file_path)
            return {"message": f"❌ Document déjà indexé : {file.filename}"}

        texte_résumé_balisé, source, hash, workspace_id, confidentiality = result

        # 💾 Sauvegarder le résumé balisé brut dans un fichier
        filename_base = os.path.splitext(file.filename)[0]
        resume_dir = "resumes"
        os.makedirs(resume_dir, exist_ok=True)
        resume_balisé_path = os.path.join(resume_dir, f"{filename_base}_resume_balisé.txt")
        with open(resume_balisé_path, "w", encoding="utf-8") as f:
            f.write(texte_résumé_balisé)

        chunks = split_documents(texte_résumé_balisé, source, hash, workspace_id, confidentiality)
        index_documents(chunks=chunks, vectorstore=vectorstore)

        os.remove(temp_file_path)

        return {
            "message": "✅ Document indexé avec succès",
            "chunks_indexed": len(chunks)
        }

    except Exception as e:
        return {"message": f"Erreur : {str(e)}"}
 
@router.post("/ingests")
async def ingest_multiple_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    workspace_id: str = Form(...),
    confidentiality: ConfidentialityLevel = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_role)
):
    all_chunks = []
    already_indexed = []
    indexed_files = []

    try:
        vectorstore = request.app.state.vectorstore
        llm = request.app.state.llm
        for file in files:
            contents = await file.read()

            result = await load_document_with_hash(file.filename, contents, workspace_id, confidentiality, vectorstore, llm)
            if result is None:
                already_indexed.append(file.filename)
                continue

            texte_résumé_balisé, source, hash, workspace_id, confidentiality = result

            # 💾 Sauvegarder le résumé balisé brut dans un fichier
            filename_base = os.path.splitext(file.filename)[0]
            resume_dir = "resumes"
            os.makedirs(resume_dir, exist_ok=True)
            resume_balisé_path = os.path.join(resume_dir, f"{filename_base}_resume_balisé.txt")
            with open(resume_balisé_path, "w", encoding="utf-8") as f:
                f.write(texte_résumé_balisé)

            chunks = split_documents(texte_résumé_balisé, source, hash, workspace_id, confidentiality)
            all_chunks.extend(chunks)
            indexed_files.append(file.filename)

        if all_chunks:
            index_documents(chunks=all_chunks, vectorstore=vectorstore)

        return {
            "message": f"{len(indexed_files)} documents indexés avec succès",
            "indexed_files": indexed_files,
            "already_indexed": already_indexed,
            "total_chunks_indexed": len(all_chunks)
        }

    except Exception as e:
        return {"message": f"Erreur : {str(e)}"}