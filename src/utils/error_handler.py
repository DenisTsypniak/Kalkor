"""
Централізована система обробки помилок
"""
import logging
import traceback
from typing import Any, Callable, Optional
from functools import wraps
import sys
from enum import Enum


class ErrorCategory(Enum):
    """Категорії помилок"""
    DATABASE = "database"
    UI = "ui"
    VALIDATION = "validation"
    NETWORK = "network"
    FILE = "file"
    SECURITY = "security"
    GENERAL = "general"


class ErrorSeverity(Enum):
    """Рівні серйозності помилок"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AppError(Exception):
    """Базовий клас для помилок додатку"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class DatabaseError(AppError):
    """Помилки бази даних"""
    pass


class ValidationError(AppError):
    """Помилки валідації"""
    pass


class LocalizationError(AppError):
    """Помилки локалізації"""
    pass


class UpdateError(AppError):
    """Помилки оновлення"""
    pass


class ErrorHandler:
    """Централізований обробник помилок"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_callbacks = []
    
    def register_callback(self, callback: Callable[[AppError], None]):
        """Реєструє callback для обробки помилок"""
        self.error_callbacks.append(callback)
    
    def handle_error(self, error: Exception, context: str = None) -> None:
        """Обробляє помилку"""
        # Логуємо помилку
        self.logger.error(f"Error in {context or 'unknown context'}: {str(error)}")
        self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Конвертуємо в AppError якщо потрібно
        if not isinstance(error, AppError):
            error = AppError(str(error), details={'original_error': type(error).__name__})
        
        # Викликаємо всі зареєстровані callbacks
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as callback_error:
                self.logger.error(f"Error in error callback: {str(callback_error)}")
    
    def handle_database_error(self, error: Exception, operation: str = None) -> None:
        """Обробляє помилки бази даних"""
        db_error = DatabaseError(
            f"Database error during {operation or 'operation'}: {str(error)}",
            error_code="DB_ERROR",
            details={'operation': operation, 'original_error': str(error)}
        )
        self.handle_error(db_error, f"Database operation: {operation}")
    
    def handle_validation_error(self, error: Exception, field: str = None) -> None:
        """Обробляє помилки валідації"""
        validation_error = ValidationError(
            f"Validation error for field {field or 'unknown'}: {str(error)}",
            error_code="VALIDATION_ERROR",
            details={'field': field, 'original_error': str(error)}
        )
        self.handle_error(validation_error, f"Validation: {field}")
    
    def handle_localization_error(self, error: Exception, language: str = None) -> None:
        """Обробляє помилки локалізації"""
        loc_error = LocalizationError(
            f"Localization error for language {language or 'unknown'}: {str(error)}",
            error_code="LOCALIZATION_ERROR",
            details={'language': language, 'original_error': str(error)}
        )
        self.handle_error(loc_error, f"Localization: {language}")
    
    def handle_update_error(self, error: Exception, step: str = None) -> None:
        """Обробляє помилки оновлення"""
        update_error = UpdateError(
            f"Update error during {step or 'unknown step'}: {str(error)}",
            error_code="UPDATE_ERROR",
            details={'step': step, 'original_error': str(error)}
        )
        self.handle_error(update_error, f"Update: {step}")


# Глобальний екземпляр обробника помилок
error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Повертає глобальний обробник помилок"""
    return error_handler


def handle_errors(category: ErrorCategory = None, severity: ErrorSeverity = None, context: str = None):
    """Декоратор для обробки помилок"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, context or func.__name__)
                raise
        return wrapper
    return decorator


def handle_errors_async(context: str = None):
    """Декоратор для обробки помилок в async функціях"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, context or func.__name__)
                raise
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """Безпечно виконує функцію і повертає результат або помилку"""
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_handler.handle_error(e, func.__name__)
        return False, e


async def safe_execute_async(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """Безпечно виконує async функцію і повертає результат або помилку"""
    try:
        result = await func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_handler.handle_error(e, func.__name__)
        return False, e


class ErrorContext:
    """Контекстний менеджер для обробки помилок"""
    
    def __init__(self, context: str, error_handler: ErrorHandler = None):
        self.context = context
        self.error_handler = error_handler or error_handler
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_handler.handle_error(exc_val, self.context)
        return False  # Не пригнічуємо помилку


def create_fallback_value(value_type: type, default_value: Any = None) -> Any:
    """Створює fallback значення для різних типів"""
    if value_type == str:
        return default_value or ""
    elif value_type == int:
        return default_value or 0
    elif value_type == float:
        return default_value or 0.0
    elif value_type == bool:
        return default_value or False
    elif value_type == list:
        return default_value or []
    elif value_type == dict:
        return default_value or {}
    else:
        return default_value


def get_error_message(error: Exception, user_friendly: bool = True) -> str:
    """Отримує повідомлення про помилку"""
    if isinstance(error, AppError):
        if user_friendly:
            return error.message
        else:
            return f"{error.error_code}: {error.message}"
    else:
        if user_friendly:
            return "An unexpected error occurred. Please try again."
        else:
            return f"{type(error).__name__}: {str(error)}"