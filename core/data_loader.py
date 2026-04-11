import logging
from pathlib import Path
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config.parking_info import PARKING_INFO
from config.settings import DATA_DIR, settings

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and process parking information data"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def load_parking_info(self) -> List[Document]:
        logger.info("Loading parking information...")
        doc = Document(
            page_content=PARKING_INFO,
            metadata={
                "source": "parking_info",
                "type": "general_information",
                "parking_name": settings.parking_name
            }
        )
        # Split into chunks
        documents = self.text_splitter.split_documents([doc])
        logger.info(f"Loaded parking info: {len(documents)} chunks")
        return documents
    
    def load_from_file(self, file_path: Path) -> List[Document]:
        logger.info(f"Loading from file: {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        doc = Document(
            page_content=content,
            metadata={
                "source": str(file_path),
                "filename": file_path.name
            }
        )
        
        # Split into chunks
        documents = self.text_splitter.split_documents([doc])
        logger.info(f"Loaded from file: {len(documents)} chunks")
        return documents
    
    def load_all_data(self) -> List[Document]:
        all_documents = []
        all_documents.extend(self.load_parking_info())
        
        # Load from raw data directory if exists
        raw_data_dir = DATA_DIR / "raw"
        if raw_data_dir.exists():
            for file_path in raw_data_dir.glob("*.txt"):
                try:
                    docs = self.load_from_file(file_path)
                    all_documents.extend(docs)
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents


def get_data_loader() -> DataLoader:
    return DataLoader()
