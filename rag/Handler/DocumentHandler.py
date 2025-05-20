from abc import ABC, abstractmethod
from typing import List
from langchain.schema import Document

class DocumentHandler(ABC):

    @abstractmethod
    def load(self, filename: str, workspace_id: str, confidentiality, file_hash: str) -> List[Document]:
        raise NotImplementedError