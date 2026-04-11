import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class PIIDetection:
    has_pii: bool
    detected_types: List[str]
    anonymized_text: str
    score: float
    details: Dict[str, List[str]]


class PIIDetector:    
    # Regex patterns for common PII
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # TODO: need to be adjusted
        "car_plate": r'\b[A-Z]{2,3}[-\s][0-9]{2,4}(?:[-\s][A-Z0-9]{0,3})?\b'
    }
    
    REPLACEMENTS = {
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "credit_card": "[CREDIT_CARD]",
        "car_plate": "[CAR_PLATE]",
    }
    
    def __init__(self, enable_detection: bool = True):
        self.enable_detection = enable_detection
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }
        logger.info(f"PIIDetector initialized (enabled={enable_detection})")
    
    def detect(self, text: str) -> PIIDetection:
        if not self.enable_detection:
            return PIIDetection(
                has_pii=False,
                detected_types=[],
                anonymized_text=text,
                score=0.0,
                details={}
            )
        
        detected_types = []
        details = {}
        anonymized_text = text
        
        for pii_type, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected_types.append(pii_type)
                details[pii_type] = matches if isinstance(matches[0], str) else [m[0] for m in matches]
                replacement = self.REPLACEMENTS[pii_type]
                anonymized_text = pattern.sub(replacement, anonymized_text)
        
        score = min(len(detected_types) / len(self.PATTERNS), 1.0)
        has_pii = len(detected_types) > 0
        
        if has_pii:
            logger.warning(f"PII detected: {detected_types}")
        
        return PIIDetection(
            has_pii=has_pii,
            detected_types=detected_types,
            anonymized_text=anonymized_text,
            score=score,
            details=details
        )
    
    def anonymize(self, text: str) -> str:
        return self.detect(text).anonymized_text
    
    def should_block(self, text: str, threshold: Optional[float] = None) -> bool:
        threshold = threshold or settings.pii_score_threshold
        detection = self.detect(text)
        return detection.has_pii and detection.score >= threshold


class SensitiveDataFilter:
    
    # Keuwords that might indicate sensitive data
    SENSITIVE_KEYWORDS = [
        "password", "secret", "private", "confidential",
        "internal", "restricted", "classified",
        "credit card", "ssn", "social security",
        "bank account", "routing number",
        "api key", "access token", "api_key", "token"
    ]
    
    def __init__(self, enable_filter: bool = True):
        """Initialize Sensitive Data Filter"""
        self.enable_filter = enable_filter
        logger.info(f"SensitiveDataFilter initialized (enabled={enable_filter})")
    
    def contains_sensitive_keywords(self, text: str) -> Tuple[bool, List[str]]:
        if not self.enable_filter:
            return False, []
        
        text_lower = text.lower()
        found = [kw for kw in self.SENSITIVE_KEYWORDS if kw in text_lower]
        return len(found) > 0, found
    
    def filter_documents(self, documents: List) -> List:
        if not self.enable_filter:
            return documents
        
        filtered = []
        for doc in documents:
            contains_sensitive, keywords = self.contains_sensitive_keywords(
                doc.page_content
            )
            if not contains_sensitive:
                filtered.append(doc)
            else:
                logger.warning(
                    f"Document filtered due to sensitive keywords: {keywords}"
                )
        return filtered
    
    def should_block(self, text: str) -> bool:
        contains_sensitive, _ = self.contains_sensitive_keywords(text)
        return contains_sensitive


class GuardrailsManager:
    
    def __init__(
        self,
        enable_pii: Optional[bool] = None,
        enable_sensitive: Optional[bool] = None
    ):
        """
        Initialize Guardrails Manager
        
        Args:
            enable_pii: Enable PII detection (default: from settings)
            enable_sensitive: Enable sensitive data filter (default: from settings)
        """
        enable_pii = enable_pii if enable_pii is not None else settings.enable_pii_detection
        enable_sensitive = enable_sensitive if enable_sensitive is not None else settings.enable_sensitive_data_filter
        self.pii_detector = PIIDetector(enable_detection=enable_pii)
        self.sensitive_filter = SensitiveDataFilter(enable_filter=enable_sensitive)
        logger.info("GuardrailsManager initialized")
    
    def check_input(self, text: str) -> Dict:
        pii_detection = self.pii_detector.detect(text)
        _, sensitive_keywords = self.sensitive_filter.contains_sensitive_keywords(text)
        
        should_block = (
            self.pii_detector.should_block(text) or
            self.sensitive_filter.should_block(text)
        )
        
        return {
            "should_block": should_block,
            "pii_detected": pii_detection.has_pii,
            "pii_types": pii_detection.detected_types,
            "pii_score": pii_detection.score,
            "sensitive_keywords": sensitive_keywords,
            "anonymized_text": pii_detection.anonymized_text
        }
    
    def filter_context(self, documents: List) -> List:
        return self.sensitive_filter.filter_documents(documents)
    
    def get_safe_response(self, response: str) -> str:
        return self.pii_detector.anonymize(response)


def get_guardrails_manager() -> GuardrailsManager:
    return GuardrailsManager()
