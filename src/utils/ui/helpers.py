# --- START OF FILE src/utils/ui/helpers.py ---

import flet as ft
import logging
from typing import Optional, Callable, Any
import asyncio

logger = logging.getLogger(__name__)

def format_number(number: float) -> str:
    """Форматує число з роздільниками тисяч"""
    return f"{int(number):,}".replace(",", " ") + " $"


def format_number_k(num: float) -> str:
    """Форматує число в стилі k/kk (1000 -> 1k, 1000000 -> 1kk)"""
    if num is None: return "0"
    num = float(num)
    if num >= 1_000_000: return f'{num / 1_000_000:.1f}kk'.replace('.0', '')
    if num >= 1_000: return f'{num / 1_000:.1f}k'.replace('.0', '')
    return str(int(num))


def format_number_full(num: float) -> str:
    """Форматує число з повними роздільниками тисяч"""
    if num is None: return "0"
    return f"{int(num):,}".replace(",", " ")

class BaseDialog:
    """Базовий клас для всіх діалогів в додатку"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.dialog: Optional[ft.AlertDialog] = None
    
    async def show(self):
        """Показує діалог"""
        if not self.page or not self.dialog:
            logger.error("Cannot show dialog: no page or dialog")
            return
        
        try:
            if self.dialog not in self.page.overlay:
                self.page.overlay.append(self.dialog)
            
            self.page.dialog = self.dialog
            self.dialog.open = True
            self.page.update()
            logger.debug("Dialog shown successfully")
        except Exception as e:
            logger.error(f"Error showing dialog: {e}")
    
    async def close(self):
        """Закриває діалог"""
        if not self.page or not self.dialog:
            return
        
        try:
            self.dialog.open = False
            self.page.update()
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")

class SafeAsyncExecutor:
    """Безпечний виконавець асинхронних операцій з timeout та retry"""
    
    DEFAULT_TIMEOUT = 30.0  # 30 секунд за замовчуванням
    DEFAULT_RETRIES = 2     # 2 спроби за замовчуванням
    
    @staticmethod
    async def execute(
        func: Callable, 
        *args, 
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        **kwargs
    ) -> Any:
        """
        Безпечно виконує асинхронну функцію з timeout та retry
        
        Args:
            func: Функція для виконання
            *args: Аргументи функції
            timeout: Timeout в секундах
            retries: Кількість спроб
            **kwargs: Ключові аргументи функції
            
        Returns:
            Результат виконання функції
            
        Raises:
            asyncio.TimeoutError: Якщо операція перевищила timeout
            Exception: Остання помилка після всіх спроб
        """
        last_exception = None
        
        for attempt in range(retries + 1):
            try:
                logger.debug(f"Executing {func.__name__} (attempt {attempt + 1}/{retries + 1})")
                
                # Виконуємо функцію з timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
                
                logger.debug(f"Successfully executed {func.__name__}")
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Timeout executing {func.__name__} (attempt {attempt + 1}): {timeout}s")
                
                if attempt < retries:
                    # Чекаємо перед повторною спробою
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                else:
                    logger.error(f"All attempts failed for {func.__name__} due to timeout")
                    raise
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Error executing {func.__name__} (attempt {attempt + 1}): {e}")
                
                # Якщо це generator помилка, не повторюємо
                if "generator didn't stop" in str(e):
                    logger.error(f"Generator error in {func.__name__}, stopping retries")
                    break
                
                if attempt < retries:
                    # Чекаємо перед повторною спробою
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                else:
                    logger.error(f"All attempts failed for {func.__name__}: {e}")
                    raise
        
        # Це не повинно статися, але на всяк випадок
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Unknown error executing {func.__name__}")

    @staticmethod
    async def execute_with_fallback(
        func: Callable, 
        fallback_value: Any,
        *args, 
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        **kwargs
    ) -> Any:
        """
        Виконує функцію з fallback значенням у випадку помилки
        
        Args:
            func: Функція для виконання
            fallback_value: Значення для повернення у випадку помилки
            *args: Аргументи функції
            timeout: Timeout в секундах
            retries: Кількість спроб
            **kwargs: Ключові аргументи функції
            
        Returns:
            Результат виконання функції або fallback_value
        """
        try:
            return await SafeAsyncExecutor.execute(
                func, *args, timeout=timeout, retries=retries, **kwargs
            )
        except Exception as e:
            logger.error(f"Function {func.__name__} failed, using fallback value: {e}")
            return fallback_value

# Константи для стилів
BUTTON_STYLE_PRIMARY = ft.ButtonStyle(
    color=ft.Colors.GREY_50,
    bgcolor=ft.Colors.GREEN_600,
    padding=ft.padding.symmetric(horizontal=24, vertical=16),
    shape=ft.RoundedRectangleBorder(radius=12),
)

BUTTON_STYLE_SECONDARY = ft.ButtonStyle(
    color=ft.Colors.GREY_50,
    bgcolor=ft.Colors.BLUE_600,
    padding=ft.padding.symmetric(horizontal=24, vertical=16),
    shape=ft.RoundedRectangleBorder(radius=12),
)

BUTTON_STYLE_DANGER = ft.ButtonStyle(
    color=ft.Colors.GREY_50,
    bgcolor=ft.Colors.RED_600,
    padding=ft.padding.symmetric(horizontal=24, vertical=16),
    shape=ft.RoundedRectangleBorder(radius=12),
)

TEXT_FIELD_STYLE = {
    "border_color": ft.Colors.BLUE_400,
    "text_size": 16,
    "label_style": ft.TextStyle(color=ft.Colors.GREY_300, weight=ft.FontWeight.W_500),
    "text_style": ft.TextStyle(color=ft.Colors.GREY_50, weight=ft.FontWeight.W_500),
    "bgcolor": ft.Colors.GREY_800,
    "border_radius": 12,
    "focused_border_color": ft.Colors.BLUE_300,
    "focused_bgcolor": ft.Colors.GREY_700,
}

def create_loading_indicator() -> ft.Control:
    """Створює індикатор завантаження"""
    return ft.Container(
        content=ft.Column([
            ft.ProgressRing(color=ft.Colors.BLUE_400),
            ft.Text("Завантаження...", color=ft.Colors.GREY_400, size=14)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        alignment=ft.alignment.center,
        expand=True
    )

def create_error_message(message: str) -> ft.Control:
    """Створює повідомлення про помилку"""
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=40),
            ft.Text(message, color=ft.Colors.RED_400, size=16, text_align=ft.TextAlign.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        alignment=ft.alignment.center,
        expand=True
    )


def create_amount_display(amount: float, color: str, size: int = 20) -> ft.Row:
    """Стандартизований віджет для відображення суми грошей.
    Використовує темний текст (без чисто білого) та жирний шрифт.
    """
    return ft.Row(
        controls=[
            ft.Text(
                format_number(amount),
                size=size,
                color=color,
                weight=ft.FontWeight.BOLD,
            )
        ],
        spacing=0,
        alignment=ft.MainAxisAlignment.END,
    )
