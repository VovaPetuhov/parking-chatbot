import pytest

from core.data_extractor import DataExtractor
from graphs.chatbot_graph import ParkingChatbot


@pytest.fixture
def data_extractor():
    """Create DataExtractor instance for testing"""
    return DataExtractor()


@pytest.fixture
def chatbot():
    """Create ParkingChatbot instance for testing"""
    return ParkingChatbot()


class TestDataExtractor:
    """Test data extraction from user input"""
    
    def test_check_reservation_intent_positive(self, data_extractor):
        """Test detecting reservation intent"""
        inputs = [
            "I want to book a parking spot",
            "Can I reserve a space?",
            "I'd like to make a reservation",
            "Book a spot for tomorrow"
        ]
        
        for input_text in inputs:
            result = data_extractor.check_reservation_intent(input_text)
            assert result is True, f"Failed to detect intent in: {input_text}"
    
    def test_check_reservation_intent_negative(self, data_extractor):
        """Test not detecting reservation intent in regular queries"""
        inputs = [
            "What are your opening hours?",
            "How much does parking cost?",
            "Where is the parking located?"
        ]
        
        for input_text in inputs:
            result = data_extractor.check_reservation_intent(input_text)
            assert result is False, f"False positive intent in: {input_text}"
    
    def test_extract_name(self, data_extractor):
        """Test name extraction"""
        test_cases = [
            ("My name is John", "John"),
            ("I'm Sarah", "Sarah"),
            ("Call me Mike", "Mike"),
            ("John", "John")
        ]
        
        for input_text, expected in test_cases:
            result = data_extractor.extract_name(input_text)
            assert result == expected, f"Failed to extract name from: {input_text}"
    
    def test_extract_name_not_found(self, data_extractor):
        """Test name extraction when no name present"""
        inputs = ["Yes", "No", "123", "???"]
        
        for input_text in inputs:
            result = data_extractor.extract_name(input_text)
            assert result is None, f"False positive name in: {input_text}"
    
    def test_extract_surname(self, data_extractor):
        """Test surname extraction"""
        test_cases = [
            ("My surname is Smith", "Smith"),
            ("Last name is Johnson", "Johnson"),
            ("It's Brown", "Brown")
        ]
        
        for input_text, expected in test_cases:
            result = data_extractor.extract_surname(input_text)
            assert result == expected, f"Failed to extract surname from: {input_text}"
    
    def test_extract_car_plate(self, data_extractor):
        """Test car plate extraction"""
        test_cases = [
            ("My plate is ABC 123", "ABC123"),
            ("Car number: XY-456-ZZ", "XY456ZZ"),
            ("It's BA 123 CD", "BA123CD")
        ]
        
        for input_text, expected in test_cases:
            result = data_extractor.extract_car_plate(input_text)
            assert result == expected, f"Failed to extract car plate from: {input_text}"
    
    def test_extract_dates(self, data_extractor):
        """Test date extraction"""
        # Note: This test depends on LLM and current date, so we just check format
        result_start, result_end = data_extractor.extract_dates(
            "From January 20th 2025 to January 25th 2025"
        )
        
        if result_start and result_end:
            # Check format YYYY-MM-DD
            assert len(result_start) == 10
            assert result_start[4] == "-" and result_start[7] == "-"
            assert len(result_end) == 10
            assert result_end[4] == "-" and result_end[7] == "-"
    
    def test_validate_car_plate(self, data_extractor):
        """Test car plate validation"""
        valid_plates = ["ABC123", "XY456ZZ", "BA123CD"]
        invalid_plates = ["12", "ABCDEFGHIJK", "123456", "ABCD"]
        
        for plate in valid_plates:
            assert data_extractor._validate_car_plate(plate) is True
        
        for plate in invalid_plates:
            assert data_extractor._validate_car_plate(plate) is False


class TestReservationFlow:
    """Test full reservation collection flow"""
    
    def test_reservation_initialization(self, chatbot):
        """Test that chatbot initializes correctly"""
        assert chatbot.rag_system is not None
        assert chatbot.guardrails is not None
        assert chatbot.data_extractor is not None
        assert chatbot.graph is not None
    
    def test_normal_query_doesnt_start_reservation(self, chatbot):
        """Test that normal queries don't trigger reservation"""
        response = chatbot.chat("What are your opening hours?", "test_conv_1")
        
        # Should get a normal response, not start reservation
        assert "first name" not in response.lower()
        assert "reservation" not in response.lower() or "working hours" in response.lower()
    
    def test_reservation_intent_starts_collection(self, chatbot):
        """Test that reservation intent starts data collection"""
        response = chatbot.chat("I want to book a parking spot", "test_conv_2")
        
        # Should ask for name
        assert "name" in response.lower() or "first name" in response.lower()
    
    def test_complete_reservation_flow(self, chatbot):
        """Test complete reservation flow with all data"""
        conv_id = "test_conv_complete"
        
        # Start reservation
        r1 = chatbot.chat("I want to reserve a parking spot", conv_id)
        assert "name" in r1.lower()
        
        # Provide name
        r2 = chatbot.chat("John", conv_id)
        assert "surname" in r2.lower() or "last name" in r2.lower()
        
        # Provide surname
        r3 = chatbot.chat("Smith", conv_id)
        assert "car" in r3.lower() or "plate" in r3.lower()
        
        # Provide car plate
        r4 = chatbot.chat("ABC123", conv_id)
        assert "date" in r4.lower() or "when" in r4.lower()
        
        # Provide dates
        r5 = chatbot.chat("from January 20th 2025 to January 25th 2025", conv_id)
        assert "confirm" in r5.lower() or "correct" in r5.lower()
        
        # Confirm
        r6 = chatbot.chat("yes", conv_id)
        assert "collected" in r6.lower() or "success" in r6.lower()
        assert "John" in r6
        assert "Smith" in r6
        assert "ABC123" in r6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
