"""
Конфігурація pytest
"""
import pytest
import tempfile
import os
import sys
sys.path.append('src')

from utils.database import DatabaseManager
from utils.localization import LocalizationManager
from utils.validators import DataValidator


@pytest.fixture
def temp_db():
    """Фікстура для тимчасової бази даних"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    db_manager = DatabaseManager(temp_file.name)
    yield db_manager
    
    # Очищення після тесту
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


@pytest.fixture
def loc_manager():
    """Фікстура для менеджера локалізації"""
    return LocalizationManager()


@pytest.fixture
def validator():
    """Фікстура для валідатора даних"""
    return DataValidator()


@pytest.fixture
def sample_transaction_data():
    """Фікстура з тестовими даними транзакції"""
    return {
        'profile_id': 1,
        'amount': 1000.50,
        'type': 'income',
        'category': 'salary',
        'notes': 'Test transaction',
        'date': '2024-01-01'
    }


@pytest.fixture
def sample_property_data():
    """Фікстура з тестовими даними нерухомості"""
    return {
        'profile_id': 1,
        'name': 'Test Property',
        'price': 100000.0,
        'purchase_date': '2024-01-01',
        'notes': 'Test property'
    }


@pytest.fixture
def sample_profile_data():
    """Фікстура з тестовими даними профілю"""
    return {
        'name': 'Test Profile',
        'email': 'test@example.com',
        'phone': '+380501234567'
    }


# Налаштування pytest
def pytest_configure(config):
    """Конфігурація pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Модифікація зібраних тестів"""
    for item in items:
        # Автоматично додаємо маркер unit для всіх тестів
        if not any(marker.name in ['slow', 'integration'] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
