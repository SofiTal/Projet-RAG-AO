from .DocumentHandler import DocumentHandler
from .preprocessing import regrouper_par_sections, summarize_section
import io
from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn
import re

class WordHandler(DocumentHandler):
    def __init__(self, content: bytes):
        self.content = content

    def iter_block_items(self, parent):
        """Génère les Paragraphs et Tables dans l'ordre du document."""
        body = parent.element.body
        for child in body.iterchildren():
            if child.tag == qn('w:p'):
                yield Paragraph(child, parent)
            elif child.tag == qn('w:tbl'):
                yield Table(child, parent)

    def extract_text_and_tables_markdown(self) -> str:
        """Extrait le texte + tableaux, en markdown, dans l'ordre du document."""
        doc = DocxDocument(io.BytesIO(self.content))
        title_styles = ["CCTP - Titre 1", "CCTP - Titre 2", "CCTP - Titre 3"]
        output = ""

        for block in self.iter_block_items(doc):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text or text == ".":
                    continue

                # Titre détecté via style
                if block.style and block.style.name in title_styles:
                    output += f"\n\n# {text}\n\n"
                else:
                    output += f"{text}\n\n"

            elif isinstance(block, Table):
                rows_data = []
                for row in block.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    if any(row_data):
                        rows_data.append(row_data)

                if rows_data:
                    # Format markdown table
                    header = rows_data[0]
                    rows = rows_data[1:]
                    table_md = (
                        "| " + " | ".join(header) + " |\n" +
                        "| " + " | ".join(["---"] * len(header)) + " |\n" +
                        "\n".join(["| " + " | ".join(row) + " |" for row in rows])
                    )
                    output += f"{table_md}\n\n"

        return output.strip()

    async def load(self, filename: str, llm) -> str:
        """
        Charge un DOCX, extrait texte + tables, balise les titres,
        découpe en sections, résume chaque section, retourne le texte balisé final.
        """
        # Étape 1 : extraction brute markdown avec # pour les titres
        texte = self.extract_text_and_tables_markdown()

        # Étape 2 : rebaliser pour que ce soit propre et structuré (utile si on change les titres)
        # Ici, on suppose que les balises ont déjà été insérées (via styles Word)
        texte_balise = texte

        # Étape 3 : séparer l’introduction (avant #) du reste
        parties = re.split(r"(?=^# )", texte_balise, maxsplit=1, flags=re.MULTILINE)
        intro_text = parties[0].strip()
        reste_balise = parties[1] if len(parties) > 1 else ""

        # Étape 4 : résumé de l’intro
        resume = ""
        if intro_text:
            intro_summary = await summarize_section("Introduction", intro_text, llm=llm)
            resume += f"# Introduction\n\n{intro_summary}\n\n{'=' * 80}\n\n"

        # 4. Regrouper et résumer le reste
        sections = regrouper_par_sections(reste_balise)
        for titre, contenu in sections.items():
            resume_section = await summarize_section(titre, contenu, llm=llm)
            resume += f"# {titre}\n\n{resume_section}\n\n{'=' * 80}\n\n"

        return resume