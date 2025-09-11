# --- START OF FILE run.py ---

import flet as ft
import asyncio
import aiohttp
import subprocess
import sys
import os
from packaging import version
import glob
import time
import ctypes
from ctypes import wintypes

from src.app.app_main import App
from src.data.data_manager import init_db
from src.utils.config import APP_VERSION, resource_path
from src.utils.logger import get_logger
from src.core.simple_integration import initialize_optimization_systems, dispose_optimization_systems

UPDATER_EXE_NAME = "updater.exe"
IS_BUNDLED = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def lock_window_size():
    """Спрощена функція блокування розміру вікна"""
    pass  # Тимчасово вимикаємо Windows API блокування


def cleanup_old_files():
    time.sleep(1)
    current_dir = os.getcwd()
    old_files = glob.glob(os.path.join(current_dir, "*.old"))
    if not old_files: return
    for f in old_files:
        try:
            os.remove(f)
        except OSError:
            pass


async def check_for_updates(page: ft.Page) -> dict | None:
    # Fallback URLs для надійності
    json_urls = [
        "https://raw.githubusercontent.com/DenisTsypniak/Kalkor/main/latest_version.json",
        "https://github.com/DenisTsypniak/Kalkor/raw/main/latest_version.json",
        "https://cdn.jsdelivr.net/gh/DenisTsypniak/Kalkor@main/latest_version.json"
    ]
    
    headers = {
        'Cache-Control': 'no-cache', 
        'Pragma': 'no-cache',
        'User-Agent': 'Kalkor-Updater/1.0'
    }
    
    timeout = aiohttp.ClientTimeout(total=10)
    
    for i, json_url in enumerate(json_urls):
        try:
            print(f"🔍 Спроба {i+1}/{len(json_urls)}: {json_url}")
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(json_url, params={"t": time.time()}) as response:
                    if response.status != 200: 
                        print(f"⚠️ HTTP {response.status} для URL {i+1}")
                        continue
                    
                    try:
                        update_data = await response.json(content_type=None)
                    except Exception as json_error:
                        print(f"⚠️ Помилка парсингу JSON для URL {i+1}: {json_error}")
                        continue
                    
                    # Валідація структури JSON
                    required_fields = ["version", "url"]
                    for field in required_fields:
                        if field not in update_data:
                            print(f"⚠️ Відсутнє поле '{field}' в JSON оновлення для URL {i+1}")
                            break
                    else:
                        print(f"✅ Успішно отримано дані з URL {i+1}")
                        return update_data
                        
        except Exception as e:
            print(f"⚠️ Помилка з URL {i+1}: {e}")
            continue
    
    print("❌ Не вдалося отримати інформацію про оновлення з жодного URL")
    return None


async def compare_versions(update_data: dict) -> dict | None:
    """Порівнює версії та повертає дані оновлення якщо потрібно"""
    try:
        latest_version = update_data.get("version")
        current_version = APP_VERSION
        
        print(f"🔍 Поточна версія: {current_version}")
        print(f"🔍 Остання версія: {latest_version}")
        
        if version.parse(latest_version) > version.parse(current_version):
            print(f"✅ Доступне оновлення до версії {latest_version}")
            return update_data
        else:
            print("✅ Використовується остання версія")
            return None
            
    except Exception as e:
        print(f"⚠️ Помилка порівняння версій: {e}")
        return None


async def main(page: ft.Page):
    # Налаштовуємо логування
    logger = get_logger(__name__)
    logger.info("Application starting...")
    
    page.title = "Kalkor"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width = 1400
    page.window_height = 900
    page.window_resizable = False
    page.window_maximizable = False
    page.window_minimizable = True
    page.window_full_screen = False
    page.window_always_on_top = False
    page.window_center_on_start = True  # Центруємо вікно при запуску
    page.padding = 0
    page.margin = 0
    page.spacing = 0
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.auto_scroll = False
    
    # Тимчасово вимикаємо Windows API блокування
    # lock_window_size()
    
    # Обробник для запобігання зміни розміру вікна
    def on_window_event(e):
        if e.data == "resize":
            # Тимчасово вимикаємо Windows API блокування
            # lock_window_size()
            page.update()
    
    page.on_window_event = on_window_event
    
    # Обробник клавіатури для запобігання зміни розміру
    def on_keyboard_event(e):
        # Блокуємо F11 (повноекранний режим)
        if e.key == "F11":
            # Тимчасово вимикаємо Windows API блокування
            # lock_window_size()
            return True
        # Блокуємо Ctrl+Plus/Minus (масштабування)
        if e.ctrl and (e.key == "=" or e.key =="-"):
            return True
        return False
    
    page.on_keyboard_event = on_keyboard_event
    # Прибираємо індикатор завантаження

    if IS_BUNDLED:
        # --- БЛОК ОНОВЛЕННЯ ---
        cleanup_old_files()
        update_data = await check_for_updates(page)
        if update_data:
            update_info = await compare_versions(update_data)
            if update_info:
                try:
                    print(f"🚀 Запуск оновлення до версії {update_info.get('version', 'unknown')}")
                    
                    # Перевіряємо, чи існує updater.exe
                    if not os.path.exists(UPDATER_EXE_NAME):
                        print(f"❌ Файл {UPDATER_EXE_NAME} не знайдено")
                        page.controls.clear()
                        page.add(ft.Text(f"Файл оновлення {UPDATER_EXE_NAME} не знайдено", color=ft.Colors.RED))
                        page.update()
                        await asyncio.sleep(5)
                        sys.exit(1)
                    
                    # Запускаємо updater з URL
                    DETACHED_PROCESS = 0x00000008
                    updater_args = [UPDATER_EXE_NAME, update_info["url"]]
                    
                    print(f"🔧 Запуск: {' '.join(updater_args)}")
                    subprocess.Popen(updater_args, creationflags=DETACHED_PROCESS, close_fds=True)
                    
                    # Показуємо повідомлення користувачу
                    page.controls.clear()
                    page.add(ft.Text("Оновлення запущено. Будь ласка, зачекайте...", 
                                   color=ft.Colors.WHITE, size=16, text_align=ft.TextAlign.CENTER))
                    page.update()
                    
                    # Даємо час для запуску updater
                    await asyncio.sleep(2)
                    sys.exit(0)
                    
                except Exception as e:
                    print(f"❌ Помилка запуску оновлення: {e}")
                    page.controls.clear()
                    page.add(ft.Text(f"Не вдалося запустити оновлення: {e}", 
                                   color=ft.Colors.RED, size=16, text_align=ft.TextAlign.CENTER))
                    page.update()
                await asyncio.sleep(5)
                sys.exit(1)
            return

    # --- ЗАВАНТАЖЕННЯ ОСНОВНОГО UI ---
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # Встановлюємо іконку вікна, використовуючи правильний шлях
    try:
        icon_path = os.path.join("assets", "app_icon.ico")
        page.window_icon = resource_path(icon_path)
    except Exception as e:
        logger.warning(f"Failed to set window icon: {e}")

    await init_db()
    
    # Ініціалізуємо системи оптимізації з обробкою помилок
    try:
        await initialize_optimization_systems()
        print("✅ Системи оптимізації ініціалізовані")
    except Exception as e:
        print(f"⚠️ Помилка ініціалізації систем оптимізації: {e}")
        print("⚠️ Продовжуємо без повної ініціалізації систем")

    try:
        app = App(page)
        await app.async_init()  # <--- ВИКЛИКАЄМО АСИНХРОННУ ІНІЦІАЛІЗАЦІЮ

        await app.navigate(e=None)  # Переходимо на початковий екран
        page.update()
    except Exception as e:

        import traceback
        traceback.print_exc()
        # Додаємо простий fallback UI
        page.controls.clear()
        page.add(ft.Text("Помилка завантаження додатку", color=ft.Colors.RED))
        page.update()
    
    # Спрощена перевірка розміру вікна
    async def check_window_size():
        while True:
            try:
                # Тільки Flet налаштування
                if page.window_width != 1400 or page.window_height != 900:
                    page.window_width = 1400
                    page.window_height = 900
                    page.window_resizable = False
                    page.update()
            except Exception as e:
                logger.warning(f"Failed to check window size: {e}")
            await asyncio.sleep(1)  # Перевіряємо кожну секунду
    
    # Запускаємо перевірку в фоні
    asyncio.create_task(check_window_size())


if __name__ == "__main__":
    ft.app(target=main, assets_dir=".")