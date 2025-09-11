# --- START OF FILE src/views/base_view.py ---

import flet as ft
from typing import Optional
from src.app.app_state import AppState
from src.utils.localization import LocalizationManager


class BaseView(ft.Column):
    """Базовий клас для всіх view з загальною функціональністю"""
    
    def __init__(self, app_state: AppState, loc: LocalizationManager, **kwargs):
        super().__init__(**kwargs)
        self.app_state = app_state
        self.loc = loc
        self.page: Optional[ft.Page] = None
        self._is_built = False
    
    def set_page(self, page: ft.Page):
        """Встановлює посилання на сторінку"""
        self.page = page
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # За замовчуванням просто оновлюємо сторінку
            if self.page:
                self.page.update()
        except Exception as e:
            print(f"Error restoring focus in {self.__class__.__name__}: {e}")
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        if not self.page or not hasattr(self.page, 'overlay'):
            return
        
        try:
            # Базова реалізація - закриваємо всі AlertDialog
            for overlay_item in self.page.overlay[:]:
                if isinstance(overlay_item, ft.AlertDialog) and hasattr(overlay_item, 'open'):
                    try:
                        overlay_item.open = False
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error closing dialogs in {self.__class__.__name__}: {e}")
    
    async def _on_lang_change(self, lang_code: str):
        """Обробник зміни мови - має бути перевизначений в дочірніх класах"""
        if not self._is_built:
            return
        # Базова реалізація - просто оновлюємо сторінку
        if self.page:
            self.page.update()
    
    async def on_view_show(self):
        """Викликається при показі view - має бути перевизначений в дочірніх класах"""
        try:
            if self is None:
                return
            # Базова реалізація - встановлюємо opacity
            if hasattr(self, 'opacity'):
                self.opacity = 1.0
        except Exception:
            pass
    
    async def on_view_hide(self):
        """Викликається при приховуванні view - має бути перевизначений в дочірніх класах"""
        try:
            # Базова реалізація - очищаємо ресурси
            pass
        except Exception:
            pass
    
    def _update_localization(self):
        """Оновлює локалізацію - має бути перевизначений в дочірніх класах"""
        if not self._is_built:
            return
        # Базова реалізація - просто оновлюємо сторінку
        if self.page:
            self.page.update()
    
    def did_mount(self):
        """Метод життєвого циклу Flet - викликається коли контрол додано на сторінку"""
        if not self._is_built:
            self._rebuild_full_view()
            self._is_built = True
    
    def _rebuild_full_view(self):
        """Перебудовує повний view - має бути перевизначений в дочірніх класах"""
        pass


class BaseContainerView(ft.Container):
    """Базовий клас для view, які наслідують від ft.Container"""
    
    def __init__(self, app_state: AppState, loc: LocalizationManager, **kwargs):
        super().__init__(**kwargs)
        self.app_state = app_state
        self.loc = loc
        self.page: Optional[ft.Page] = None
        self._is_built = False
    
    def set_page(self, page: ft.Page):
        """Встановлює посилання на сторінку"""
        self.page = page
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # За замовчуванням просто оновлюємо сторінку
            if self.page:
                self.page.update()
        except Exception as e:
            print(f"Error restoring focus in {self.__class__.__name__}: {e}")
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        if not self.page or not hasattr(self.page, 'overlay'):
            return
        
        try:
            # Базова реалізація - закриваємо всі AlertDialog
            for overlay_item in self.page.overlay[:]:
                if isinstance(overlay_item, ft.AlertDialog) and hasattr(overlay_item, 'open'):
                    try:
                        overlay_item.open = False
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error closing dialogs in {self.__class__.__name__}: {e}")
    
    async def _on_lang_change(self, lang_code: str):
        """Обробник зміни мови - має бути перевизначений в дочірніх класах"""
        if not self._is_built:
            return
        # Базова реалізація - просто оновлюємо сторінку
        if self.page:
            self.page.update()
    
    async def on_view_show(self):
        """Викликається при показі view - має бути перевизначений в дочірніх класах"""
        try:
            if self is None:
                return
            # Базова реалізація - встановлюємо opacity
            if hasattr(self, 'opacity'):
                self.opacity = 1.0
        except Exception:
            pass
    
    async def on_view_hide(self):
        """Викликається при приховуванні view - має бути перевизначений в дочірніх класах"""
        try:
            # Базова реалізація - очищаємо ресурси
            pass
        except Exception:
            pass
    
    def _update_localization(self):
        """Оновлює локалізацію - має бути перевизначений в дочірніх класах"""
        if not self._is_built:
            return
        # Базова реалізація - просто оновлюємо сторінку
        if self.page:
            self.page.update()
    
    def did_mount(self):
        """Метод життєвого циклу Flet - викликається коли контрол додано на сторінку"""
        if not self._is_built:
            self._rebuild_full_view()
            self._is_built = True
    
    def _rebuild_full_view(self):
        """Перебудовує повний view - має бути перевизначений в дочірніх класах"""
        pass