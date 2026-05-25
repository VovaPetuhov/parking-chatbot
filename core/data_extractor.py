"""
Data Extractor - Extract reservation data from user input using LLM
"""
import logging
import re
from datetime import datetime
from typing import Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from config.prompts import (
    EXTRACT_CAR_PLATE_PROMPT,
    EXTRACT_DATES_PROMPT,
    EXTRACT_NAME_PROMPT,
    EXTRACT_SURNAME_PROMPT,
    RESERVATION_INTENT_PROMPT,
)
from core.llm import get_chat_model

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extract structured data from user input using LLM"""

    def __init__(self, llm: Optional[BaseChatModel] = None, extraction_llm: Optional[BaseChatModel] = None):
        from config.settings import settings
        self.llm = llm or get_chat_model()
        if extraction_llm:
            self.extraction_llm = extraction_llm
        elif settings.data_extraction_model != settings.openai_model_name:
            logger.info(f"Using specialized extraction model: {settings.data_extraction_model}")
            self.extraction_llm = get_chat_model(model_name=settings.data_extraction_model)
        else:
            self.extraction_llm = self.llm
        self.parser = StrOutputParser()
        logger.info(f"DataExtractor initialized (extraction model: {settings.data_extraction_model})")
    
    def check_reservation_intent(self, user_input: str) -> bool:
        """Check if user wants to make a reservation"""
        logger.info(f"Checking reservation intent: {user_input}")
        prompt = PromptTemplate.from_template(RESERVATION_INTENT_PROMPT)
        chain = prompt | self.extraction_llm | self.parser
        result = chain.invoke({"user_input": user_input})
        result = result.strip().lower()
        has_intent = "yes" in result and "no" not in result
        logger.info(f"Reservation intent: {has_intent} (raw: {result})")
        return has_intent
    
    def extract_name(self, user_input: str) -> Optional[str]:
        logger.info(f"Extracting name from: {user_input}")
        prompt = PromptTemplate.from_template(EXTRACT_NAME_PROMPT)
        chain = prompt | self.extraction_llm | self.parser
        result = chain.invoke({"user_input": user_input})
        result = result.strip()
        if "not_found" in result.lower() or "not found" in result.lower():
            logger.info("Name not found")
            return None
        result = re.sub(r'^(name:|the name is|name is)\s*', '', result, flags=re.IGNORECASE)
        result = result.strip().strip('"\'.,')

        if not result or len(result) < 2 or len(result) > 50:
            logger.info(f"Invalid name format: {result}")
            return None

        name = result.capitalize()
        logger.info(f"Extracted name: {name}")
        return name
    
    def extract_surname(self, user_input: str) -> Optional[str]:
        logger.info(f"Extracting surname from: {user_input}")
        prompt = PromptTemplate.from_template(EXTRACT_SURNAME_PROMPT)
        chain = prompt | self.extraction_llm | self.parser

        result = chain.invoke({"user_input": user_input})
        result = result.strip()

        if "not_found" in result.lower() or "not found" in result.lower():
            logger.info("Surname not found")
            return None

        result = re.sub(r'^(surname:|last name:|the surname is|surname is)\s*', '', result, flags=re.IGNORECASE)
        result = result.strip().strip('"\'.,')

        if not result or len(result) < 2 or len(result) > 50:
            logger.info(f"Invalid surname format: {result}")
            return None

        surname = result.capitalize()
        logger.info(f"Extracted surname: {surname}")
        return surname
    
    def extract_car_plate(self, user_input: str) -> Optional[str]:
        logger.info(f"Extracting car plate from: {user_input}")
        prompt = PromptTemplate.from_template(EXTRACT_CAR_PLATE_PROMPT)
        chain = prompt | self.extraction_llm | self.parser
        result = chain.invoke({"user_input": user_input})
        result = result.strip()

        if "not_found" in result.lower() or "not found" in result.lower():
            logger.info("Car plate not found")
            return None

        result = re.sub(r'^(plate:|car plate:|license plate:|plate number is|the plate is)\s*', '', result, flags=re.IGNORECASE)
        result = result.strip().strip('"\'.,')

        result = result.upper().replace(" ", "").replace("-", "")
        if not result:
            logger.info("Car plate empty after cleanup")
            return None

        if not self._validate_car_plate(result):
            logger.warning(f"Invalid car plate format: {result}")
            return None
        logger.info(f"Extracted car plate: {result}")
        return result
    
    def extract_dates(self, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        logger.info(f"Extracting dates from: {user_input}")

        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = PromptTemplate.from_template(EXTRACT_DATES_PROMPT)
        chain = prompt | self.extraction_llm | self.parser

        result = chain.invoke({
            "user_input": user_input,
            "current_date": current_date
        })
        result = result.strip()

        if "not_found" in result.lower() or "not found" in result.lower():
            logger.info("Dates not found")
            return None, None
        if "|" not in result:
            logger.info(f"Pipe separator not found in: {result}")
            return None, None

        # Parse dates
        try:
            parts = result.split("|")
            if len(parts) < 2:
                logger.warning(f"Not enough date parts: {parts}")
                return None, None
            start_date = parts[0].strip().strip('"\'.,')
            end_date = parts[1].strip().strip('"\'.,')
            date_pattern = r'(\d{4}-\d{2}-\d{2})'
            start_match = re.search(date_pattern, start_date)
            end_match = re.search(date_pattern, end_date)
            if start_match:
                start_date = start_match.group(1)
            if end_match:
                end_date = end_match.group(1)
            if not self._validate_date(start_date) or not self._validate_date(end_date):
                logger.warning(f"Invalid date format: {start_date}, {end_date}")
                return None, None
            logger.info(f"Extracted dates: {start_date} to {end_date}")
            return start_date, end_date
        except Exception as e:
            logger.error(f"Error parsing dates: {e}")
            return None, None
    
    def _validate_car_plate(self, plate: str) -> bool:
        if not plate or len(plate) < 3 or len(plate) > 10:
            return False
        has_letter = any(c.isalpha() for c in plate)
        has_digit = any(c.isdigit() for c in plate)
        return has_letter and has_digit
    
    def _validate_date(self, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False


_data_extractor: Optional[DataExtractor] = None


def get_data_extractor() -> DataExtractor:
    """Get or create DataExtractor instance"""
    global _data_extractor
    if _data_extractor is None:
        _data_extractor = DataExtractor()
    return _data_extractor
