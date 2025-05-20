from fastapi import FastAPI
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

from models.db import Base, engine  # ← moteur async ici

app = FastAPI()
API_KEY = "YjdmNGQyOTY0MDEyZDAyOGJiMDYyZTI0MDQ0MW"

@app.on_event("startup")
async def startup_event():
    # Création des tables avec moteur async
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Weaviate setup
    app.state.client = weaviate.Client(url="http://10.10.40.11:8080")
    app.state.embedding = OllamaEmbeddings(model="nomic-embed-text", model_kwargs={"trust_remote_code": True}, base_url="http://192.168.1.19:11434")
    app.state.llm = OllamaLLM(base_url="http://192.168.1.19:11434", model="llama3.2:3b")
    app.state.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # "linux6200/bge-reranker-v2-m3"

#     # 🔸 Connexion à Weaviate
#     app.state.client = WeaviateClient(
#         url="https://vector.internal.etixway.com",
#         additional_headers={
#             "X-API-Key": API_KEY
#         }
#     )

# #     # # 🔸 Embeddings avec Ollama
#     app.state.embedding = OllamaEmbeddings(
#         model="nomic-embed-text",
#         base_url="https://llm.internal.etixway.com",
#         model_kwargs={
#             "trust_remote_code": True
#         },
#         headers={
#             "X-API-Key": API_KEY
#         }
#     )

# #     # # 🔸 LLM avec Ollama
#     app.state.llm = OllamaLLM(
#     model="llama3.2:3b",
#     base_url="https://llm.internal.etixway.com",
#     client_kwargs={
#         "headers": {
#             "X-API-Key": API_KEY
#         }
#     }
# )
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
        "page_num" : "int"
    }
    # print([method for method in dir(app.state.client.schema) if not method.startswith('_')])
   
    if not ao_class:
        app.state.client.schema.create_class({
            "class": "AO",
            "description": "Contient les chunks de documents ingérés",
            "vectorizer": "none",
            "properties": [{"name": k, "dataType": [v]} for k, v in expected_props.items()]
        })
        print("Schéma 'AO' créé avec toutes les propriétés.")
    else:
        # On récupère la classe spécifique (et non tout le schema)
        existing_props = {prop["name"] for prop in ao_class.get("properties", [])}

        # Ajouter les nouvelles propriétés si besoin
        for name, dtype in expected_props.items():
            if name not in existing_props:
                # Ajouter la propriété manquante via la méthode correcte
                app.state.client.schema.property.create(
                    schema_class_name="AO",
                    schema_property={
                        "name": name,
                        "dataType": [dtype]
                    }
                )
                print(f"Propriété '{name}' ajoutée à la classe 'AO'.")
        print("Vérification des propriétés terminée.")
    # else:
    #     existing_props = {prop["name"] for prop in ao_class.get("properties", [])}
    #     for name, dtype in expected_props.items():
    #         if name not in existing_props:
    #             app.state.client.schema.create_property(class_name="AO", property={
    #                 "name": name,
    #                 "dataType": [dtype]
    #             })
    #             print(f"Propriété '{name}' ajoutée à la classe 'AO'.")

    app.state.vectorstore = WeaviateStore(
        embedding=app.state.embedding,
        client=app.state.client,
        index_name="AO",
        text_key="text",
        by_text=False,
        attributes=["source", "hash", "workspace_id", "confidentiality", "chunk_index", "type", "idx_table", "table_chunk_index", "page_num", "section_title"]
    )

# API routes
app.include_router(ingest.router, prefix="")
app.include_router(query.router, prefix="")
app.include_router(auth.router)
app.include_router(user_manager.router)

@app.get("/")
async def root():
    return {"message": "L'API RAG est en service"}
