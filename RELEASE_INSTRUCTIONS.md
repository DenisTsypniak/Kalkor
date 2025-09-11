# 🚀 Інструкція по створенню релізу

## 📋 Перед створенням релізу

### 1. Перевірте код
```bash
# Запустіть тести
python run_tests.py

# Перевірте, що все працює
python run.py
```

### 2. Оновіть версію
Відредагуйте `src/utils/config.py`:
```python
APP_VERSION = "1.1.1"  # Нова версія
```

## 🎯 Створення релізу

### Автоматичний спосіб (рекомендований)
```bash
# Створити реліз з поточною версією
python create_release.py

# Або вказати версію вручну
python create_release.py --version 1.1.1

# Якщо не хочете відправляти на GitHub одразу
python create_release.py --no-push
```

### Ручний спосіб
```bash
# 1. Оновіть версію в файлах
# 2. Додайте зміни
git add .
git commit -m "Release v1.1.1"

# 3. Створіть тег
git tag v1.1.1

# 4. Відправте на GitHub
git push origin main
git push origin --tags
```

## 🔄 Що відбувається автоматично

1. **GitHub Actions** запускається при push тегу
2. **Збирається** додаток (PyInstaller)
3. **Створюється** ZIP архів з додатком
4. **Розраховується** SHA256 хеш
5. **Оновлюється** `latest_version.json`
6. **Створюється** GitHub Release
7. **Завантажується** архів як asset

## 📁 Структура релізу

```
Kalkor_v1.1.1.zip
├── Kalkor.exe          # Основний додаток
├── updater.exe         # Оновлювач
├── latest_version.json # Інформація про версію
└── README.md          # Документація
```

## 🔧 Налаштування GitHub

### 1. Створіть репозиторій
- Назва: `Kalkor`
- Власник: `DenisTsypniak`
- Публічний/Приватний

### 2. Налаштуйте GitHub Actions
Файл `.github/workflows/release.yml` вже створено і налаштовано.

### 3. Перевірте URL
У `run.py` та `latest_version.json` вказано правильний URL:
```
https://raw.githubusercontent.com/DenisTsypniak/Kalkor/main/latest_version.json
```

## 🧪 Тестування системи оновлень

### 1. Локальне тестування
```bash
# Запустіть додаток
python run.py

# Перевірте, чи працює перевірка оновлень
# (в консолі повинні з'явитися повідомлення)
```

### 2. Тестування updater'а
```bash
# Зберіть updater
pyinstaller updater.spec

# Протестуйте з тестовим URL
updater.exe "https://example.com/test.zip"
```

## 🐛 Вирішення проблем

### Проблема: GitHub Actions не запускається
**Рішення:**
- Перевірте, чи створено тег правильно: `git tag -l`
- Переконайтеся, що тег відправлено: `git push origin --tags`

### Проблема: Додаток не оновлюється
**Рішення:**
- Перевірте URL в `latest_version.json`
- Переконайтеся, що файл доступний: відкрийте URL в браузері
- Перевірте логи в `updater_log.txt`

### Проблема: Помилка збірки
**Рішення:**
- Перевірте, чи встановлені всі залежності: `pip install -r requirements.txt`
- Переконайтеся, що PyInstaller працює: `pyinstaller --version`

## 📊 Моніторинг релізів

### GitHub Releases
- Перейдіть на https://github.com/DenisTsypniak/Kalkor/releases
- Перевірте, чи створився новий реліз
- Завантажте та протестуйте архів

### Логи
- GitHub Actions: вкладка "Actions" в репозиторії
- Локальні логи: `logs/` папка
- Updater логи: `updater_log.txt`

## 🎉 Після створення релізу

1. **Протестуйте** завантажений архів
2. **Перевірте** автоматичні оновлення
3. **Оновіть** документацію (якщо потрібно)
4. **Повідомте** користувачів про новий реліз

---

**💡 Порада:** Завжди тестуйте реліз перед публікацією!

