from .DocumentHandler import DocumentHandler
import os
from .preprocessing import *

class PDFHandler(DocumentHandler):
    def __init__(self, content: bytes):
        self.content = content  # PDF binaire

    async def load(self, filename: str, llm) -> str:
        """
        Charge un PDF, extrait le texte et les tableaux, balise les titres, découpe par sections
        et génère un résumé par section.

        Retourne : un texte balisé contenant le résumé de chaque section.
        """

        # Extraire texte brut + tables, contenu dans extractions
        texte = extract_text_and_tables_markdown(self.content, filename=os.path.basename(filename) + ".txt")

        # Extraire le sommaire du pdf
        sommaire = extraire_titres_sommaire(filename)

        # Baliser texte en utilisant les titres présents dans sommaire
        texte_balise = balise_titres_sections(texte, sommaire)

        # Séparer l’introduction (avant #) du reste
        parties = re.split(r"(?=^# )", texte_balise, maxsplit=1, flags=re.MULTILINE)
        intro_text = parties[0].strip()
        reste_balise = parties[1] if len(parties) > 1 else ""

        # Résumé de l’intro
        resume = ""
        if intro_text:
            intro_summary = await summarize_section("Introduction", intro_text, llm=llm)
            resume += f"# Introduction\n\n{intro_summary}\n\n{'=' * 80}\n\n"

        # Regrouper et résumer le reste
        sections = regrouper_par_sections(reste_balise)
        for titre, contenu in sections.items():
            resume_section = await summarize_section(titre, contenu, llm=llm)
            resume += f"# {titre}\n\n{resume_section}\n\n{'=' * 80}\n\n"

        return resume
