from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import ingest, query, auth, user_manager
from langchain_ollama import OllamaLLM
from langchain_community.vectorstores import Weaviate as WeaviateStore
import weaviate
from langchain_community.embeddings import OllamaEmbeddings
from weaviate import Client as WeaviateClient
from typing import List
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from weaviate.schema.properties import Property
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from models.base import engine, Base, SessionLocal
from models.init_db import init_db
from .auth import router as auth_router
from .user_manager import router as user_router
from .query import router as query_router
from .ingest import router as ingest_router
from .workspaces import router as workspaces_router

app = FastAPI()

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # URL du frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

API_KEY = "YjdmNGQyOTY0MDEyZDAyOGJiMDYyZTI0MDQ0MW"

@app.on_event("startup")
async def startup_event():
    # Création des tables et initialisation de la base de données
    await init_db()

    # Weaviate setup
    app.state.client = weaviate.Client(url="http://10.10.40.11:8080")
    app.state.embedding = OllamaEmbeddings(model="nomic-embed-text", model_kwargs={"trust_remote_code": True}, base_url="http://192.168.1.19:11434")
    app.state.llm = OllamaLLM(base_url="http://192.168.1.19:11434", model="llama3.2:3b")
    app.state.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Setup schema Weaviate
    schema = app.state.client.schema.get()
    classes = schema.get("classes", [])
    ao_class = next((cls for cls in classes if cls.get("class") == "AO"), None)

    expected_props = {
        "text": "text",
        "source": "text",
        "hash": "text",
        "workspace_id": "text",
        "confidentiality": "text",
        "chunk_index": "int",
        "type": "text",
        "section_title": "text",
        "idx_table": "int",
        "table_chunk_index": "int",
        "page_num": "int"
    }
   
    if not ao_class:
        # Créer la classe avec toutes les propriétés
        app.state.client.schema.create_class({
            "class": "AO",
            "description": "Contient les chunks de documents ingérés",
            "vectorizer": "none",
            "properties": [{"name": k, "dataType": [v]} for k, v in expected_props.items()]
        })
        print("Schéma 'AO' créé avec toutes les propriétés.")
    else:
        # Vérifier et ajouter les propriétés manquantes
        existing_props = {prop["name"] for prop in ao_class.get("properties", [])}
        missing_props = {name: dtype for name, dtype in expected_props.items() if name not in existing_props}
        
        if missing_props:
            print(f"Propriétés manquantes détectées : {list(missing_props.keys())}")
            for name, dtype in missing_props.items():
                try:
                    app.state.client.schema.property.create(
                        schema_class_name="AO",
                        schema_property={
                            "name": name,
                            "dataType": [dtype]
                        }
                    )
                    print(f"✅ Propriété '{name}' ajoutée à la classe 'AO'.")
                except Exception as e:
                    print(f"⚠️ Erreur lors de l'ajout de la propriété '{name}': {e}")
        else:
            print("✅ Toutes les propriétés requises sont présentes dans le schéma.")

    app.state.vectorstore = WeaviateStore(
        embedding=app.state.embedding,
        client=app.state.client,
        index_name="AO",
        text_key="text",
        by_text=False,
        attributes=list(expected_props.keys())  # Utiliser les mêmes propriétés que dans le schéma
    )

# API routes
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(user_router, prefix="/api", tags=["users"])
app.include_router(query_router, prefix="/api", tags=["query"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(workspaces_router, prefix="/api", tags=["workspaces"])

@app.get("/")
async def root():
    return {"message": "L'API RAG est en service"}
