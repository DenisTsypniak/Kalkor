"""
Покращена система логування
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional
import json


class StructuredFormatter(logging.Formatter):
    """Форматер для структурованого логування"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Додаємо додаткові поля якщо вони є
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        if hasattr(record, 'duration'):
            log_entry['duration'] = record.duration
        if hasattr(record, 'error_code'):
            log_entry['error_code'] = record.error_code
        
        # Додаємо exception info якщо є
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class Logger:
    """Покращений логер"""
    
    def __init__(self, name: str = None, log_dir: str = "logs"):
        self.name = name or __name__
        self.log_dir = log_dir
        self.logger = logging.getLogger(self.name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Налаштовує логер"""
        # Очищаємо існуючі handlers
        self.logger.handlers.clear()
        
        # Встановлюємо рівень логування
        self.logger.setLevel(logging.DEBUG)
        
        # Створюємо директорію для логів
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Налаштовуємо різні handlers
        self._setup_console_handler()
        self._setup_file_handler()
        self._setup_error_handler()
        self._setup_rotating_handler()
    
    def _setup_console_handler(self):
        """Налаштовує консольний handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Простий форматер для консолі
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self):
        """Налаштовує файловий handler"""
        file_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'app.log'),
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Структурований форматер для файлу
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def _setup_error_handler(self):
        """Налаштовує handler для помилок"""
        error_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'errors.log'),
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        error_formatter = StructuredFormatter()
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
    
    def _setup_rotating_handler(self):
        """Налаштовує ротаційний handler"""
        rotating_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self.log_dir, 'app_rotating.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        rotating_handler.setLevel(logging.INFO)
        
        rotating_formatter = StructuredFormatter()
        rotating_handler.setFormatter(rotating_formatter)
        self.logger.addHandler(rotating_handler)
    
    def debug(self, message: str, **kwargs):
        """Логує debug повідомлення"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Логує info повідомлення"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Логує warning повідомлення"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Логує error повідомлення"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Логує critical повідомлення"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Внутрішній метод логування"""
        # Створюємо record з додатковими полями
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None
        )
        
        # Додаємо додаткові поля
        for key, value in kwargs.items():
            setattr(record, key, value)
        
        # Логуємо
        self.logger.handle(record)
    
    def log_user_action(self, action: str, user_id: str = None, **kwargs):
        """Логує дії користувача"""
        self.info(f"User action: {action}", user_id=user_id, operation=action, **kwargs)
    
    def log_database_operation(self, operation: str, duration: float = None, **kwargs):
        """Логує операції з базою даних"""
        self.info(f"Database operation: {operation}", operation=operation, duration=duration, **kwargs)
    
    def log_error(self, error: Exception, context: str = None, **kwargs):
        """Логує помилки"""
        self.error(f"Error in {context or 'unknown context'}: {str(error)}", 
                  error_code=type(error).__name__, **kwargs)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Логує метрики продуктивності"""
        self.info(f"Performance: {operation} took {duration:.3f}s", 
                  operation=operation, duration=duration, **kwargs)


# Глобальний логер
app_logger = Logger("KalkulatorApp")


def get_logger(name: str = None) -> Logger:
    """Отримує логер"""
    if name:
        return Logger(name)
    return app_logger


def log_function_call(func_name: str, **kwargs):
    """Логує виклик функції"""
    app_logger.debug(f"Function call: {func_name}", operation=func_name, **kwargs)


def log_function_result(func_name: str, success: bool, duration: float = None, **kwargs):
    """Логує результат функції"""
    status = "success" if success else "failure"
    app_logger.info(f"Function {func_name}: {status}", 
                   operation=func_name, duration=duration, **kwargs)


def log_exception(func_name: str, exception: Exception, **kwargs):
    """Логує виняток"""
    app_logger.error(f"Exception in {func_name}: {str(exception)}", 
                    operation=func_name, error_code=type(exception).__name__, **kwargs)
