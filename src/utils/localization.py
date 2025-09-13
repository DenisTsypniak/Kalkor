"""
Покращена система локалізації
"""
import json
import os
import sys
from typing import Dict, Any, Optional
import logging

from .logger import get_logger
from .error_handler import handle_errors, LocalizationError


class LocalizationManager:
    """Покращений менеджер локалізації"""
    
    def __init__(self, locale_dir: str = "locale"):
        # Використовуємо resource_path для правильної роботи з PyInstaller
        self.locale_dir = self._get_resource_path(locale_dir)
        self.logger = get_logger(__name__)
        self._translations: Dict[str, str] = {}
        self.current_language = "uk"
        self._fallback_language = "en"
        
        # Інформація про мови
        self.languages = {
            "uk": {"lang_name": "Українська"},
            "en": {"lang_name": "English"},
            "ru": {"lang_name": "Русский"}
        }
    
    def _get_resource_path(self, relative_path: str) -> str:
        """
        Отримує абсолютний шлях до ресурсу, працює як для розробки, так і для PyInstaller.
        """
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller створює тимчасову папку і зберігає шлях в _MEIPASS
            return os.path.join(sys._MEIPASS, relative_path)
        
        # Для розробки - відносно поточної директорії
        return os.path.abspath(relative_path)
    
    @handle_errors("load_language")
    def load_language(self, language_code: str) -> None:
        """Завантажує мову"""
        if not language_code:
            raise ValueError("Language code cannot be empty")
        
        file_path = os.path.join(self.locale_dir, f"{language_code}.json")
        self.logger.info(f"Looking for language file: {file_path}")
        
        if not os.path.exists(file_path):
            self.logger.warning(f"Language file not found: {file_path}")
            if language_code != self._fallback_language:
                self.logger.info(f"Trying fallback language: {self._fallback_language}")
                self.load_language(self._fallback_language)
                return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self._translations = json.load(f)
            
            self.current_language = language_code
            self.logger.info(f"Language loaded: {language_code}")
            
        except json.JSONDecodeError as e:
            raise LocalizationError(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            raise LocalizationError(f"Failed to load language {language_code}: {e}")
    
    def get(self, key: str, default: Optional[str] = None) -> str:
        """Отримує переклад"""
        if not key:
            return ""
        
        translation = self._translations.get(key, default or key)
        
        # Логуємо відсутні переклади
        if translation == key and key not in self._translations:
            self.logger.warning(f"Missing translation: {key} for language {self.current_language}")
        
        return translation
    
    def get_all_translations(self) -> Dict[str, str]:
        """Повертає всі переклади"""
        return self._translations.copy()
    
    def validate_translations(self) -> Dict[str, Any]:
        """Валідує переклади"""
        issues = {
            'missing_keys': [],
            'empty_values': [],
            'duplicate_keys': []
        }
        
        # Перевіряємо на порожні значення
        for key, value in self._translations.items():
            if not value or not value.strip():
                issues['empty_values'].append(key)
        
        # Перевіряємо на дублікати ключів
        keys = list(self._translations.keys())
        if len(keys) != len(set(keys)):
            issues['duplicate_keys'] = list(set(keys) - set(set(keys)))
        
        return issues