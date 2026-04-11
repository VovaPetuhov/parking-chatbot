import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config.prompts import RAG_SYSTEM_PROMPT, RAG_USER_PROMPT
from config.settings import settings
from core.llm import get_chat_model
from core.vector_store import VectorStoreManager, get_vectorstore

logger = logging.getLogger(__name__)


class RAGSystem:
    
    def __init__(
        self,
        vectorstore_manager: Optional[VectorStoreManager] = None,
        llm: Optional[BaseChatModel] = None,
        parking_name: Optional[str] = None
    ):
        
        self.vectorstore_manager = vectorstore_manager or get_vectorstore(read_only=True)
        self.llm = llm or get_chat_model()
        self.parking_name = parking_name or settings.parking_name
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", RAG_USER_PROMPT)
        ])
        
        # Create retrieval chein
        self.retriever = self.vectorstore_manager.get_retriever()
        logger.info("RAG System initialised")
    
    def _format_docs(self, docs: List[Document]) -> str:
        if not docs:
            return "No relevant information found in the knowledge base."
        
        formatted = []
        for i, doc in enumerate(docs, 1):
            formatted.append(f"[Source {i}]\n{doc.page_content}\n")
        
        return "\n".join(formatted)
    
    def retrieve_context(self, query: str) -> List[Document]:
        logger.info(f"Retrieving context for: {query}")
        docs = self.vectorstore_manager.similarity_search(query)
        logger.info(f"Retrieved {len(docs)} relevant documents")
        return docs
    
    def generate_answer(
        self,
        question: str,
        chat_history: Optional[List] = None
    ) -> str:
        logger.info(f"Generating answer for: {question}")
        
        # Retrieve our context
        docs = self.retrieve_context(question)
        context = self._format_docs(docs)
        
        # Prepare messages
        messages = {
            "parking_name": self.parking_name,
            "context": context,
            "question": question,
            "chat_history": chat_history or []
        }
        
        # Generate response
        chain = self.prompt | self.llm | StrOutputParser()
        response = chain.invoke(messages)
        logger.info("Answer generated")
        return response
    
    def create_conversational_chain(self):
        # TODO: in progress (not currently used)
        # def format_chat_history(messages: List) -> str:
        #     """Format chat history for context"""
        #     if not messages:
        #         return ""
            
        #     formatted = []
        #     for msg in messages:
        #         if isinstance(msg, HumanMessage):
        #             formatted.append(f"User: {msg.content}")
        #         elif isinstance(msg, AIMessage):
        #             formatted.append(f"Assistant: {msg.content}")
            
        #     return "\n".join(formatted)
        
        chain = (
            {
                "context": lambda x: self._format_docs(self.retrieve_context(x["question"]) ),        
                "question": lambda x: x["question"],
                "chat_history": lambda x: x.get("chat_history", []),
                "parking_name": lambda x: self.parking_name
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        return chain
    
    def get_stats(self) -> dict:
        vectorstore_stats = self.vectorstore_manager.get_stats()
        return {
            "llm_model": self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown",
            "parking_name": self.parking_name,
            "vectorstore": vectorstore_stats
        }


def get_rag_system(
    vectorstore_manager: Optional[VectorStoreManager] = None,
    llm: Optional[BaseChatModel] = None
) -> RAGSystem:
    return RAGSystem(
        vectorstore_manager=vectorstore_manager,
        llm=llm
    )
