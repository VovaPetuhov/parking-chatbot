import logging
from functools import lru_cache
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory for creating and caching LLM instances
    """
    
    @staticmethod
    @lru_cache(maxsize=4)
    def create_chat_model(
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseChatModel:

        model_name = model_name or settings.openai_model_name
        temperature = temperature if temperature is not None else settings.openai_temperature
        max_tokens = max_tokens or settings.max_tokens
        logger.info(f"Creating chat model: {model_name} (temp={temperature}, max_tokens={max_tokens})")
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.openai_api_key,
            **kwargs
        )
    
    @staticmethod
    @lru_cache(maxsize=2)
    def create_embeddings(model: str = "text-embedding-3-small", **kwargs) -> Embeddings:

        logger.info(f"Creating embeddings model: {model}")
        
        return OpenAIEmbeddings(
            model=model,
            api_key=settings.openai_api_key,
            **kwargs
        )


def get_chat_model(temperature: Optional[float] = None,**kwargs) -> BaseChatModel:
    return LLMFactory.create_chat_model(temperature=temperature, **kwargs)


def get_embeddings() -> Embeddings:
    return LLMFactory.create_embeddings()


def get_cheap_model() -> BaseChatModel:
    return LLMFactory.create_chat_model(
        model_name="gpt-4o-mini",
        temperature=0.0)


def get_smart_model() -> BaseChatModel:
    return LLMFactory.create_chat_model(
        model_name="gpt-4o",
        temperature=0.0
    )


def get_creative_model() -> BaseChatModel:
    return LLMFactory.create_chat_model(
        temperature=0.7
    )
