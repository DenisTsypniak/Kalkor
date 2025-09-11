"""
Скрипт для запуску тестів
"""
import subprocess
import sys
import os


def run_tests():
    """Запускає всі тести"""
    print("🧪 Запуск тестів...")
    
    # Перевіряємо чи встановлені залежності
    try:
        import pytest
    except ImportError:
        print("❌ pytest не встановлений. Встановлюємо...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"])
    
    # Запускаємо тести
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term-missing"
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("✅ Всі тести пройшли успішно!")
        print("📊 Звіт про покриття: htmlcov/index.html")
    else:
        print("❌ Деякі тести провалились")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
