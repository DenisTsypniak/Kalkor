"""
Утиліти для покращення відгуковості UI
"""

import asyncio
import logging
from typing import Callable, Any, Optional, Union
from functools import wraps
import time
import flet as ft
# from .ui_helpers import create_loading_indicator  # Видалено - не використовується

logger = logging.getLogger(__name__)

class LoadingManager:
    """Менеджер для показу loading індикаторів"""
    
    def __init__(self):
        self._loading_indicators: dict[str, 'ft.Control'] = {}
        self._loading_states: dict[str, bool] = {}
    
    def show_loading(self, key: str, indicator: 'ft.Control'):
        """Показує loading індикатор"""
        self._loading_indicators[key] = indicator
        self._loading_states[key] = True
        
        if hasattr(indicator, 'visible'):
            indicator.visible = True
        if hasattr(indicator, 'opacity'):
            indicator.opacity = 1.0
        
        if hasattr(indicator, 'page') and indicator.page:
            indicator.update()
    
    def hide_loading(self, key: str):
        """Приховує loading індикатор"""
        if key in self._loading_indicators:
            indicator = self._loading_indicators[key]
            self._loading_states[key] = False
            
            if hasattr(indicator, 'visible'):
                indicator.visible = False
            if hasattr(indicator, 'opacity'):
                indicator.opacity = 0.0
            
            if hasattr(indicator, 'page') and indicator.page:
                indicator.update()
    
    def is_loading(self, key: str) -> bool:
        """Перевіряє чи показується loading"""
        return self._loading_states.get(key, False)

class Debouncer:
    """Debouncer для оптимізації часті виклики"""
    
    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self._tasks: dict[str, asyncio.Task] = {}
    
    async def debounce(self, key: str, func: Callable, *args, **kwargs):
        """Debounce функцію"""
        # Скасовуємо попередню задачу
        if key in self._tasks:
            self._tasks[key].cancel()
        
        # Створюємо нову задачу
        async def delayed_execution():
            await asyncio.sleep(self.delay)
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in debounced function {func.__name__}: {e}")
            finally:
                if key in self._tasks:
                    del self._tasks[key]
        
        self._tasks[key] = asyncio.create_task(delayed_execution())
        return self._tasks[key]

class Throttler:
    """Throttler для обмеження частоти викликів"""
    
    def __init__(self, rate: float = 1.0):  # 1 виклик в секунду
        self.rate = rate
        self._last_called: dict[str, float] = {}
    
    async def throttle(self, key: str, func: Callable, *args, **kwargs):
        """Throttle функцію"""
        current_time = time.time()
        last_called = self._last_called.get(key, 0)
        
        if current_time - last_called >= self.rate:
            self._last_called[key] = current_time
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in throttled function {func.__name__}: {e}")

def async_ui_operation(loading_key: Optional[str] = None, show_loading: bool = True):
    """Декоратор для асинхронних UI операцій"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            loading_manager = get_loading_manager()
            
            try:
                if show_loading and loading_key:
                    # Створюємо loading індикатор
                    loading_indicator = ft.Container(
                        content=ft.Row([
                            ft.ProgressRing(
                                width=20,
                                height=20,
                                stroke_width=2,
                                color=ft.Colors.BLUE_400
                            ),
                            ft.Text(
                                "Завантаження...",
                                color=ft.Colors.WHITE70,
                                size=14
                            )
                        ], 
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10),
                        padding=ft.padding.all(20),
                        alignment=ft.alignment.center
                    )
                    loading_manager.show_loading(loading_key, loading_indicator)
                
                # Виконуємо операцію
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                logger.error(f"Error in async UI operation {func.__name__}: {e}")
                raise
            finally:
                if show_loading and loading_key:
                    loading_manager.hide_loading(loading_key)
        
        return wrapper
    return decorator


class UIResponsivenessManager:
    """Головний менеджер для відгуковості UI"""
    
    def __init__(self):
        self.loading_manager = LoadingManager()
        self.debouncer = Debouncer()
        self.throttler = Throttler()
        self._background_tasks: set[asyncio.Task] = set()
    
    async def execute_in_background(self, func: Callable, *args, **kwargs):
        """Виконує функцію в фоні"""
        task = asyncio.create_task(self._safe_background_execution(func, *args, **kwargs))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task
    
    async def _safe_background_execution(self, func: Callable, *args, **kwargs):
        """Безпечне виконання в фоні"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in background execution {func.__name__}: {e}")
    
    async def debounce_ui_update(self, key: str, update_func: Callable, *args, **kwargs):
        """Debounce UI оновлення"""
        return await self.debouncer.debounce(key, update_func, *args, **kwargs)
    
    async def throttle_ui_update(self, key: str, update_func: Callable, *args, **kwargs):
        """Throttle UI оновлення"""
        return await self.throttler.throttle(key, update_func, *args, **kwargs)
    
    def show_loading(self, key: str, indicator: 'ft.Control'):
        """Показує loading"""
        self.loading_manager.show_loading(key, indicator)
    
    def hide_loading(self, key: str):
        """Приховує loading"""
        self.loading_manager.hide_loading(key)
    
    def is_loading(self, key: str) -> bool:
        """Перевіряє loading стан"""
        return self.loading_manager.is_loading(key)
    
    async def cleanup(self):
        """Очищає ресурси"""
        # Скасовуємо всі фонові задачі
        for task in self._background_tasks:
            task.cancel()
        
        # Чекаємо завершення
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self._background_tasks.clear()

# Глобальний екземпляр
_ui_manager = UIResponsivenessManager()

def get_ui_responsiveness_manager() -> UIResponsivenessManager:
    """Отримує глобальний менеджер відгуковості UI"""
    return _ui_manager

def get_loading_manager() -> LoadingManager:
    """Отримує менеджер loading індикаторів"""
    return _ui_manager.loading_manager

def get_debouncer() -> Debouncer:
    """Отримує debouncer"""
    return _ui_manager.debouncer

def get_throttler() -> Throttler:
    """Отримує throttler"""
    return _ui_manager.throttler

# Утилітарні функції
async def safe_ui_update(control: 'ft.Control', update_func: Callable):
    """Безпечно оновлює UI елемент"""
    try:
        if asyncio.iscoroutinefunction(update_func):
            await update_func()
        else:
            update_func()
        
        if hasattr(control, 'page') and control.page:
            control.update()
    except Exception as e:
        logger.error(f"Error updating UI control: {e}")

async def batch_ui_updates(controls: list['ft.Control'], update_funcs: list[Callable]):
    """Пакетно оновлює UI елементи"""
    try:
        # Виконуємо всі оновлення
        for update_func in update_funcs:
            if asyncio.iscoroutinefunction(update_func):
                await update_func()
            else:
                update_func()
        
        # Оновлюємо всі контроли одним викликом
        page = None
        for control in controls:
            if hasattr(control, 'page') and control.page:
                page = control.page
                break
        
        if page:
            page.update()
    except Exception as e:
        logger.error(f"Error in batch UI updates: {e}")
