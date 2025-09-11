"""
Покращена система бази даних
"""
import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .logger import get_logger
from .error_handler import handle_errors, DatabaseError
from .validators import DataValidator


class DatabaseManager:
    """Покращений менеджер бази даних"""
    
    def __init__(self, db_path: str = "tracker.db"):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        self.validator = DataValidator()
        self._init_database()
    
    def _init_database(self) -> None:
        """Ініціалізує базу даних"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            self.logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    def _create_tables(self) -> None:
        """Створює таблиці"""
        tables = [
            """CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                notes TEXT,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles (id)
            )""",
            """CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles (id)
            )"""
        ]
        
        cursor = self.conn.cursor()
        for table_sql in tables:
            cursor.execute(table_sql)
        self.conn.commit()
    
    @handle_errors("add_transaction")
    def add_transaction(self, profile_id: int, amount: float, type: str, 
                       category: str, notes: str = None, date: str = None) -> int:
        """Додає транзакцію"""
        # Валідація
        if not self.validator.validate_amount(amount):
            raise ValueError("Invalid amount")
        if not self.validator.validate_transaction_type(type):
            raise ValueError("Invalid transaction type")
        if not self.validator.validate_category(category):
            raise ValueError("Invalid category")
        if date and not self.validator.validate_date(date):
            raise ValueError("Invalid date")
        
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (profile_id, amount, type, category, notes, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (profile_id, amount, type, category, notes, date))
        
        self.conn.commit()
        transaction_id = cursor.lastrowid
        
        self.logger.log_database_operation("add_transaction")
        return transaction_id
    
    @handle_errors("get_transactions")
    def get_transactions(self, profile_id: int) -> List[Dict[str, Any]]:
        """Отримує транзакції"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE profile_id = ? 
            ORDER BY date DESC
        """, (profile_id,))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        self.logger.log_database_operation("get_transactions")
        return transactions
    
    @handle_errors("add_property")
    def add_property(self, profile_id: int, name: str, price: float, 
                    purchase_date: str, notes: str = None) -> int:
        """Додає нерухомість"""
        # Валідація
        if not self.validator.validate_property_name(name):
            raise ValueError("Invalid property name")
        if not self.validator.validate_amount(price):
            raise ValueError("Invalid price")
        if not self.validator.validate_date(purchase_date):
            raise ValueError("Invalid purchase date")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO properties (profile_id, name, price, purchase_date, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (profile_id, name, price, purchase_date, notes))
        
        self.conn.commit()
        property_id = cursor.lastrowid
        
        self.logger.log_database_operation("add_property")
        return property_id
    
    @handle_errors("get_properties")
    def get_properties(self, profile_id: int) -> List[Dict[str, Any]]:
        """Отримує нерухомість"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM properties 
            WHERE profile_id = ? 
            ORDER BY purchase_date DESC
        """, (profile_id,))
        
        properties = [dict(row) for row in cursor.fetchall()]
        self.logger.log_database_operation("get_properties")
        return properties
    
    @handle_errors("get_transactions_by_period")
    def get_transactions_by_period(self, profile_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Отримує транзакції за період"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE profile_id = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
        """, (profile_id, start_date, end_date))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        self.logger.log_database_operation("get_transactions_by_period")
        return transactions
    
    @handle_errors("calculate_total_income")
    def calculate_total_income(self, profile_id: int, start_date: str, end_date: str) -> float:
        """Розраховує загальний дохід за період"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT SUM(amount) as total FROM transactions 
            WHERE profile_id = ? AND type = 'дохід' AND date BETWEEN ? AND ?
        """, (profile_id, start_date, end_date))
        
        result = cursor.fetchone()
        total = result['total'] if result and result['total'] else 0.0
        self.logger.log_database_operation("calculate_total_income")
        return total
    
    @handle_errors("calculate_total_expenses")
    def calculate_total_expenses(self, profile_id: int, start_date: str, end_date: str) -> float:
        """Розраховує загальні витрати за період"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT SUM(amount) as total FROM transactions 
            WHERE profile_id = ? AND type = 'витрата' AND date BETWEEN ? AND ?
        """, (profile_id, start_date, end_date))
        
        result = cursor.fetchone()
        total = result['total'] if result and result['total'] else 0.0
        self.logger.log_database_operation("calculate_total_expenses")
        return total

    def close(self) -> None:
        """Закриває з'єднання з БД"""
        if hasattr(self, 'conn'):
            self.conn.close()
            self.logger.info("Database connection closed")
