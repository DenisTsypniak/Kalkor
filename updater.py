# --- START OF FILE updater.py (Фінальна версія з примусовим завершенням) ---

import sys
import subprocess
import threading
import time
import requests
import zipfile
import io
import os
import psutil
import shutil
import tempfile
import traceback
import hashlib
import json
from tkinter import Tk, Label
from tkinter.ttk import Progressbar

# --- Логування ---
LOG_FILE = "updater_log.txt"


def log_message(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        f.write(f"[{timestamp}] {message}\n")


def calculate_file_hash(file_path):
    """Розраховує SHA256 хеш файлу"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        log_message(f"Помилка при розрахунку хешу файлу {file_path}: {e}")
        return None


def verify_file_integrity(file_path, expected_hash):
    """Перевіряє цілісність файлу за хешем"""
    if not expected_hash:
        log_message("Хеш не надано, пропускаємо перевірку")
        return True
    
    actual_hash = calculate_file_hash(file_path)
    if not actual_hash:
        return False
    
    is_valid = actual_hash.lower() == expected_hash.lower()
    if is_valid:
        log_message(f"✅ Хеш файлу {file_path} валідний")
    else:
        log_message(f"❌ Хеш файлу {file_path} не валідний. Очікувано: {expected_hash}, отримано: {actual_hash}")
    
    return is_valid


def download_with_retry(url, max_retries=3, timeout=30):
    """Завантажує файл з повторними спробами"""
    for attempt in range(max_retries):
        try:
            log_message(f"Спроба завантаження {attempt + 1}/{max_retries}: {url}")
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            log_message(f"Помилка завантаження (спроба {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                log_message(f"Очікування {wait_time} секунд перед наступною спробою...")
                time.sleep(wait_time)
            else:
                raise e


MAIN_APP_EXE = "Kalkor.exe"
UPDATER_EXE_NAME = "updater.exe"


def get_update_info(url):
    """Отримує інформацію про оновлення з URL"""
    try:
        log_message(f"Отримання інформації про оновлення з: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Якщо URL вказує на JSON файл
        if url.endswith('.json'):
            return response.json()
        
        # Якщо URL вказує на zip файл, повертаємо базову інформацію
        return {
            "url": url,
            "sha256": None,  # Хеш буде отримано пізніше
            "version": "unknown"
        }
    except Exception as e:
        log_message(f"Помилка отримання інформації про оновлення: {e}")
        return None


# --- ЗМІНЕНО/ДОДАНО: Функція для "вбивства" процесу ---
def terminate_process_by_name(process_name):
    """Знаходить процес за іменем та примусово його завершує."""
    log_message(f"Пошук процесу '{process_name}' для завершення...")
    for proc in psutil.process_iter(['pid', 'name']):
        # .lower() для надійності, оскільки імена процесів можуть бути в різному регістрі
        if proc.info['name'].lower() == process_name.lower():
            try:
                log_message(f"Знайдено процес '{proc.info['name']}' з PID {proc.pid}. Примусове завершення...")
                p = psutil.Process(proc.pid)
                p.kill()  # kill() - це найнадійніший спосіб (SIGKILL)
                p.wait(timeout=5)  # Чекаємо підтвердження, що процес завершився
                log_message(f"Процес {proc.pid} успішно завершено.")
            except psutil.NoSuchProcess:
                log_message(f"Процес {proc.pid} вже не існує.")
            except psutil.AccessDenied:
                log_message(f"ПОМИЛКА: Відмовлено в доступі при спробі завершити процес {proc.pid}.")
            except Exception as e:
                log_message(f"ПОМИЛКА: Невідома помилка при завершенні процесу {proc.pid}: {e}")


# --- ПОКРАЩЕНО: Логіка потоку оновлення з перевіркою хешу та retry ---
def update_thread_logic(url, update_status_func):
    log_message("--- ФОНОВИЙ ПОТІК ОНОВЛЕННЯ ЗАПУЩЕНО ---")
    temp_dir = None
    downloaded_file = None
    
    try:
        # --- КЛЮЧОВА ЗМІНА: Перший крок - гарантоване завершення старої програми ---
        update_status_func("Завершення попередньої версії...", 0.1)
        terminate_process_by_name(MAIN_APP_EXE)
        time.sleep(2)  # Даємо час системі звільнити файли

        # Отримуємо інформацію про оновлення
        update_status_func("Отримання інформації про оновлення...", 0.15)
        update_info = get_update_info(url)
        if not update_info:
            raise Exception("Не вдалося отримати інформацію про оновлення")
        
        # Визначаємо URL для завантаження
        download_url = update_info.get("url", url)
        expected_hash = update_info.get("sha256")
        version = update_info.get("version", "unknown")
        
        log_message(f"Оновлення до версії: {version}")
        if expected_hash:
            log_message(f"Очікуваний хеш: {expected_hash}")

        # Завантажуємо файл з retry логікою
        update_status_func("Завантаження оновлення...", 0.2)
        response = download_with_retry(download_url)
        
        # Зберігаємо завантажений файл для перевірки хешу
        temp_dir = tempfile.mkdtemp(prefix="update_")
        downloaded_file = os.path.join(temp_dir, "update.zip")
        
        with open(downloaded_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Перевіряємо цілісність файлу
        if expected_hash:
            update_status_func("Перевірка цілісності файлу...", 0.4)
            if not verify_file_integrity(downloaded_file, expected_hash):
                raise Exception("Файл оновлення пошкоджений або не автентичний")
        
        # Розпакуємо файли
        update_status_func("Розпакування файлів...", 0.6)
        with zipfile.ZipFile(downloaded_file) as archive:
            archive.extractall(temp_dir)
        
        # Оновлюємо файли
        update_status_func("Оновлення файлів...", 0.8)
        files_updated = 0
        for item_name in os.listdir(temp_dir):
            if item_name == "update.zip":
                continue
                
            source_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(os.getcwd(), item_name)
            
            if item_name.lower() == UPDATER_EXE_NAME.lower():
                log_message(f"Пропускаємо оновлення самого себе: {item_name}")
                continue

            log_message(f"Оновлення файлу: {item_name}")
            
            # Створюємо backup старого файлу
            if os.path.exists(dest_path):
                old_file_path = dest_path + ".old"
                if os.path.exists(old_file_path): 
                    os.remove(old_file_path)
                os.rename(dest_path, old_file_path)
            
            # Переміщуємо новий файл
            shutil.move(source_path, dest_path)
            files_updated += 1
        
        log_message(f"Оновлено {files_updated} файлів")
        update_status_func("Файли успішно оновлено!", 0.9)
        
        # Перевіряємо, чи основний файл існує
        main_app_path = os.path.join(os.getcwd(), MAIN_APP_EXE)
        if not os.path.exists(main_app_path):
            raise Exception(f"Основний файл {MAIN_APP_EXE} не знайдено після оновлення")
        
        update_status_func("Перезапуск додатку...", 1.0)
        subprocess.Popen([MAIN_APP_EXE])
        time.sleep(2)
        update_status_func("Завершено!", 1.0, finished=True)

    except Exception as e:
        full_traceback = traceback.format_exc()
        log_message(f"!!! КРИТИЧНА ПОМИЛКА В ФОНОВОМУ ПОТОЦІ !!!\n{full_traceback}")
        update_status_func(f"Помилка: {e}", 0, error=True)
        
        # Спроба відновлення з backup файлів
        try:
            log_message("Спроба відновлення з backup файлів...")
            for file_name in os.listdir(os.getcwd()):
                if file_name.endswith(".old"):
                    original_name = file_name[:-4]  # Видаляємо .old
                    original_path = os.path.join(os.getcwd(), original_name)
                    backup_path = os.path.join(os.getcwd(), file_name)
                    
                    if os.path.exists(backup_path):
                        if os.path.exists(original_path):
                            os.remove(original_path)
                        os.rename(backup_path, original_path)
                        log_message(f"Відновлено файл: {original_name}")
        except Exception as restore_error:
            log_message(f"Помилка відновлення: {restore_error}")
    
    finally:
        # Очищаємо тимчасові файли
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                log_message("Тимчасові файли очищено")
            except Exception as e:
                log_message(f"Помилка очищення тимчасових файлів: {e}")


def main_gui():
    if len(sys.argv) < 2:
        return

    download_url = sys.argv[1]
    root = Tk()
    root.title("Оновлення Kalkor")

    window_width, window_height = 450, 200
    center_x = int(root.winfo_screenwidth() / 2 - window_width / 2)
    center_y = int(root.winfo_screenheight() / 2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    root.resizable(False, False)
    root.configure(bg='#202020')

    # Заголовок
    title_label = Label(root, text="Оновлення Kalkor", fg="white", bg='#202020', font=("Segoe UI", 12, "bold"))
    title_label.pack(pady=(20, 10))

    # Статус
    status_label = Label(root, text="Підготовка до оновлення...", fg="white", bg='#202020', font=("Segoe UI", 9))
    status_label.pack(pady=5)

    # Прогрес бар
    progress_bar = Progressbar(root, orient="horizontal", length=350, mode="determinate")
    progress_bar.pack(pady=10)

    # Детальна інформація
    detail_label = Label(root, text="", fg="#888888", bg='#202020', font=("Segoe UI", 8))
    detail_label.pack(pady=5)

    # Кнопка скасування (поки що неактивна)
    cancel_button = Label(root, text="Не закривайте це вікно", fg="#666666", bg='#202020', font=("Segoe UI", 8))
    cancel_button.pack(pady=10)

    def update_status(text, progress, finished=False, error=False):
        status_label.config(text=text)
        progress_bar['value'] = progress * 100
        
        # Оновлюємо детальну інформацію
        if progress > 0:
            detail_label.config(text=f"Прогрес: {int(progress * 100)}%")
        
        if error: 
            status_label.config(fg="red")
            detail_label.config(text="Помилка оновлення. Перевірте лог файл.")
            cancel_button.config(text="Натисніть Enter для закриття", fg="white")
            root.bind('<Return>', lambda e: root.destroy())
        elif finished: 
            status_label.config(fg="#00ff00")
            detail_label.config(text="Оновлення завершено успішно!")
            cancel_button.config(text="Натисніть Enter для закриття", fg="white")
            root.bind('<Return>', lambda e: root.destroy())

    thread = threading.Thread(target=update_thread_logic, args=(download_url, update_status), daemon=True)
    thread.start()
    root.mainloop()


if __name__ == "__main__":
    if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
    log_message("--- Tkinter Updater запущено ---")
    main_gui()