import io
from typing import List
from langchain.schema import Document
import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension
import re

from .DocumentHandler import DocumentHandler

class MarkdownTableProcessor(Treeprocessor):
    def run(self, root):
        """
        Traite les éléments de type tableau dans le Markdown.
        """
        tables = []
        for element in root.iter():
            if element.tag == 'table':
                table_data = []
                for row in element.iter('tr'):
                    row_data = [cell.text.strip() for cell in row.iter('td')]
                    if any(row_data):
                        table_data.append(row_data)
                tables.append(table_data)
        return tables

class MarkdownHandler(DocumentHandler):
    def __init__(self, content: bytes):
        self.content = content

    def extract_text_and_tables_by_order_clean(self) -> List[dict]:
        """
        Extrait le texte et les tableaux du contenu Markdown.
        """
        elements = []

        # Convertir le Markdown en HTML
        html_content = markdown.markdown(self.content.decode('utf-8'))

        # Analyser le contenu HTML et extraire les tables et le texte
        from lxml import etree
        tree = etree.HTML(html_content)

        # Extraire les tableaux
        tables = MarkdownTableProcessor(tree).run(tree)

        # Ajouter les tableaux extraits
        for table_idx, table in enumerate(tables):
            elements.append({
                "type": "table",
                "content": table,
                "page_num": table_idx  # Simuler le numéro de page
            })

        # Extraire le texte
        text_blocks = re.findall(r'(.*?)(?=\n#|\n$)', self.content.decode('utf-8'))
        for idx, text_block in enumerate(text_blocks):
            cleaned_text = text_block.strip()
            if cleaned_text:
                elements.append({
                    "type": "text",
                    "content": cleaned_text,
                    "page_num": idx
                })

        return elements

    def load(self, filename: str, workspace_id: str, confidentiality, file_hash: str) -> List[Document]:
        """
        Charge le fichier Markdown et retourne une liste de documents (chunks).
        """
        # Récupérer les morceaux de texte extraits
        content_chunks = self.extract_text_and_tables_by_order_clean()
        documents = []

        for idx, chunk in enumerate(content_chunks):
            chunk_type = chunk["type"]
            content = chunk["content"]
            page_num = chunk["page_num"]

            # Formater le contenu en fonction du type (texte ou tableau)
            if chunk_type == "text":
                page_content = content.strip()
            elif chunk_type == "table":
                page_content = (
                    "| " + " | ".join(content[0]) + " |\n" +
                    "| " + " | ".join(["---"] * len(content[0])) + " |\n" +
                    "\n".join(["| " + " | ".join(row) + " |" for row in content[1:]])
                )
            else:
                page_content = ""

            # Ajouter le chunk comme un document LangChain
            documents.append(Document(
                page_content=page_content,
                metadata={
                    "source": filename,
                    "hash": file_hash,
                    "workspace_id": workspace_id,
                    "confidentiality": confidentiality,
                    "type": chunk_type,
                    "page_num": page_num,
                    "chunk_index": idx
                }
            ))

        return documents