import io
import pdfplumber
import re
import os
from pathlib import Path
import fitz  # PyMuPDF
import math
from collections import Counter 

def tableau_en_markdown(table):
    if not table or not any(table):
        return ""

    lignes_md = []
    nb_colonnes = max(len(row) for row in table)

    def clean(cell):
        return cell.strip().replace('\n', ' ') if cell else ""

    en_tete = [clean(cell) for cell in table[0]]
    lignes_md.append("| " + " | ".join(en_tete) + " |")
    lignes_md.append("| " + " | ".join(["---"] * len(en_tete)) + " |")

    for ligne in table[1:]:
        ligne_md = [clean(cell) for cell in ligne] + [""] * (nb_colonnes - len(ligne))
        lignes_md.append("| " + " | ".join(ligne_md) + " |")

    return "\n".join(lignes_md)

def extract_text_and_tables_markdown(pdf_bytes: bytes, filename: str = "extraction.txt") -> str:
    texte_final = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texte_page = page.extract_text()
            if texte_page:
                texte_final += texte_page.strip() + "\n\n"
            for table in page.extract_tables():
                markdown_table = tableau_en_markdown(table)
                if markdown_table:
                    texte_final += markdown_table + "\n\n"

    # 💾 Sauvegarde dans le dossier 'extractions/'
    os.makedirs("extractions", exist_ok=True)
    with open(os.path.join("extractions", filename), "w", encoding="utf-8") as f:
        f.write(texte_final)

    return texte_final

def detect_lignes_recurrentes(pages: list[list[str]], seuil: float = 0.6) -> set[str]:
    """
    Détecte les lignes qui apparaissent sur une proportion significative des pages (entêtes ou pieds de page).
    """
    nb_pages = len(pages)
    ligne_counts = Counter()

    for page in pages:
        uniques = set(page)
        for ligne in uniques:
            ligne_counts[ligne.strip()] += 1

    return {ligne for ligne, count in ligne_counts.items() if count / nb_pages >= seuil}


def clean_lines(raw_text: str, lignes_a_ignorer: set[str] = None) -> list[str]:
    lines = raw_text.splitlines()
    lines = [re.sub(r'[\u00a0]', ' ', l).strip() for l in lines if l.strip()]
    cleaned = []
    buffer = ""
    lignes_a_ignorer = lignes_a_ignorer or set()

    for line in lines:
        line = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', line).strip()
        if not line or line in lignes_a_ignorer:
            continue

        if re.match(r'^Page\s+\d+\s+sur\s+\d+', line, re.IGNORECASE):
            continue

        if re.match(r'^\d+$', line):
            if buffer:
                buffer += ' ' + line
                cleaned.append(buffer)
                buffer = ""
            else:
                cleaned.append(line)
        elif re.search(r'\.{3,}', line):
            if buffer:
                buffer += ' ' + line
                cleaned.append(buffer)
                buffer = ""
            else:
                cleaned.append(line)
        else:
            if buffer:
                buffer += ' ' + line
            else:
                buffer = line

    if buffer:
        cleaned.append(buffer)
    return cleaned

def extraire_titres_sommaire(pdf_path: str, max_pages: int = 7) -> list[str]:
    def load_pdf_text(path, max_pages):
        text = ""
        pages = []
        doc = fitz.open(path)
        for i in range(min(len(doc), max_pages)):
            page = doc.load_page(i)
            page_text = page.get_text()
            lines = [l.strip() for l in page_text.splitlines() if l.strip()]
            pages.append(lines)
            text += "\n".join(lines) + "\n"
            joined_lines = '\n'.join(lines[:5])
            print(f"\n=== Page {i+1} ===\n{repr(joined_lines)}")

        return text, pages

    def extract_toc_lines(lines):
        toc = []

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Cas : "Article 1 DEFINITIONS ......... 3"
            match = re.match(r'^(ARTICLE\s+\d+\s+.+?)\.{3,}\s*\d{1,3}$', line, re.IGNORECASE)
            if match:
                toc.append(match.group(1).strip())
                continue

            # Cas : "Article 1" seul → titre sur deux lignes
            match = re.match(r'^\s*ARTICLE\s+\d+\s*$', line, re.IGNORECASE)
            if match:
                i = idx + 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line:
                        full_title = f"{line.strip()} {next_line.strip()}"
                        toc.append(full_title)
                        break
                    i += 1
                continue

            # Cas : "1.1.2 Titre" .... 4
            match = re.match(r'^((\d+(\.\d+)+)\s+.+?)\.{3,}\s*(\d{1,3})$', line)
            if match:
                toc.append(match.group(1).strip())
                continue

            # Cas : "II.1 Quelque chose" page 5
            match = re.match(r'^(([IVXLCDM]+\.\d+.*?)\s+.+?)(\d{1,3})$', line, re.IGNORECASE)
            if match:
                toc.append(match.group(1).strip())
                continue

            # Cas : "AB1-UO2 : Titre ....... 4"
            match = re.match(r'^([A-Z]+\d+-UO\d+\s*:\s+.+?)\.{3,}\s*(\d{1,3})$', line, re.IGNORECASE)
            if match:
                toc.append(match.group(1).strip())
                continue

            # Fallback : tentative de détection multi-ligne pour autres formats
            multiline_start = re.match(
                r'^(ARTICLE\s+\d+.*|(\d+(\.\d+)+)\s+.*|[IVXLCDM]+\.\d+.*|[A-Z]+\d+-UO\d+\s*:\s+.*)$',
                line, re.IGNORECASE
            )
            if multiline_start:
                temp_title = line
                i = idx + 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if re.match(r'^\s*\d{1,3}$', next_line):
                        toc.append(temp_title.strip())
                        break
                    page_match = re.match(r'(?:\.{3,}\s*)?(\d{1,3})$', next_line)
                    if page_match:
                        toc.append(temp_title.strip())
                        break
                    temp_title += ' ' + next_line
                    i += 1
                continue

        return toc

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"❌ Fichier introuvable : {pdf_path}")

    raw_text, pages_lines = load_pdf_text(pdf_path, max_pages=max_pages)
    lignes_recurrentes = detect_lignes_recurrentes(pages_lines)

    print("\n📌 Lignes ignorées (entêtes récurrents détectés) :")
    for l in lignes_recurrentes:
        print(f"  - {l}")

    lines = clean_lines(raw_text, lignes_recurrentes)
    titres = extract_toc_lines(lines)

    print("\n📑 Titres extraits du sommaire :")
    for titre in titres:
        print(f" - {titre}")

    return titres

def normaliser_texte(t):
    return re.sub(r'[\W_]+', ' ', t).lower().strip()

def balise_titres_sections(texte: str, sommaire: list[str]) -> str:
    """
    Balise uniquement les titres présents dans le sommaire.
    """
    lignes = texte.splitlines()
    lignes_balisees = []

    titres_sommaire = set(normaliser_texte(t) for t in sommaire)

    for ligne in lignes:
        ligne_stripped = ligne.strip().replace('\u00a0', ' ')
        ligne_stripped = re.sub(r'[\r\n\t\f\v]', '', ligne_stripped)
        ligne_normalisee = normaliser_texte(ligne_stripped)

        if ligne_normalisee in titres_sommaire:
            lignes_balisees.append(f"# {ligne_stripped}")
        else:
            lignes_balisees.append(ligne)

    texte_balise = "\n".join(lignes_balisees)

    # Écrit le fichier dans le dossier
    with open(os.path.join("balises", "texte_balise.txt"), "w", encoding="utf-8") as f:
        f.write(texte_balise)

    return texte_balise

def regrouper_par_sections(texte_balise: str) -> dict:
        """
        Prend un texte balisé (avec # Titre) et retourne un dictionnaire {titre: contenu}.
        """
        sections = {}
        current_title = None
        current_content = []

        for line in texte_balise.splitlines():
            if line.strip().startswith("#") and len(line.strip()) > 1:
                if current_title is not None:
                    sections[current_title] = "\n".join(current_content).strip()
                current_title = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_title is not None:
            sections[current_title] = "\n".join(current_content).strip()

        return sections

async def summarize_section(section_title: str, text: str, llm, chunk_word_limit: int = 1500) -> str:
    """
    Résume une section en ajoutant son titre au début (sans balise #).
    Si le texte est court, on retourne simplement : titre + texte nettoyé.
    Sinon, on découpe en chunks et on fait appel au LLM.
    """
    def nettoyer_texte(t):
        t = re.sub(r'\n\s*\n', '\n\n', t)         # lignes vides multiples → une seule
        t = re.sub(r'[ \t]+', ' ', t)             # espaces multiples → un espace
        t = re.sub(r' +\n', '\n', t)              # espaces en fin de ligne
        t = re.sub(r'\n+', '\n', t)               # sauts de ligne multiples → un seul
        return t.strip()

    text = nettoyer_texte(text)
    words = text.split()

    if len(words) <= chunk_word_limit:
        return f"{section_title}\n\n{text}"

    # Sinon, découpage + appel LLM
    nb_chunks = math.ceil(len(words) / chunk_word_limit)
    resumes = []

    for i in range(nb_chunks):
        chunk = " ".join(words[i * chunk_word_limit : (i + 1) * chunk_word_limit])
        prompt = f"""Tu es un assistant expert en appels d'offres. Voici un extrait d'un document juridique/technique associé.

Résume ce contenu de manière claire, structurée et concise, en ne conservant **que les informations réellement pertinentes pour comprendre les exigences, prestations attendues, aspects techniques et technologiques, critères contractuels ou autres informations pertinentes à propos du marché**.

Ignore les parties répétitives, génériques ou peu informatives. Si l'extrait ne contient rien d'utile, réponds uniquement : " ".

Extrait :
{chunk}

Résumé :
"""
        try:
            response = await llm.ainvoke(prompt)
            resume = response.strip()
            if resume:
                resumes.append(resume)
        except Exception as e:
            print(f"❌ Erreur dans le résumé d’un chunk : {e}")
            resumes.append(chunk[:1000] + "...")

    resume_final = "\n\n".join(resumes).strip()

    if not resume_final:
        return f"{section_title}\n\n"

    return f"{section_title}\n\n{resume_final}"
