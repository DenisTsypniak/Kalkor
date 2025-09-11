#!/usr/bin/env python3
"""
Script для створення релізу
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime

def get_current_version():
    """Отримує поточну версію з config.py"""
    with open('src/utils/config.py', 'r', encoding='utf-8') as f:
        content = f.read()
        for line in content.split('\n'):
            if line.strip().startswith('APP_VERSION'):
                return line.split('"')[1]
    return None

def update_version_files(version):
    """Оновлює версію в усіх файлах"""
    # Оновлюємо config.json
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    config['app']['version'] = version
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # Оновлюємо latest_version.json
    with open('latest_version.json', 'r', encoding='utf-8') as f:
        latest = json.load(f)
    latest['version'] = version
    latest['release_date'] = datetime.now().strftime('%Y-%m-%d')
    with open('latest_version.json', 'w', encoding='utf-8') as f:
        json.dump(latest, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Версія оновлена до {version}")

def create_git_tag(version):
    """Створює git тег"""
    tag_name = f"v{version}"
    
    # Додаємо зміни
    subprocess.run(['git', 'add', '.'], check=True)
    subprocess.run(['git', 'commit', '-m', f'Release {tag_name}'], check=True)
    
    # Створюємо тег
    subprocess.run(['git', 'tag', tag_name], check=True)
    
    print(f"✅ Git тег {tag_name} створено")

def push_to_github():
    """Відправляє зміни на GitHub"""
    subprocess.run(['git', 'push', 'origin', 'main'], check=True)
    subprocess.run(['git', 'push', 'origin', '--tags'], check=True)
    
    print("✅ Зміни відправлено на GitHub")

def main():
    parser = argparse.ArgumentParser(description='Створення релізу')
    parser.add_argument('--version', help='Версія релізу (наприклад, 1.1.0)')
    parser.add_argument('--no-push', action='store_true', help='Не відправляти на GitHub')
    
    args = parser.parse_args()
    
    if args.version:
        version = args.version
    else:
        version = get_current_version()
        if not version:
            print("❌ Не вдалося отримати поточну версію")
            sys.exit(1)
    
    print(f"🚀 Створення релізу версії {version}")
    
    try:
        # Оновлюємо файли
        update_version_files(version)
        
        # Створюємо git тег
        create_git_tag(version)
        
        # Відправляємо на GitHub (якщо не вказано --no-push)
        if not args.no_push:
            push_to_github()
            print("🎉 Реліз створено! GitHub Actions автоматично збере додаток.")
        else:
            print("📝 Реліз підготовлено. Виконайте 'git push origin main --tags' для завершення.")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неочікувана помилка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

