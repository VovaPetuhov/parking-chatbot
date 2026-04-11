import logging
from typing import List, Optional

from langchain_community.vectorstores import DeepLake
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from config.settings import settings
from core.llm import get_embeddings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    
    def __init__(
        self,
        dataset_path: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        read_only: bool = False
    ):
        self.dataset_path = dataset_path or settings.deeplake_path
        self.embeddings = embeddings or get_embeddings()
        self.read_only = read_only
        self._vectorstore: Optional[VectorStore] = None
        logger.info(f"Initialized VectorStoreManager: {self.dataset_path}")
    
    @property
    def vectorstore(self) -> VectorStore:
        if self._vectorstore is None:
            self._vectorstore = self._load_or_create_vectorstore()
        return self._vectorstore
    
    def _load_or_create_vectorstore(self) -> VectorStore:
        try:
            logger.info(f"Loading DeepLake from: {self.dataset_path}")
            vectorstore = DeepLake(
                dataset_path=self.dataset_path,
                embedding=self.embeddings,
                read_only=self.read_only,
                token=settings.deeplake_token
            )
            logger.info("DeepLake loaded successfully")
            return vectorstore
            
        except Exception as e:
            logger.warning(f"Could not load existing dataset: {e}")
            if self.read_only:
                raise RuntimeError("Cannot create new dataset in read-only mode")
            logger.info("Creating new DeepLake dataset...")
            return self._create_new_vectorstore()
    
    def _create_new_vectorstore(self) -> VectorStore:
        logger.info(f"Creating new DeepLake dataset at: {self.dataset_path}")
        vectorstore = DeepLake(
            dataset_path=self.dataset_path,
            embedding=self.embeddings,
            token=settings.deeplake_token,
            overwrite=False  # Don't overwrite if exists, will raise error instead
        )
        logger.info("New DeepLake dataset created")
        return vectorstore
    
    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 100
    ) -> List[str]:
        if self.read_only:
            raise RuntimeError("Cannot add documents in read-only mode")        
        ids = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_ids = self.vectorstore.add_documents(batch)
            ids.extend(batch_ids)
        logger.info(f"Added {len(ids)} documents")
        return ids
    
    def similarity_search(
        self,
        query: str,
        k: Optional[int] = None,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        k = k or settings.top_k_results
        docs_and_scores = self.vectorstore.similarity_search_with_score(
            query,
            k=k
        )
        threshold = score_threshold or settings.similarity_threshold
        filtered_docs = [doc for doc, score in docs_and_scores if score >= threshold]
        logger.info(f"Found {len(filtered_docs)} documents above threshold {threshold}")
        return filtered_docs
    
    def get_retriever(self, **kwargs):
        search_kwargs = {"k": kwargs.pop("k", settings.top_k_results)}
        return self.vectorstore.as_retriever(
            search_kwargs=search_kwargs,
            **kwargs
        )

    def delete_dataset(self):
        if self.read_only:
            raise RuntimeError("Cannot delete dataset in read-only mode")

        try:
            if self.dataset_path.startswith("hub://"):
                import deeplake
                logger.info(f"Deleting cloud dataset: {self.dataset_path}")
                deeplake.delete(self.dataset_path, token=settings.deeplake_token, force=True)
            else:
                # For local datasets, use the vectorstore method
                if self._vectorstore is not None:
                    self._vectorstore.delete_dataset()
                else:
                    import shutil
                    from pathlib import Path
                    dataset_dir = Path(self.dataset_path)
                    if dataset_dir.exists():
                        shutil.rmtree(dataset_dir)
                        logger.info(f"Local dataset directory deleted: {self.dataset_path}")

            self._vectorstore = None
            logger.info("Dataset deleted successfully")

        except Exception as e:
            logger.error(f"Error deleting dataset: {e}")
            raise
    
    def get_stats(self) -> dict:
        try:
            # DeepLake specific stats
            # Note: ds might be a method or property depending on DeepLake version
            ds = self.vectorstore.ds if not callable(self.vectorstore.ds) else self.vectorstore.ds()
            try:
                total_docs = len(ds)
            except TypeError:
                total_docs = ds.shape[0] if hasattr(ds, 'shape') else 0
            return {
                "total_documents": total_docs,
                "dataset_path": self.dataset_path,
                "read_only": self.read_only,
                "embedding_model": self.embeddings.model if hasattr(self.embeddings, 'model') else "unknown"
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


def get_vectorstore(read_only: bool = False) -> VectorStoreManager:
    return VectorStoreManager(read_only=read_only)
