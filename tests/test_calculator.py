"""
Тести для калькулятора
"""
import pytest
import sys
sys.path.append('src')

from utils.calculator import Calculator


class TestCalculator:
    """Тести для Calculator"""
    
    def setup_method(self):
        """Налаштування перед кожним тестом"""
        self.calc = Calculator()
    
    def test_basic_operations(self):
        """Тест базових математичних операцій"""
        # Додавання
        assert self.calc.calculate("2 + 3") == 5
        assert self.calc.calculate("10 + 5") == 15
        
        # Віднімання
        assert self.calc.calculate("10 - 3") == 7
        assert self.calc.calculate("5 - 2") == 3
        
        # Множення
        assert self.calc.calculate("4 * 3") == 12
        assert self.calc.calculate("6 * 7") == 42
        
        # Ділення
        assert self.calc.calculate("15 / 3") == 5
        assert self.calc.calculate("20 / 4") == 5
    
    def test_decimal_operations(self):
        """Тест операцій з десятковими числами"""
        assert self.calc.calculate("2.5 + 3.7") == 6.2
        assert self.calc.calculate("10.5 - 3.2") == 7.3
        assert self.calc.calculate("4.5 * 2") == 9.0
        assert self.calc.calculate("15.6 / 3") == 5.2
    
    def test_complex_expressions(self):
        """Тест складних виразів"""
        assert self.calc.calculate("2 + 3 * 4") == 14  # 2 + 12 = 14
        assert self.calc.calculate("(2 + 3) * 4") == 20  # 5 * 4 = 20
        assert self.calc.calculate("10 / 2 + 3 * 2") == 11  # 5 + 6 = 11
    
    def test_division_by_zero(self):
        """Тест ділення на нуль"""
        with pytest.raises(ValueError, match="Division by zero"):
            self.calc.calculate("10 / 0")
    
    def test_invalid_expressions(self):
        """Тест невалідних виразів"""
        with pytest.raises(ValueError):
            self.calc.calculate("2 +")
        
        with pytest.raises(ValueError):
            self.calc.calculate("+ 2")
        
        with pytest.raises(ValueError):
            self.calc.calculate("2 + + 3")
    
    def test_empty_expression(self):
        """Тест порожнього виразу"""
        with pytest.raises(ValueError):
            self.calc.calculate("")
        
        with pytest.raises(ValueError):
            self.calc.calculate("   ")
    
    def test_whitespace_handling(self):
        """Тест обробки пробілів"""
        assert self.calc.calculate(" 2 + 3 ") == 5
        assert self.calc.calculate("2+3") == 5
        assert self.calc.calculate("  10   -   5  ") == 5
    
    def test_negative_numbers(self):
        """Тест від'ємних чисел"""
        assert self.calc.calculate("-5 + 3") == -2
        assert self.calc.calculate("5 - (-3)") == 8
        assert self.calc.calculate("-5 * 3") == -15
        assert self.calc.calculate("-15 / 3") == -5
    
    def test_large_numbers(self):
        """Тест великих чисел"""
        assert self.calc.calculate("1000000 + 2000000") == 3000000
        assert self.calc.calculate("999999 * 2") == 1999998
    
    def test_precision(self):
        """Тест точності обчислень"""
        result = self.calc.calculate("1 / 3")
        assert abs(result - 0.3333333333333333) < 1e-10


if __name__ == '__main__':
    pytest.main([__file__])
