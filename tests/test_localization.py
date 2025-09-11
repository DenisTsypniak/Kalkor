"""
Тести для локалізації
"""
import pytest
import json
import os
import sys
sys.path.append('src')

from utils.localization import LocalizationManager


class TestLocalizationManager:
    """Тести для LocalizationManager"""
    
    def setup_method(self):
        """Налаштування перед кожним тестом"""
        self.loc_manager = LocalizationManager()
    
    def test_load_ukrainian(self):
        """Тест завантаження української локалізації"""
        self.loc_manager.load_language('uk')
        assert self.loc_manager.current_language == 'uk'
        assert self.loc_manager.get('app_title') is not None
    
    def test_load_english(self):
        """Тест завантаження англійської локалізації"""
        self.loc_manager.load_language('en')
        assert self.loc_manager.current_language == 'en'
        assert self.loc_manager.get('app_title') is not None
    
    def test_load_russian(self):
        """Тест завантаження російської локалізації"""
        self.loc_manager.load_language('ru')
        assert self.loc_manager.current_language == 'ru'
        assert self.loc_manager.get('app_title') is not None
    
    def test_get_translation(self):
        """Тест отримання перекладу"""
        self.loc_manager.load_language('uk')
        translation = self.loc_manager.get('app_title')
        assert isinstance(translation, str)
        assert len(translation) > 0
    
    def test_get_nonexistent_key(self):
        """Тест отримання неіснуючого ключа"""
        self.loc_manager.load_language('uk')
        translation = self.loc_manager.get('nonexistent_key')
        assert translation == 'nonexistent_key'  # Повертає ключ якщо переклад не знайдено
    
    def test_get_with_default(self):
        """Тест отримання з дефолтним значенням"""
        self.loc_manager.load_language('uk')
        translation = self.loc_manager.get('nonexistent_key', 'Default Value')
        assert translation == 'Default Value'
    
    def test_all_languages_have_same_keys(self):
        """Тест що всі мови мають однакові ключі"""
        languages = ['uk', 'en', 'ru']
        keys_sets = []
        
        for lang in languages:
            self.loc_manager.load_language(lang)
            keys = set(self.loc_manager._translations.keys())
            keys_sets.append(keys)
        
        # Перевіряємо що всі мови мають однакові ключі
        for i in range(1, len(keys_sets)):
            assert keys_sets[0] == keys_sets[i], f"Language {languages[i]} has different keys than {languages[0]}"
    
    def test_json_files_valid(self):
        """Тест що JSON файли локалізації валідні"""
        locale_dir = 'locale'
        languages = ['uk', 'en', 'ru']
        
        for lang in languages:
            file_path = os.path.join(locale_dir, f'{lang}.json')
            assert os.path.exists(file_path), f"File {file_path} does not exist"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                assert isinstance(data, dict), f"File {file_path} is not a valid JSON object"
                assert len(data) > 0, f"File {file_path} is empty"
    
    def test_no_duplicate_keys_in_json(self):
        """Тест що в JSON файлах немає дублікатів ключів"""
        locale_dir = 'locale'
        languages = ['uk', 'en', 'ru']
        
        for lang in languages:
            file_path = os.path.join(locale_dir, f'{lang}.json')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Перевіряємо що немає дублікатів ключів
            lines = content.split('\n')
            keys = []
            for line in lines:
                if ':' in line and not line.strip().startswith('//'):
                    key = line.split(':')[0].strip().strip('"')
                    if key:
                        keys.append(key)
            
            assert len(keys) == len(set(keys)), f"File {file_path} has duplicate keys"
    
    def test_no_trailing_commas(self):
        """Тест що в JSON файлах немає trailing commas"""
        locale_dir = 'locale'
        languages = ['uk', 'en', 'ru']
        
        for lang in languages:
            file_path = os.path.join(locale_dir, f'{lang}.json')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Перевіряємо що немає trailing commas
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip().endswith(','):
                    # Перевіряємо що це не останній елемент
                    next_line = lines[i + 1] if i + 1 < len(lines) else ''
                    if '}' in next_line or ']' in next_line:
                        assert False, f"File {file_path} has trailing comma on line {i + 1}"
    
    def test_switch_language(self):
        """Тест перемикання мови"""
        # Завантажуємо українську
        self.loc_manager.load_language('uk')
        uk_title = self.loc_manager.get('profiles_title')
        
        # Перемикаємо на англійську
        self.loc_manager.load_language('en')
        en_title = self.loc_manager.get('profiles_title')
        
        # Переклади мають бути різними
        assert uk_title != en_title
        
        # Перемикаємо назад на українську
        self.loc_manager.load_language('uk')
        uk_title_again = self.loc_manager.get('profiles_title')
        
        # Має бути той самий переклад
        assert uk_title == uk_title_again


if __name__ == '__main__':
    pytest.main([__file__])
