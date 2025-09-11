"""
Валідатори для даних
"""
import re
from datetime import datetime
from typing import Any, Union


class DataValidator:
    """Клас для валідації даних"""
    
    def __init__(self):
        self.valid_transaction_types = ['income', 'expense']
        self.valid_categories = [
            'salary', 'bonus', 'freelance', 'investment', 'other_income',
            'food', 'transport', 'entertainment', 'shopping', 'bills', 'health', 'other_expense'
        ]
        self.valid_languages = ['uk', 'en', 'ru']
    
    def validate_amount(self, amount: Any) -> bool:
        """Валідація суми"""
        if not isinstance(amount, (int, float)):
            return False
        return amount >= 0
    
    def validate_date(self, date_str: str) -> bool:
        """Валідація дати"""
        if not isinstance(date_str, str) or not date_str.strip():
            return False
        
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def validate_transaction_type(self, transaction_type: str) -> bool:
        """Валідація типу транзакції"""
        if not isinstance(transaction_type, str):
            return False
        return transaction_type in self.valid_transaction_types
    
    def validate_category(self, category: str) -> bool:
        """Валідація категорії"""
        if not isinstance(category, str) or not category.strip():
            return False
        return category in self.valid_categories
    
    def validate_property_name(self, name: str) -> bool:
        """Валідація назви нерухомості"""
        if not isinstance(name, str) or not name.strip():
            return False
        return len(name.strip()) <= 255
    
    def validate_profile_name(self, name: str) -> bool:
        """Валідація назви профілю"""
        if not isinstance(name, str) or not name.strip():
            return False
        return len(name.strip()) < 100  # Менше 100 символів
    
    def validate_notes(self, notes: str) -> bool:
        """Валідація нотаток"""
        if notes is None:
            return True
        if not isinstance(notes, str):
            return False
        return len(notes) <= 1000
    
    def validate_language_code(self, lang_code: str) -> bool:
        """Валідація коду мови"""
        if not isinstance(lang_code, str):
            return False
        return lang_code in self.valid_languages
    
    def validate_email(self, email: str) -> bool:
        """Валідація email"""
        if not isinstance(email, str) or not email.strip():
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))
    
    def validate_phone(self, phone: str) -> bool:
        """Валідація телефону"""
        if not isinstance(phone, str) or not phone.strip():
            return False
        
        # Видаляємо всі символи крім цифр та +
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Перевіряємо що номер має від 10 до 15 цифр
        digits = re.sub(r'[^\d]', '', clean_phone)
        return 10 <= len(digits) <= 15
    
    def validate_json_structure(self, data: dict) -> bool:
        """Валідація структури JSON"""
        if not isinstance(data, dict):
            return False
        
        # Перевіряємо на дублікати ключів
        keys = list(data.keys())
        return len(keys) == len(set(keys))
    
    def validate_transaction_data(self, data: dict) -> tuple[bool, str]:
        """Валідація всіх даних транзакції"""
        required_fields = ['amount', 'type', 'category', 'date']
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        if not self.validate_amount(data['amount']):
            return False, "Invalid amount"
        
        if not self.validate_transaction_type(data['type']):
            return False, "Invalid transaction type"
        
        if not self.validate_category(data['category']):
            return False, "Invalid category"
        
        if not self.validate_date(data['date']):
            return False, "Invalid date"
        
        if 'notes' in data and not self.validate_notes(data['notes']):
            return False, "Invalid notes"
        
        return True, "Valid"
    
    def validate_property_data(self, data: dict) -> tuple[bool, str]:
        """Валідація всіх даних нерухомості"""
        required_fields = ['name', 'price', 'purchase_date']
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        if not self.validate_property_name(data['name']):
            return False, "Invalid property name"
        
        if not self.validate_amount(data['price']):
            return False, "Invalid price"
        
        if not self.validate_date(data['purchase_date']):
            return False, "Invalid purchase date"
        
        if 'notes' in data and not self.validate_notes(data['notes']):
            return False, "Invalid notes"
        
        return True, "Valid"
    
    def validate_profile_data(self, data: dict) -> tuple[bool, str]:
        """Валідація всіх даних профілю"""
        required_fields = ['name']
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        if not self.validate_profile_name(data['name']):
            return False, "Invalid profile name"
        
        if 'email' in data and data['email'] and not self.validate_email(data['email']):
            return False, "Invalid email"
        
        if 'phone' in data and data['phone'] and not self.validate_phone(data['phone']):
            return False, "Invalid phone"
        
        return True, "Valid"
