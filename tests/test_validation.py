"""
Тести для валідації даних
"""
import pytest
import sys
sys.path.append('src')

from utils.validators import DataValidator


class TestDataValidator:
    """Тести для DataValidator"""
    
    def setup_method(self):
        """Налаштування перед кожним тестом"""
        self.validator = DataValidator()
    
    def test_validate_amount(self):
        """Тест валідації суми"""
        # Валідні суми
        assert self.validator.validate_amount(100) == True
        assert self.validator.validate_amount(100.50) == True
        assert self.validator.validate_amount(0) == True
        assert self.validator.validate_amount(999999.99) == True
        
        # Невалідні суми
        assert self.validator.validate_amount(-100) == False
        assert self.validator.validate_amount("100") == False
        assert self.validator.validate_amount(None) == False
        assert self.validator.validate_amount("") == False
    
    def test_validate_date(self):
        """Тест валідації дати"""
        # Валідні дати
        assert self.validator.validate_date("2024-01-01") == True
        assert self.validator.validate_date("2024-12-31") == True
        assert self.validator.validate_date("2023-02-28") == True
        
        # Невалідні дати
        assert self.validator.validate_date("2024-13-01") == False  # Невалідний місяць
        assert self.validator.validate_date("2024-01-32") == False  # Невалідний день
        assert self.validator.validate_date("2024-02-30") == False  # Невалідний день для лютого
        assert self.validator.validate_date("invalid-date") == False
        assert self.validator.validate_date("") == False
        assert self.validator.validate_date(None) == False
    
    def test_validate_transaction_type(self):
        """Тест валідації типу транзакції"""
        # Валідні типи
        assert self.validator.validate_transaction_type("income") == True
        assert self.validator.validate_transaction_type("expense") == True
        
        # Невалідні типи
        assert self.validator.validate_transaction_type("invalid") == False
        assert self.validator.validate_transaction_type("") == False
        assert self.validator.validate_transaction_type(None) == False
        assert self.validator.validate_transaction_type(123) == False
    
    def test_validate_category(self):
        """Тест валідації категорії"""
        # Валідні категорії
        assert self.validator.validate_category("salary") == True
        assert self.validator.validate_category("food") == True
        assert self.validator.validate_category("transport") == True
        assert self.validator.validate_category("entertainment") == True
        
        # Невалідні категорії
        assert self.validator.validate_category("") == False
        assert self.validator.validate_category(None) == False
        assert self.validator.validate_category("   ") == False
    
    def test_validate_property_name(self):
        """Тест валідації назви нерухомості"""
        # Валідні назви
        assert self.validator.validate_property_name("Квартира в центрі") == True
        assert self.validator.validate_property_name("House #1") == True
        assert self.validator.validate_property_name("Офіс") == True
        
        # Невалідні назви
        assert self.validator.validate_property_name("") == False
        assert self.validator.validate_property_name("   ") == False
        assert self.validator.validate_property_name(None) == False
        assert self.validator.validate_property_name("a" * 256) == False  # Занадто довга
    
    def test_validate_profile_name(self):
        """Тест валідації назви профілю"""
        # Валідні назви
        assert self.validator.validate_profile_name("Мій профіль") == True
        assert self.validator.validate_profile_name("Profile 1") == True
        assert self.validator.validate_profile_name("Тест") == True
        
        # Невалідні назви
        assert self.validator.validate_profile_name("") == False
        assert self.validator.validate_profile_name("   ") == False
        assert self.validator.validate_profile_name(None) == False
        assert self.validator.validate_profile_name("a" * 100) == False  # Занадто довга
    
    def test_validate_notes(self):
        """Тест валідації нотаток"""
        # Валідні нотатки
        assert self.validator.validate_notes("Опис транзакції") == True
        assert self.validator.validate_notes("") == True  # Нотатки можуть бути порожніми
        assert self.validator.validate_notes(None) == True  # Нотатки можуть бути None
        
        # Невалідні нотатки
        assert self.validator.validate_notes("a" * 1001) == False  # Занадто довгі
    
    def test_validate_language_code(self):
        """Тест валідації коду мови"""
        # Валідні коди
        assert self.validator.validate_language_code("uk") == True
        assert self.validator.validate_language_code("en") == True
        assert self.validator.validate_language_code("ru") == True
        
        # Невалідні коди
        assert self.validator.validate_language_code("invalid") == False
        assert self.validator.validate_language_code("") == False
        assert self.validator.validate_language_code(None) == False
        assert self.validator.validate_language_code("UK") == False  # Має бути нижній регістр
    
    def test_validate_email(self):
        """Тест валідації email"""
        # Валідні email
        assert self.validator.validate_email("test@example.com") == True
        assert self.validator.validate_email("user.name@domain.co.uk") == True
        assert self.validator.validate_email("test+tag@example.org") == True
        
        # Невалідні email
        assert self.validator.validate_email("invalid-email") == False
        assert self.validator.validate_email("@example.com") == False
        assert self.validator.validate_email("test@") == False
        assert self.validator.validate_email("") == False
        assert self.validator.validate_email(None) == False
    
    def test_validate_phone(self):
        """Тест валідації телефону"""
        # Валідні телефони
        assert self.validator.validate_phone("+380501234567") == True
        assert self.validator.validate_phone("0501234567") == True
        assert self.validator.validate_phone("+1-555-123-4567") == True
        
        # Невалідні телефони
        assert self.validator.validate_phone("123") == False  # Занадто короткий
        assert self.validator.validate_phone("invalid") == False
        assert self.validator.validate_phone("") == False
        assert self.validator.validate_phone(None) == False
    
    def test_validate_json_structure(self):
        """Тест валідації структури JSON"""
        # Валідний JSON
        valid_json = {"key1": "value1", "key2": "value2"}
        assert self.validator.validate_json_structure(valid_json) == True
        
        # Невалідний JSON (не словник)
        invalid_json = "not a dict"
        assert self.validator.validate_json_structure(invalid_json) == False
        
        # Порожній JSON
        assert self.validator.validate_json_structure({}) == True
        assert self.validator.validate_json_structure(None) == False


if __name__ == '__main__':
    pytest.main([__file__])
