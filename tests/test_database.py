"""
Тести для роботи з базою даних
"""
import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch
import sys
sys.path.append('src')

from utils.database import DatabaseManager


class TestDatabaseManager:
    """Тести для DatabaseManager"""
    
    def setup_method(self):
        """Налаштування перед кожним тестом"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)
    
    def teardown_method(self):
        """Очищення після кожного тесту"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            try:
                os.unlink(self.temp_db.name)
            except PermissionError:
                # Файл може бути заблокований, спробуємо пізніше
                pass
    
    def test_database_initialization(self):
        """Тест ініціалізації бази даних"""
        assert os.path.exists(self.temp_db.name)
        assert self.db_manager.db_path == self.temp_db.name
    
    def test_create_tables(self):
        """Тест створення таблиць"""
        # Перевіряємо що таблиці створені
        cursor = self.db_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['profiles', 'transactions', 'properties']
        for table in expected_tables:
            assert table in tables
    
    def test_add_transaction(self):
        """Тест додавання транзакції"""
        transaction_data = {
            'profile_id': 1,
            'amount': 100.50,
            'type': 'income',
            'category': 'salary',
            'notes': 'Test transaction',
            'date': '2024-01-01'
        }
        
        result = self.db_manager.add_transaction(**transaction_data)
        assert result is not None
        
        # Перевіряємо що транзакція додана
        transactions = self.db_manager.get_transactions(1)
        assert len(transactions) == 1
        assert transactions[0]['amount'] == 100.50
        assert transactions[0]['type'] == 'income'
    
    def test_add_property(self):
        """Тест додавання нерухомості"""
        property_data = {
            'profile_id': 1,
            'name': 'Test Property',
            'price': 100000.0,
            'purchase_date': '2024-01-01',
            'notes': 'Test property'
        }
        
        result = self.db_manager.add_property(**property_data)
        assert result is not None
        
        # Перевіряємо що нерухомість додана
        properties = self.db_manager.get_properties(1)
        assert len(properties) == 1
        assert properties[0]['name'] == 'Test Property'
        assert properties[0]['price'] == 100000.0
    
    def test_get_transactions_by_period(self):
        """Тест отримання транзакцій за період"""
        # Додаємо тестові транзакції
        self.db_manager.add_transaction(1, 100, 'income', 'salary', 'Jan', '2024-01-01')
        self.db_manager.add_transaction(1, 200, 'income', 'bonus', 'Feb', '2024-02-01')
        self.db_manager.add_transaction(1, 50, 'expense', 'food', 'Mar', '2024-03-01')
        
        # Тестуємо фільтрацію за періодом
        jan_transactions = self.db_manager.get_transactions_by_period(1, '2024-01-01', '2024-01-31')
        assert len(jan_transactions) == 1
        assert jan_transactions[0]['notes'] == 'Jan'
        
        all_transactions = self.db_manager.get_transactions_by_period(1, '2024-01-01', '2024-12-31')
        assert len(all_transactions) == 3
    
    def test_calculate_total_income(self):
        """Тест розрахунку загального доходу"""
        # Додаємо тестові транзакції
        self.db_manager.add_transaction(1, 1000, 'income', 'salary', 'Salary', '2024-01-01')
        self.db_manager.add_transaction(1, 500, 'income', 'bonus', 'Bonus', '2024-01-15')
        self.db_manager.add_transaction(1, 200, 'expense', 'food', 'Food', '2024-01-20')
        
        total_income = self.db_manager.calculate_total_income(1, '2024-01-01', '2024-01-31')
        assert total_income == 1500.0
    
    def test_calculate_total_expenses(self):
        """Тест розрахунку загальних витрат"""
        # Додаємо тестові транзакції
        self.db_manager.add_transaction(1, 1000, 'income', 'salary', 'Salary', '2024-01-01')
        self.db_manager.add_transaction(1, 300, 'expense', 'food', 'Food', '2024-01-15')
        self.db_manager.add_transaction(1, 200, 'expense', 'transport', 'Transport', '2024-01-20')
        
        total_expenses = self.db_manager.calculate_total_expenses(1, '2024-01-01', '2024-01-31')
        assert total_expenses == 500.0
    
    def test_database_connection_error(self):
        """Тест обробки помилок з'єднання з БД"""
        # Створюємо невалідний шлях до БД
        invalid_db = DatabaseManager('/invalid/path/database.db')
        
        # Перевіряємо що помилка обробляється
        with pytest.raises(Exception):
            invalid_db.get_transactions(1)
    
    def test_transaction_validation(self):
        """Тест валідації даних транзакції"""
        # Тестуємо невалідні дані
        with pytest.raises(ValueError):
            self.db_manager.add_transaction(1, -100, 'income', 'salary', 'Invalid', '2024-01-01')
        
        with pytest.raises(ValueError):
            self.db_manager.add_transaction(1, 100, 'invalid_type', 'salary', 'Invalid', '2024-01-01')
    
    def test_property_validation(self):
        """Тест валідації даних нерухомості"""
        # Тестуємо невалідні дані
        with pytest.raises(ValueError):
            self.db_manager.add_property(1, '', 100000, '2024-01-01', 'Invalid')
        
        with pytest.raises(ValueError):
            self.db_manager.add_property(1, 'Test', -100000, '2024-01-01', 'Invalid')


if __name__ == '__main__':
    pytest.main([__file__])
