import logging
import sys

from config.settings import settings
from core.data_loader import get_data_loader
from core.vector_store import VectorStoreManager, get_vectorstore

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


logger = logging.getLogger(__name__)


def initialize_database(force_recreate: bool = False):
    """Initialize vector database with parking data.

    Args:
        force_recreate: If True, delete existing database and recreate from scratch
    """
    logger.info("Starting database initialization...")
    try:
        vectorstore_manager = get_vectorstore(read_only=False)
        stats = vectorstore_manager.get_stats()
        existing_docs = stats.get("total_documents", 0)

        if existing_docs > 0 and not force_recreate:
            logger.info(f"Database already initialized with {existing_docs} documents")
            logger.info("Use --force to recreate the database")
            return

        if force_recreate and existing_docs > 0:
            logger.warning("Deleting existing database...")
            vectorstore_manager.delete_dataset()
            vectorstore_manager = VectorStoreManager(read_only=False)

        # Load data
        logger.info("Loading parking data...")
        data_loader = get_data_loader()
        documents = data_loader.load_all_data()

        # Add data to vector DB
        logger.info("Adding documents to vector store...")
        ids = vectorstore_manager.add_documents(documents)

        # Verify DB
        final_stats = vectorstore_manager.get_stats()
        logger.info(f"Final statistics: {final_stats}")

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise


if __name__ == "__main__":
    force = "--force" in sys.argv or "-f" in sys.argv
    initialize_database(force_recreate=force)
