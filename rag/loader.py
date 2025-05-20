from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from schemas.user_schema import ConfidentialityLevel
import logging
from typing import List, Tuple
import hashlib
logging.getLogger("fitz").setLevel(logging.ERROR)
import re
from typing import List, Tuple
from .Handler.PDFHandler import PDFHandler
from .Handler.WordHandler import WordHandler
from .Handler.MarkdownHandler import MarkdownHandler

# Initialisation du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_handler_for_file(filename: str, file_bytes: bytes):
    # Vérifie l'extension du fichier et instancie le bon handler
    if filename.endswith('.pdf'):
        return PDFHandler(file_bytes)  # Assurez-vous de passer file_bytes ici
    elif filename.endswith('.docx'):
        return WordHandler(file_bytes)  # Pour Word aussi, il faudrait passer file_bytes
    elif filename.endswith('.md'):  # Vérification pour le format Markdown
        return MarkdownHandler(file_bytes)  # Instanciation du handler pour Markdown
    else:
        raise ValueError(f"Unsupported file type: {filename}") 

def compute_sha256(content: bytes) -> str:
    """
    Retourne un hash SHA-256 sous forme de chaîne hexadécimale
    """
    return hashlib.sha256(content).hexdigest()


async def load_document_with_hash(filename: str, file_bytes: bytes, workspace_id: str, confidentiality: ConfidentialityLevel, vectorstore, llm) -> Tuple[str, str, str, str, str] :
    """
    Identifie le type de document
    Sélectionne le bon handler
    Appelle la fonction load qui correspond pour chargé le texte résumé balisé
    Renvoie le texte résumé balisé avec les metadata
    """
    logger.info(f"📄 Chargement du fichier : {filename}")

    try:
        handler = get_handler_for_file(filename, file_bytes)

        # Maintenant on va vérifier si on doit ouvrir le fichier en binaire ou en texte
        if filename.endswith('.md'):  # Si c'est un fichier Markdown
            # Ouvrir en mode texte pour les fichiers Markdown
            with open(filename, "r") as f:
                file_text = f.read()
            file_bytes = file_text.encode('utf-8')  # Convertir le texte en bytes si nécessaire pour la signature

        else:
            # Sinon, on ouvre en mode binaire pour PDF ou DOCX
            with open(filename, "rb") as f:
                file_bytes = f.read()

        file_hash = compute_sha256(file_bytes)
        logger.info(f"🔑 Hash SHA-256 calculé : {file_hash}")
        
        query_result = vectorstore._client.query.get("AO", ["hash"]).with_where({
            "path": ["hash"],
            "operator": "Equal",
            "valueText": file_hash
        }).with_limit(1).do()

        hits = query_result.get("data", {}).get("Get", {}).get("AO", [])
        if hits:
            logger.warning(f"⚠️ Doublon détecté : {filename}, hash : {file_hash}")
            return None

        # 💡 Nouvelle extraction mixée, ordonnée
        texte_résumé_balisé = await handler.load(filename, llm)  # Chargement via le handler

        source = filename

        return texte_résumé_balisé, source, file_hash, workspace_id, confidentiality

    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement du fichier {filename} : {e}")
        return None

def split_documents(texte_résumé_balisé: str, source: str, hash: str, workspace_id: str, confidentiality: ConfidentialityLevel, chunk_size: int = 500, overlap: int = 55) -> List[Document]:
    """
    Découpe un texte balisé (# Titre) en chunks avec métadonnées.
    - Section "Introduction" traitée avant la première balise.
    - Chaque chunk porte les métadonnées de sa section.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", "!", "?"]
    )

    chunks = []
    idx = 0
    section_idx = 0
    current_title = "Introduction"
    buffer = []

    def flush_buffer(title: str, content_lines, section_idx):
        nonlocal idx
        text = "\n".join(content_lines).strip()
        if not text:
            return
        for chunk in splitter.split_text(text):
            metadata = {
                "chunk_index": idx,
                "source": source,
                "hash": hash,
                "section_title": title,
                "section_idx": section_idx,
                "workspace_id": workspace_id,
                "confidentiality": confidentiality
            }
            chunks.append(Document(page_content=chunk.strip(), metadata=metadata))
            idx += 1

    for line in texte_résumé_balisé.splitlines():
        match = re.match(r"^# (.+)$", line.strip())
        if match:
            # On flush le buffer de l'ancienne section
            flush_buffer(current_title, buffer, section_idx)
            # Nouvelle section
            current_title = match.group(1).strip()
            section_idx += 1
            buffer = []
        else:
            buffer.append(line)

    # Dernier flush (fin de fichier)
    flush_buffer(current_title, buffer, section_idx)

    return chunks

def index_documents(chunks: List[Document], vectorstore):
    """
    Indexe une liste de chunks dans le vectorstore.
    """
    if not chunks:
        logger.warning("⚠️ Aucun chunk à indexer.")
        return {"status": "no_chunks"}
    try:
        vectorstore.add_documents(chunks)
        chunk = chunks[0]
        print("Contenu du chunk")
        print(chunk.page_content)
        logger.info(f"✅ {len(chunks)} chunk(s) indexé(s) avec succès.")
        return {"status": "ok", "chunks_indexed": len(chunks)}
    except Exception as e:
        logger.error(f"❌ Échec de l’indexation : {e}")
        return {"status": "error", "message": str(e)}