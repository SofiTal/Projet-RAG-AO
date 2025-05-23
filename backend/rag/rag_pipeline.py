import logging
from typing import List
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from langchain.schema import Document

logging.basicConfig(level=logging.DEBUG)  # au lieu de INFO
logger = logging.getLogger(__name__)
   
def rerank_documents(query: str, documents: List[Document], model_name, top_k: int = 5) -> List:
    """
    Rerank documents using a CrossEncoder model (like BGE-Reranker, MS-MARCO, etc.)

    Args:
        query (str): The user query.
        documents (List): A list of documents, each having `.page_content`.
        model_name: Model name (string) or already loaded model.
        top_k (int): Number of top documents to return.
    Returns:
        List: Top-k reranked documents.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)

    device = ("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    scores = []
    logger.info(f"💡 Début du reranking avec {len(documents)} documents pour la query: '{query}'")
    for doc in documents:
        inputs = tokenizer(query, doc.page_content, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
            score = logits[0][0].item() if logits.shape[1] == 1 else logits[0][1].item()
        scores.append(score)

    reranked = [doc for _, doc in sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)]
    return reranked[:top_k]

def get_neighbors(chunk, all_chunks, k=2):
    """
    Retourne les k voisins gauche/droite d'un chunk donné, sans inclure le chunk lui-même.
    """
    doc_source = chunk.metadata["source"]
    chunk_idx = chunk.metadata["chunk_index"]
    section_title = chunk.metadata["section_title"]
    
    # Filtrer les chunks du même document et avec le même titre de section
    same_doc_chunks = [c for c in all_chunks if c.metadata["source"] == doc_source and c.metadata["section_title"] == section_title]
    same_doc_chunks.sort(key=lambda x: x.metadata["chunk_index"])

    idx = next((i for i, c in enumerate(same_doc_chunks) if c.metadata["chunk_index"] == chunk_idx), None)

    if idx is None:
        return []

    neighbors = []
    
    left_neighbors = same_doc_chunks[max(0, idx - k):idx]
    neighbors.extend(left_neighbors)

    # Voisins à droite
    right_neighbors = same_doc_chunks[idx + 1:idx + 1 + k]
    neighbors.extend(right_neighbors)

    return neighbors

def build_context(reranked_docs, all_chunks, k_neighbors=2, min_chunks=16):
    """
    Construit un contexte enrichi à partir des top documents reranked,
    en ajoutant leurs voisins gauche/droite (via get_neighbors),
    jusqu'à atteindre un minimum de `min_chunks` uniques.
    """
    enriched_chunks = []
    seen = set()
    total_chunks = 0

    logger.info(f"🧱 Début de la construction du contexte avec min_chunks={min_chunks}")

    i = 0  # Index du document reranké actuel
    while total_chunks < min_chunks and i < len(reranked_docs):
        doc = reranked_docs[i]
        key = (doc.metadata["source"], doc.metadata["chunk_index"])

        # Ajouter le document lui-même s'il n'est pas encore dans enriched_chunks
        if key not in seen:
            enriched_chunks.append(doc)
            seen.add(key)
            total_chunks += 1
            logger.info(f"🧱 Ajout doc principal : {key}")

        # Ajouter ses voisins gauche/droite
        neighbors = get_neighbors(doc, all_chunks, k=k_neighbors)
        logger.info(f"🧱 Voisins trouvés pour {key} : {len(neighbors)}")

        for neighbor in neighbors:
            n_key = (neighbor.metadata["source"], neighbor.metadata["chunk_index"])
            if n_key not in seen and \
               neighbor.metadata["source"] == doc.metadata["source"] and \
               neighbor.metadata["section_title"] == doc.metadata["section_title"]:
                enriched_chunks.append(neighbor)
                seen.add(n_key)
                total_chunks += 1
                logger.info(f"🧱 Ajout voisin : {n_key}")

            if total_chunks >= min_chunks:
                break

        i += 1

    if total_chunks < min_chunks:
        logger.warning(f"🛑 Nombre insuffisant de chunks après enrichissement : {total_chunks}/{min_chunks}")

    # Tri logique par source et index
    enriched_chunks.sort(key=lambda x: (x.metadata["source"], x.metadata["chunk_index"]))

    # Construction du texte de contexte avec séparations par source
    previous_source = None
    separator = "\n\n"
    contexte_parts = []

    for chunk in enriched_chunks:
        current_source = chunk.metadata["source"]
        if current_source != previous_source and previous_source is not None:
            contexte_parts.append("\n------- Nouvelle source :\n")
        contexte_parts.append(chunk.page_content)
        previous_source = current_source

    contexte = separator.join(contexte_parts)

    logger.info(f"🧱 Contexte construit avec {total_chunks} chunks.")
    logger.info(f"Contexte final (preview 10000c): {contexte[:10000]}")

    return contexte, enriched_chunks

def find_most_relevant_sections(question: str, sections: List[str], model_name: str, top_k: int = 3) -> List[str]:
    """
    Trouve les sections les plus pertinentes en fonction de la similarité entre la question et chaque titre de section.

    Args:
        question (str): La question posée par l'utilisateur.
        sections (List[str]): Liste de titres de section (strings).
        model_name (str): Le nom du modèle utilisé pour calculer la similarité.
        top_k (int): Le nombre de sections les plus pertinentes à renvoyer.

    Returns:
        List[str]: Liste des top-k titres de section les plus pertinents.
    """

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    scores = []

    print(f"🔍 Calcul de la similarité pour la question : {question}")

    for section_title in sections:
        print(f"Comparaison avec le titre : '{section_title}'")

        inputs = tokenizer(question, section_title, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)

        with torch.no_grad():
            logits = model(**inputs).logits
            score = logits[0][1].item() if logits.shape[1] == 2 else logits[0][0].item()

        print(f"Score : {score}")
        scores.append((score, section_title))

    reranked_sections = [title for score, title in sorted(scores, key=lambda x: x[0], reverse=True)[:top_k]]

    print(f"🔝 Sections les plus pertinentes : {reranked_sections}")
    return reranked_sections

def should_use_section_filter(question: str, sections: List[str], model_name: str, top_diff: float = 1.0) -> bool:
    """
    Décide si le filtrage par section est pertinent en comparant le meilleur score au deuxième.
    Cela évite de dépendre d'un seuil absolu de similarité (non fiable sur des logits).
    
    Args:
        question (str): Question utilisateur.
        sections (List[str]): Titres de sections.
        model_name (str): Nom du modèle utilisé.
        top_diff (float): Différence minimale entre le meilleur et le deuxième score pour déclencher le filtre.

    Returns:
        bool: True si filtrage pertinent, sinon False.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    scores = []
    for section_title in sections:
        inputs = tokenizer(question, section_title, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
            score = logits[0][1].item() if logits.shape[1] == 2 else logits[0][0].item()
            scores.append(score)

    sorted_scores = sorted(scores, reverse=True)
    logger.info(f"📊 Top 2 scores section: {sorted_scores[:2]}")
    
    if len(sorted_scores) < 2:
        return True  # Si une seule section, on filtre forcément
    use_filter = (sorted_scores[0] - sorted_scores[1]) >= top_diff

    if use_filter:
        logger.info(f"✅ Filtrage activé : écart de score ({sorted_scores[0] - sorted_scores[1]:.2f}) ≥ seuil ({top_diff})")
    else:
        logger.info(f"❌ Filtrage désactivé : écart de score ({sorted_scores[0] - sorted_scores[1]:.2f}) < seuil ({top_diff})")

    return use_filter

def get_title_documents(documents: List[Document], source) -> List[str]:
    """
    Extrait une liste de titres de sections uniques à partir des documents dont le type est 'title'.
    """
    titres_uniques = set()

    for doc in documents:
        if doc.metadata["source"] == source:
            titres_uniques.add(doc.metadata["section_title"])

    return sorted(titres_uniques)

def poser_question(question, vectorstore, llm, workspace_id, allowed_levels, reranker_model, k=100, top_n_reranked=5, k_neighbors=3, top_k=1) -> dict:
    logger.info(f"❓ Question posée : {question}")
    logger.info(f"🔑 Workspace ID demandé : {workspace_id}")
    logger.info(f"🔒 Niveaux de confidentialité autorisés : {allowed_levels}")

    try:
        # 🔢 Nombre total de documents dans la classe 'AO' (toute la base)
        weaviate_client = vectorstore._client
        count_result = weaviate_client.query.aggregate("AO").with_meta_count().do()
        count = count_result['data']['Aggregate']['AO'][0]['meta']['count']
        logger.info(f"🔢 Nombre de documents dans l'index 'AO' : {count}")
    
        # Crée un retriever avec filtre sur workspace et niveaux de confidentialité
        retriever = vectorstore.as_retriever(search_kwargs={
            "k": count  # ou un chiffre plus raisonnable si tu veux pas reranker 300 docs à chaque fois
        })
        # Recherche vectorielle filtrée
        docs = retriever.get_relevant_documents(query = question)
        logger.info(f"📄 Documents trouvés avant filtrage : {len(docs)}")

        # Étape 2 : filtre à la main sur le workspace_id
        filtered_docs = [
            doc for doc in docs if doc.metadata["workspace_id"] == workspace_id and doc.metadata["confidentiality"] in allowed_levels
        ]
        
        # Logs pour le débogage du filtrage
        for doc in docs[:5]:  # On affiche les 5 premiers documents pour vérifier
            logger.info(f"📝 Document avant filtrage - Workspace: {doc.metadata['workspace_id']}, Confidentiality: {doc.metadata['confidentiality']}")
        
        docs = filtered_docs[:k]
        logger.info(f"🔍 {len(docs)} document(s) trouvé(s) après filtrage vectoriel.")
        
        if not docs:
            logger.warning("❌ Aucun document trouvé après filtrage. Vérifiez que :")
            logger.warning(f"   - Le workspace_id '{workspace_id}' existe dans les documents")
            logger.warning(f"   - Les niveaux de confidentialité {allowed_levels} correspondent aux documents")
            return {"response": "Aucun document pertinent trouvé.", "sources": []}

        # Logs pour les documents filtrés
        for doc in docs[:5]:  # On affiche les 5 premiers documents filtrés
            logger.info(f"✅ Document après filtrage - Workspace: {doc.metadata.get('workspace_id')}, Confidentiality: {doc.metadata.get('confidentiality')}")

        source = docs[0].metadata["source"]
        sections = get_title_documents(docs, source)
        logger.info(f"📚 Sections trouvées : {sections}")

        if should_use_section_filter(question, sections, reranker_model):
            reranked_sections = find_most_relevant_sections(question, sections, reranker_model, top_k)
            docs = [
                doc for doc in docs if doc.metadata["section_title"] in reranked_sections
            ]
            logger.info(f"🔍 {len(docs)} document(s) trouvé(s) après filtrage sections.")
        else:
            logger.info(f"📭 Filtrage par section ignoré (aucune section n'est suffisamment pertinente).")

        if not docs:
            logger.warning("Aucun document trouvé après filtrage.")
            return {"response": "Aucun document pertinent trouvé.", "sources": []}

        # Reranking
        reranked_docs = rerank_documents(question, docs, reranker_model, top_n_reranked)
        logger.info(f"🔍 {len(reranked_docs[:top_n_reranked])} document(s) trouvé(s) après reranking.")

        if not reranked_docs:
            logger.warning("Aucun document pertinent trouvé après reranking.")
            return {"response": "Aucun document pertinent trouvé.", "sources": []}

        logger.info(f"🔝 Reranked docs: {[ (doc.metadata['source'], doc.metadata['chunk_index']) for doc in reranked_docs ]}")

        # Enrichissement de contexte (optionnel)
        contexte, enriched_chunks = build_context(reranked_docs, all_chunks=filtered_docs, k_neighbors=k_neighbors)
        logger.info(f"🔍 {len(enriched_chunks)} document(s) trouvé(s) après enrichissement.")

        # Génération finale
        prompt = (
            f"Tu es un assistant intelligent. Tu dois répondre en français à la question suivante en t'appuyant **exclusivement** sur le texte fourni. "
            f"Ne mélange pas les sources fournies et ne complète jamais avec des connaissances extérieures.\n\n"
            f"### Contexte :\n{contexte}\n"
            f"### Question :\n{question}\n"
            f"### Réponse :"
        )
        response = llm.invoke(prompt)

        sources = [
            {
                "title": doc.metadata["source"],
                "content": doc.page_content,
                "page": doc.metadata.get("page_num")  # Optionnel, peut être None
            }
            for doc in enriched_chunks
        ]

        logger.info(f"✅ Réponse générée : {response[:100]}...")
        return {"response": response, "sources": sources}

    except Exception as e:
        logger.error(f"Erreur lors du traitement de la question : {e}")
        return {"response": "Une erreur s'est produite lors du traitement de la question.", "sources": []}