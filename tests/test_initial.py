import pytest

from core.llm import get_chat_model, get_embeddings
from guardrails.pii_protection import GuardrailsManager, PIIDetector


def test_llm_creation():
    """Test LLM model creation"""
    llm = get_chat_model()
    assert llm is not None
    assert hasattr(llm, 'invoke')


def test_embeddings_creation():
    """Test embeddings model creation"""
    embeddings = get_embeddings()
    assert embeddings is not None


def test_pii_detector():
    """Test PII detection"""
    detector = PIIDetector()
    result = detector.detect("Hello, I want to reserve parking")
    assert result.has_pii == False
    result = detector.detect("My email is test@example.com")
    assert result.has_pii == True
    assert "email" in result.detected_types


def test_guardrails_manager():
    """Test guardrails manager"""
    manager = GuardrailsManager()
    
    result = manager.check_input("What are your working hours?")
    assert result["should_block"] == False
    
    result = manager.check_input("My SSN is 123-45-6789")
    assert "pii_detected" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
