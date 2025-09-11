# 🧪 Тести для Kalkulator

## Запуск тестів

```bash
# Встановлення залежностей
pip install -r requirements-test.txt

# Запуск всіх тестів
python run_tests.py

# Або безпосередньо
pytest tests/ -v --cov=src
```

## Структура тестів

- `test_database.py` - Тести бази даних
- `test_calculator.py` - Тести калькулятора  
- `test_localization.py` - Тести локалізації
- `test_validation.py` - Тести валідації
- `conftest.py` - Конфігурація pytest

## Покриття коду

Ціль: **70%+ покриття коду**

Звіт генерується в `htmlcov/index.html`
