"""
Калькулятор для математичних обчислень
"""
import re
from typing import Union


class Calculator:
    """Клас для математичних обчислень"""
    
    def __init__(self):
        self.operators = {
            '+': lambda x, y: x + y,
            '-': lambda x, y: x - y,
            '*': lambda x, y: x * y,
            '/': lambda x, y: x / y if y != 0 else self._raise_division_by_zero(),
            '^': lambda x, y: x ** y,
            '%': lambda x, y: x % y if y != 0 else self._raise_division_by_zero()
        }
    
    def _raise_division_by_zero(self):
        """Викидає помилку ділення на нуль"""
        raise ValueError("Division by zero")
    
    def calculate(self, expression: str) -> float:
        """Обчислює математичний вираз"""
        if not expression or not expression.strip():
            raise ValueError("Empty expression")
        
        # Очищаємо вираз від пробілів
        expression = expression.replace(' ', '')
        
        # Перевіряємо базову валідність
        if not self._is_valid_expression(expression):
            raise ValueError("Invalid expression")
        
        try:
            # Обчислюємо вираз
            result = self._evaluate_expression(expression)
            return float(result)
        except Exception as e:
            raise ValueError(f"Calculation error: {str(e)}")
    
    def _is_valid_expression(self, expression: str) -> bool:
        """Перевіряє валідність виразу"""
        # Перевіряємо що вираз не порожній
        if not expression:
            return False
        
        # Перевіряємо що вираз містить тільки дозволені символи
        allowed_chars = set('0123456789+-*/.()^%')
        if not all(c in allowed_chars for c in expression):
            return False
        
        # Перевіряємо що немає подвійних операторів
        if re.search(r'[+\-*/^%]{2,}', expression):
            return False
        
        # Перевіряємо що вираз не починається з оператора (крім -)
        if expression[0] in '+*/^%':
            return False
        
        # Перевіряємо що вираз не закінчується оператором
        if expression[-1] in '+-*/^%':
            return False
        
        # Перевіряємо баланс дужок
        if not self._check_parentheses_balance(expression):
            return False
        
        return True
    
    def _check_parentheses_balance(self, expression: str) -> bool:
        """Перевіряє баланс дужок"""
        count = 0
        for char in expression:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0
    
    def _evaluate_expression(self, expression: str) -> float:
        """Обчислює вираз з урахуванням пріоритету операцій"""
        # Обробляємо дужки
        while '(' in expression:
            expression = self._evaluate_parentheses(expression)
        
        # Обчислюємо операції згідно з пріоритетом
        expression = self._evaluate_operations(expression, ['^', '%'])
        expression = self._evaluate_operations(expression, ['*', '/'])
        expression = self._evaluate_operations(expression, ['+', '-'])
        
        return float(expression)
    
    def _evaluate_parentheses(self, expression: str) -> str:
        """Обчислює вирази в дужках"""
        # Знаходимо найглибші дужки
        start = expression.rfind('(')
        if start == -1:
            return expression
        
        # Знаходимо відповідну закриваючу дужку
        end = start + 1
        count = 1
        while end < len(expression) and count > 0:
            if expression[end] == '(':
                count += 1
            elif expression[end] == ')':
                count -= 1
            end += 1
        
        if count != 0:
            raise ValueError("Unbalanced parentheses")
        
        # Обчислюємо вираз в дужках
        inner_expression = expression[start + 1:end - 1]
        result = self._evaluate_expression(inner_expression)
        
        # Замінюємо вираз в дужках на результат
        return expression[:start] + str(result) + expression[end:]
    
    def _evaluate_operations(self, expression: str, operators: list) -> str:
        """Обчислює операції з заданим пріоритетом"""
        while any(op in expression for op in operators):
            # Знаходимо першу операцію з заданим пріоритетом
            for i, char in enumerate(expression):
                if char in operators:
                    # Перевіряємо чи це не унарний мінус на початку
                    if char == '-' and i == 0:
                        continue
                    
                    # Знаходимо лівий операнд
                    left_start = self._find_operand_start(expression, i - 1)
                    left_operand_str = expression[left_start:i]
                    
                    # Якщо лівий операнд порожній, пропускаємо (це може бути унарний мінус)
                    if not left_operand_str:
                        continue
                        
                    left_operand = float(left_operand_str)
                    
                    # Знаходимо правий операнд
                    right_end = self._find_operand_end(expression, i + 1)
                    right_operand = float(expression[i + 1:right_end])
                    
                    # Обчислюємо результат
                    result = self.operators[char](left_operand, right_operand)
                    
                    # Замінюємо вираз на результат
                    expression = expression[:left_start] + str(result) + expression[right_end:]
                    break
        
        return expression
    
    def _find_operand_start(self, expression: str, start: int) -> int:
        """Знаходить початок операнда"""
        # Обробляємо від'ємні числа
        if start >= 0 and expression[start] == '-':
            if start == 0 or expression[start - 1] in '+-*/^%(':
                return start
        
        # Знаходимо початок числа
        while start >= 0 and (expression[start].isdigit() or expression[start] == '.'):
            start -= 1
        
        return start + 1
    
    def _find_operand_end(self, expression: str, start: int) -> int:
        """Знаходить кінець операнда"""
        end = start
        while end < len(expression) and (expression[end].isdigit() or expression[end] == '.'):
            end += 1
        
        return end
    
    def format_result(self, result: float, precision: int = 2) -> str:
        """Форматує результат для відображення"""
        if result == int(result):
            return str(int(result))
        else:
            return f"{result:.{precision}f}".rstrip('0').rstrip('.')
