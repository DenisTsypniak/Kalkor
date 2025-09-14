# --- START OF FILE src/app/app_main.py ---

import flet as ft
import asyncio
import sys
import time
from typing import Callable
import os

# Імпортуємо нові системи
from src.utils.logger import get_logger
from src.utils.error_handler import error_handler, handle_errors

logger = get_logger(__name__)

from src.app.app_state import AppState
from src.data import data_manager as dm
from src.views.profiles.profiles_view import ProfilesView
from src.views.transactions.transactions_view import TransactionsView
from src.views.analytics.analytics_view import AnalyticsView
from src.components.calculator.calculator_view import Calculator
from src.views.properties.properties_view import PropertiesView
import random
from src.utils.config import resource_path, TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_EXPENSE, INITIAL_BALANCE_CATEGORY
from src.utils.localization import LocalizationManager

# Повертаємо системи оптимізації поступово
try:
    from src.utils.animation_manager import get_animation_manager
    from src.utils.metrics_collector import record_ui_metric
    from src.utils.lazy_image_loader import get_image_loader
    from src.core.simple_integration import get_integrator
    OPTIMIZATION_ENABLED = True
    print("✅ Extended optimization systems enabled")
except ImportError as e:
    print(f"⚠️ Extended optimization systems not available: {e}")
    OPTIMIZATION_ENABLED = False


class App:
    PROFILE_TRANSITION_DURATION = 450
    PROFILE_TRANSITION_OPACITY_DURATION = 300
    CALCULATOR_ANIMATION_DURATION = 300
    CALCULATOR_WIDTH = 340
    CALCULATOR_HEIGHT = 540
    MINI_PROFILE_MENU_WIDTH = 200
    MINI_PROFILE_BUTTON_SIZE = 56

    def __init__(self, page: ft.Page):
        self.page = page
        
        # Ініціалізуємо нові системи
        self._init_new_systems()
        self.app_state = AppState()
        self.loc = LocalizationManager()
        self.calculator_close_callback: Callable | None = None
        self.current_view = None  # Поточний активний view

        # --- ДОДАНО: Кеш для списку профілів ---
        self.profile_list_cache: list = []
    
    def _init_new_systems(self):
        """Ініціалізує нові системи"""
        try:
            # Реєструємо callback для обробки помилок
            error_handler.register_callback(self._on_error)
            
            # Завантажуємо конфігурацію
        except Exception as e:
            logger.error(f"Failed to initialize new systems: {e}")
    
    def _on_error(self, error):
        """Обробляє помилки"""
        logger.error(f"Application error: {error.message}")
        # Тут можна додати показ повідомлення користувачу

        # Повертаємо сервіси оптимізації поступово
        if OPTIMIZATION_ENABLED:
            try:
                self.integrator = get_integrator()
                print("✅ Integrator initialized")
                # Включаємо animation_manager для анімацій
                self.animation_manager = get_animation_manager()
                # Повертаємо image_loader (безпечний)
                self.image_loader = get_image_loader()
                print("✅ Image loader initialized")
                
            except Exception as e:
                print(f"⚠️ Error initializing services: {e}")
                self.animation_manager = None
                self.image_loader = None
        else:
            self.animation_manager = None
            self.image_loader = None

        self.app_state.register_on_profile_change(self._on_profile_change_update_ui)
        self.app_state.register_on_language_change(self._on_language_change_update_ui)
        self.page.on_keyboard_event = self._on_page_keyboard

        # Звук буде ініціалізований в async_init

        self._build_ui_placeholders()

    @handle_errors("async_init")
    async def async_init(self):
        logger.info("🚀 Initializing application...")
        
        saved_language = await dm.get_setting("language", "uk")
        self.loc.load_language(saved_language)
        self.app_state._current_language = saved_language
        
        # Ініціалізуємо звук
        self.profile_select_sound = ft.Audio(autoplay=False, volume=1, balance=0)
        self.page.overlay.append(self.profile_select_sound)
        
        sound_path = resource_path("sounds/profile_selection.mp3")
        self.profile_select_sound.src = sound_path
        logger.info(f"🔊 Sound initialized: {sound_path}")

        # --- ДОДАНО: Початкове заповнення кешу ---
        await self.refresh_profile_cache()

        self._create_navigation_controls()
        
        # --- ДОДАНО: Безпечна ініціалізація UI елементів ---
        self._safe_init_ui_elements()
        
        # Додаємо обробник втрати фокусу для закриття спливаючих вікон
        self.page.on_window_event = self._on_window_event

        # Ініціалізуємо views з обробкою помилок
        self.views = {}
        
        try:
            self.views["profiles"] = ProfilesView(
                page=self.page,
                app_state=self.app_state,
                navigate_func=self.navigate,
                loc=self.loc,
                # --- ЗМІНЕНО: Передаємо весь об'єкт App для доступу до кешу ---
                on_profile_selected=self.start_profile_transition,
                app=self
            )
        except Exception as e:
    
            import traceback
            traceback.print_exc()
            self.views["profiles"] = self._create_fallback_container("Помилка завантаження вкладки 'Профілі'")
            
        try:
            transactions_view = TransactionsView(self.app_state, self.toggle_calculator_visibility, loc=self.loc)
            # Встановлюємо page для TransactionsView
            transactions_view.page = self.page
            self.views["transactions"] = transactions_view
        except Exception as e:
            logger.error(f"Failed to initialize transactions view: {e}")
            self.views["transactions"] = self._create_fallback_container("Помилка завантаження вкладки 'Транзакції'")
        
        try:
            properties_view = PropertiesView(self.app_state, loc=self.loc)
            # Встановлюємо page для PropertiesView
            properties_view.set_page(self.page)
            self.views["properties"] = properties_view
        except Exception as e:
            logger.error(f"Failed to initialize properties view: {e}")
            self.views["properties"] = self._create_fallback_container("Помилка завантаження вкладки 'Майно'")
            
        try:
            self.views["analytics"] = AnalyticsView(self.page, self.app_state, loc=self.loc)
        except Exception as e:
            logger.error(f"Failed to initialize analytics view: {e}")
            self.views["analytics"] = self._create_fallback_container("Помилка завантаження вкладки 'Аналітика'")

        # Фільтруємо None значення перед створенням Stack
        valid_views = [view for view in self.views.values() if view is not None]
        logger.info(f"📱 Views created: {len(valid_views)} views")
        self.main_content_container.content = ft.Stack(valid_views, expand=True)
        
        # Встановлюємо початкову видимість всіх views як False
        for view in valid_views:
            if hasattr(view, 'visible'):
                view.visible = False
        self.main_content_container.animate_opacity = ft.Animation(250, "ease")
        

        
        # Створюємо layout після створення views
        self._build_layout()
        
        # Показуємо початкову сторінку профілів
        await self.navigate(e=None, view_name="profiles")
        
        # Оновлюємо UI
        self.page.update()
        logger.info("✅ Application ready!")
        


    # --- ДОДАНО: Метод для оновлення кешу профілів ---
    async def refresh_profile_cache(self):
        self.profile_list_cache = await dm.get_profile_list()
        logger.info(f"👤 Profiles loaded: {len(self.profile_list_cache)}")

    def _create_fallback_container(self, error_message: str) -> ft.Container:
        """Створює fallback контейнер з правильними атрибутами"""
        fallback_container = ft.Container(
            content=ft.Text(error_message, color=ft.Colors.RED),
            alignment=ft.alignment.center,
            expand=True,
            visible=True
        )
        # Додаємо необхідні атрибути для fallback контейнера
        fallback_container._set_attr_internal = lambda *args, **kwargs: None
        fallback_container.on_view_show = lambda: None
        fallback_container.on_view_hide = lambda: None
        return fallback_container

    async def start_profile_transition(self, e: ft.ControlEvent, profile_data: dict):
        avatar_container = e.control.content
        if hasattr(self, 'profile_select_sound'):
            self.profile_select_sound.play()
        avatar_b64 = profile_data.get('avatar_b64')
        if avatar_b64:
            self.transition_avatar_image.src_base64 = avatar_b64.split(',')[1]
            self.transition_avatar_image.visible = True
            self.transition_avatar_icon.visible = False
        else:
            self.transition_avatar_image.visible = False
            self.transition_avatar_icon.name = ft.Icons.PERSON_OUTLINE
            self.transition_avatar_icon.visible = True
        container_width = avatar_container.width if avatar_container.width is not None else 140
        container_height = avatar_container.height if avatar_container.height is not None else 140
        self.transition_overlay.width, self.transition_overlay.height = container_width, container_height
        if hasattr(e, 'global_x') and e.global_x is not None and hasattr(e, 'local_x'):
            start_x, start_y = (e.global_x - e.local_x, e.global_y - e.local_y)
        else:
            start_x, start_y = (self.page.width / 2 - (container_width / 2),
                                self.page.height / 2 - (container_height / 2))
        self.transition_overlay.top, self.transition_overlay.left = start_y, start_x
        self.transition_overlay.bgcolor = avatar_container.bgcolor
        self.transition_overlay.scale, self.transition_overlay.opacity, self.transition_overlay.visible = 1, 0, True
        self.page.update()
        await asyncio.sleep(0.01)
        self.transition_overlay.opacity = 1
        target_scale = max(self.page.width, self.page.height) / max(container_width, 1) * 2.5
        self.transition_overlay.scale = target_scale
        self.page.update()
        await asyncio.sleep(self.transition_overlay.animate_scale.duration / 1000)
        # --- ЗМІНЕНО: Встановлюємо весь об'єкт профілю ---
        self.app_state.current_profile = profile_data
        await self.navigate(e=None)
        self.transition_overlay.opacity = 0
        self.page.update()
        await asyncio.sleep(self.transition_overlay.animate_opacity.duration / 1000)
        self.transition_overlay.visible = False
        self.transition_overlay.scale = 1
        self.page.update()

    def _build_ui_placeholders(self):
        self.transition_avatar_image = ft.Image(fit=ft.ImageFit.COVER, border_radius=1000)
        self.transition_avatar_icon = ft.Icon(size=80, color=ft.Colors.GREY_50)
        self.transition_overlay = ft.Container(
            shape=ft.BoxShape.CIRCLE, scale=1, opacity=0, visible=False,
            content=ft.Stack([self.transition_avatar_image, self.transition_avatar_icon]),
            animate_scale=ft.Animation(duration=self.PROFILE_TRANSITION_DURATION, curve=ft.AnimationCurve.EASE_IN_OUT),
            animate_opacity=ft.Animation(duration=self.PROFILE_TRANSITION_OPACITY_DURATION,
                                         curve=ft.AnimationCurve.EASE_OUT))
        self.calculator_view = Calculator(page=self.page, loc=self.loc, app_state=self.app_state)
        self.calculator_overlay = ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK),
                                               visible=False,
                                               on_click=lambda e: self.page.run_task(self.close_calculator),
                                               animate_opacity=ft.Animation(200, "ease"))
        self.calculator_container = ft.Container(content=self.calculator_view, right=-self.CALCULATOR_WIDTH, bottom=20,
                                                 height=self.CALCULATOR_HEIGHT,
                                                 border_radius=20, bgcolor="#1C1C1C", padding=ft.padding.all(20),
                                                 visible=False,
                                                 animate=ft.Animation(duration=self.CALCULATOR_ANIMATION_DURATION,
                                                                      curve=ft.AnimationCurve.DECELERATE))

        self.page.overlay.extend(
            [self.transition_overlay, self.calculator_overlay, self.calculator_container])

        self.mini_profile_button_avatar = ft.Image(
            width=self.MINI_PROFILE_BUTTON_SIZE,
            height=self.MINI_PROFILE_BUTTON_SIZE,
            fit=ft.ImageFit.COVER,
            border_radius=28,
            visible=False
        )
        self.mini_profile_button_icon_container = ft.Container(
            content=ft.Icon(ft.Icons.PERSON),
            alignment=ft.alignment.center,
            expand=True,
            visible=True
        )

        self.mini_profile_button = ft.Container(
            content=ft.Stack(
                [
                    self.mini_profile_button_icon_container,
                    self.mini_profile_button_avatar
                ]
            ),
            width=self.MINI_PROFILE_BUTTON_SIZE, height=self.MINI_PROFILE_BUTTON_SIZE,
            left=22, bottom=20, bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLUE_GREY_700), shape=ft.BoxShape.CIRCLE,
            border=ft.border.all(3, ft.Colors.WHITE),  # Додаємо білу обводку до основного профілю
            on_click=self.toggle_mini_profile_menu, tooltip="Змінити профіль", visible=False,
            animate=ft.Animation(300, "ease"),
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )

        self.mini_profile_menu = ft.Container(content=ft.Column(
            controls=[ft.Row(wrap=True, spacing=15, run_spacing=15, alignment=ft.MainAxisAlignment.START)],
            scroll=ft.ScrollMode.ADAPTIVE, spacing=10), left=22, bottom=85, padding=15, border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.BLACK),
            border=ft.border.all(1, ft.Colors.WHITE24), width=self.MINI_PROFILE_MENU_WIDTH, opacity=0,
            visible=False, animate_opacity=ft.Animation(200, "easeIn"),
            animate_scale=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT_QUART),
            scale=ft.Scale(0.9))
        self.main_content_container = ft.Container(expand=True, bgcolor=ft.Colors.BLACK)

    def _safe_init_ui_elements(self):
        """Безпечно ініціалізує UI елементи з перевірками на None"""
        try:
            # Перевіряємо та ініціалізуємо навігаційні елементи
            if not hasattr(self, 'navigation_rail') or self.navigation_rail is None:
                self._create_navigation_controls()
                
            if not hasattr(self, 'divider') or self.divider is None:
                self.divider = ft.VerticalDivider(width=1, visible=False)
                
            if not hasattr(self, 'mini_profile_button') or self.mini_profile_button is None:
                self._build_ui_placeholders()
                
            # Перевіряємо калькулятор
            if not hasattr(self, 'calculator_container') or self.calculator_container is None:
                self._build_ui_placeholders()
                
        except Exception:
            pass

    def _build_lang_menu(self):
        langs_info = {
            "uk": {"name": self.loc.languages.get("uk", {}).get("lang_name", "Українська"),
                   "icon": "assets/flags/ua.png"},
            "en": {"name": self.loc.languages.get("en", {}).get("lang_name", "English"), "icon": "assets/flags/us.png"},
            "ru": {"name": self.loc.languages.get("ru", {}).get("lang_name", "Русский"), "icon": "assets/flags/ru.png"}
        }
        current_lang_code = self.app_state.current_language
        sorted_codes = sorted(langs_info.keys(), key=lambda code: code != current_lang_code)
        menu_items = [ft.PopupMenuItem(
            content=ft.Container(
                content=ft.Row([
                    ft.Image(src=langs_info[code]['icon'], width=24, height=18, fit=ft.ImageFit.CONTAIN),
                    ft.Text(langs_info[code]['name']),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if code == current_lang_code else None,
                border_radius=6, padding=ft.padding.symmetric(vertical=6, horizontal=12)),
            data=code, on_click=self.change_language
        ) for code in sorted_codes]
        return ft.PopupMenuButton(icon=ft.Icons.LANGUAGE, items=menu_items, tooltip="Вибір мови / Language selection")
    

    def _create_navigation_controls(self):
        self.lang_menu = self._build_lang_menu()
        self.navigation_rail = ft.NavigationRail(
            selected_index=0, label_type=ft.NavigationRailLabelType.ALL, min_width=100,
            min_extended_width=200, visible=False,
            trailing=ft.Column([
                ft.Container(expand=True), 
                self.lang_menu
            ], alignment=ft.MainAxisAlignment.END,
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.PAYMENT_OUTLINED, label=self.loc.get("nav_transactions")),
                ft.NavigationRailDestination(icon=ft.Icons.DIAMOND_OUTLINED, label=self.loc.get("nav_properties")),
                ft.NavigationRailDestination(icon=ft.Icons.ANALYTICS_OUTLINED, label=self.loc.get("nav_analytics")),
            ], on_change=self.navigate)
        self.divider = ft.VerticalDivider(width=1, visible=False)

    def _build_layout(self):
        left_panel = self.navigation_rail
        page_layout_row = ft.Row(controls=[left_panel, self.divider, self.main_content_container], expand=True)
        page_layout_stack = ft.Stack(controls=[page_layout_row, self.mini_profile_menu, self.mini_profile_button],
                                     expand=True)
        self.page.controls.clear()
        self.page.add(page_layout_stack)

    async def _on_page_keyboard(self, e: ft.KeyboardEvent):
        if self.calculator_container.visible:
            await self.calculator_view._on_keyboard(e)

    async def change_language(self, e: ft.ControlEvent):
        lang_code = e.control.data
        if lang_code != self.app_state.current_language:
            self.loc.load_language(lang_code)
            await dm.save_setting("language", lang_code)
            self.app_state.current_language = lang_code
            
            # Оновлюємо меню мов
            self.lang_menu = self._build_lang_menu()
            
            if self.navigation_rail.trailing: 
                self.navigation_rail.trailing.controls[-1] = self.lang_menu
            
            # Оновлюємо навігаційні пункти
            self.navigation_rail.destinations = [
                ft.NavigationRailDestination(icon=ft.Icons.PAYMENT_OUTLINED, label=self.loc.get("nav_transactions")),
                ft.NavigationRailDestination(icon=ft.Icons.DIAMOND_OUTLINED, label=self.loc.get("nav_properties")),
                ft.NavigationRailDestination(icon=ft.Icons.ANALYTICS_OUTLINED, label=self.loc.get("nav_analytics")),
            ]
            
            # Оновлюємо поточний view
            if hasattr(self, 'current_view') and self.current_view:
                if hasattr(self.current_view, '_on_lang_change'):
                    await self.current_view._on_lang_change(lang_code)
            
            # Оновлюємо навігаційну панель
            if self.navigation_rail.visible: 
                self.navigation_rail.update()
            
            # Оновлюємо міні-профіль меню якщо воно видиме
            if hasattr(self, 'mini_profile_menu') and self.mini_profile_menu.visible:
                await self._update_mini_profile_menu_content()
            
            self.page.update()
    
    def _on_window_event(self, e):
        """Обробник подій вікна для закриття спливаючих вікон при втраті фокусу"""
        if e.data == "blur":
            # Втрата фокусу - закриваємо всі спливаючі вікна
            self._close_all_overlays()
        elif e.data == "focus":
            # Отримання фокусу - відновлюємо фокус на текстові поля
            self._restore_text_focus()
    
    def cleanup(self):
        """Очищає ресурси при закритті додатку"""
        try:
            print("🔍 Cleaning up app resources...")
            
            # Закриваємо всі спливаючі вікна
            self._close_all_overlays()
            
            # Очищаємо views
            if hasattr(self, 'views'):
                for view in self.views.values():
                    if hasattr(view, 'cleanup'):
                        view.cleanup()
            
            # Очищаємо системи оптимізації
            try:
                from src.core.simple_integration import dispose_optimization_systems
                dispose_optimization_systems()
                print("✅ Optimization systems disposed")
            except Exception as e:
                print(f"⚠️ Error disposing optimization systems: {e}")
            
            # Очищаємо базу даних
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._cleanup_database())
                else:
                    loop.run_until_complete(self._cleanup_database())
            except Exception as e:
                print(f"⚠️ Error cleaning up database: {e}")
            
            print("✅ App cleanup completed")
            
        except Exception as e:
            print(f"⚠️ Error during app cleanup: {e}")
    
    async def _cleanup_database(self):
        """Асинхронна очистка бази даних"""
        try:
            from src.data.data_manager import close_all_connections
            await close_all_connections()
            print("✅ Database connections closed")
        except Exception as e:
            print(f"⚠️ Error closing database connections: {e}")
    
    def _close_all_overlays(self):
        """Закриває всі спливаючі вікна в overlay"""
        if not self.page or not hasattr(self.page, 'overlay'):
            return
        
        try:
            # Закриваємо діалоги поточного view
            if hasattr(self, 'current_view') and self.current_view:
                if hasattr(self.current_view, '_close_all_dialogs'):
                    self.current_view._close_all_dialogs()
            
            for overlay_item in self.page.overlay[:]:
                if isinstance(overlay_item, ft.AlertDialog) and hasattr(overlay_item, 'open'):
                    try:
                        overlay_item.open = False
                    except Exception:
                        pass
                elif isinstance(overlay_item, ft.Container) and hasattr(overlay_item, 'visible'):
                    try:
                        if overlay_item.visible:
                            overlay_item.visible = False
                    except Exception:
                        pass
                # Закриваємо калькулятор якщо він відкритий
                elif hasattr(self, 'calculator_container') and overlay_item == self.calculator_container:
                    try:
                        if overlay_item.visible:
                            overlay_item.visible = False
                            if hasattr(self, 'calculator_overlay'):
                                self.calculator_overlay.visible = False
                    except Exception:
                        pass
            
            self.page.update()
        except Exception as e:
            print(f"Error closing overlays: {e}")
    
    def _restore_text_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # Відновлюємо фокус на поточному view
            if hasattr(self, 'current_view') and self.current_view:
                if hasattr(self.current_view, '_restore_focus'):
                    self.current_view._restore_focus()
                else:
                    # Fallback для view, які не мають _restore_focus
                    if self.page:
                        self.page.update()
        except Exception as e:
            print(f"Error restoring text focus: {e}")
    

    async def _on_language_change_update_ui(self, lang_code: str):
        if not hasattr(self, 'navigation_rail'): return
        self.navigation_rail.destinations[0].label = self.loc.get("nav_transactions")
        self.navigation_rail.destinations[1].label = self.loc.get("nav_properties")
        self.navigation_rail.destinations[2].label = self.loc.get("nav_analytics")
        self.lang_menu = self._build_lang_menu()
        if self.navigation_rail.trailing: self.navigation_rail.trailing.controls[-1] = self.lang_menu
        if self.navigation_rail.visible: self.navigation_rail.update()
        if hasattr(self, 'mini_profile_menu') and self.mini_profile_menu.visible:
            await self._update_mini_profile_menu_content()
        
        # Оновлюємо поточний view
        if hasattr(self, 'current_view') and self.current_view:
            if hasattr(self.current_view, '_on_lang_change'):
                await self.current_view._on_lang_change(lang_code)
        

    async def toggle_calculator_visibility(self, e, initial_value: str | None = None,
                                           on_done_callback: Callable | None = None):
        self.calculator_close_callback = on_done_callback
        self.calculator_view.show(initial_value)
        self.calculator_overlay.visible, self.calculator_container.visible = True, True
        self.page.update()
        await asyncio.sleep(0.01)
        self.calculator_overlay.opacity = 1
        self.calculator_container.right = 20
        self.page.update()

    async def close_calculator(self, e=None):
        if not self.calculator_container.visible:
            return
        if self.calculator_close_callback:
            await self.calculator_close_callback(self.calculator_view.get_result())
        self.calculator_overlay.opacity = 0
        self.calculator_container.right = -self.CALCULATOR_WIDTH
        self.page.update()
        await asyncio.sleep(self.CALCULATOR_ANIMATION_DURATION / 1000)
        self.calculator_overlay.visible = False
        self.calculator_container.visible = False
        self.calculator_close_callback = None
        self.page.update()

    # --- ЗМІНЕНО: Логіка працює з об'єктом профілю ---
    async def _on_profile_change_update_ui(self, profile_data: dict | None):
        if not profile_data:
            self.mini_profile_button.visible = False
            if self.page: self.page.update()
            return

        if profile_data.get('avatar_b64'):
            self.mini_profile_button_avatar.src_base64 = profile_data['avatar_b64'].split(',')[1]
            self.mini_profile_button_avatar.visible = True
            self.mini_profile_button_icon_container.visible = False
        else:
            self.mini_profile_button_avatar.visible = False
            self.mini_profile_button_icon_container.visible = True

        self.mini_profile_button.visible = True
        if self.mini_profile_button.page:
            self.mini_profile_button.update()

    async def toggle_mini_profile_menu(self, e):
        if self.mini_profile_menu.visible:
            self.mini_profile_menu.opacity, self.mini_profile_menu.scale = 0, ft.Scale(0.9)
            self.page.update()
            await asyncio.sleep(0.3)
            self.mini_profile_menu.visible = False
        else:
            await self._update_mini_profile_menu_content()
            self.mini_profile_menu.visible = True
            self.page.update()
            await asyncio.sleep(0.01)
            self.mini_profile_menu.opacity, self.mini_profile_menu.scale = 1, ft.Scale(1.0)
        self.page.update()

    async def _update_mini_profile_menu_content(self):
        # --- ЗМІНЕНО: Використовуємо кеш ---
        profiles = self.profile_list_cache
        menu_row = self.mini_profile_menu.content.controls[0]
        menu_row.controls.clear()
        for profile in profiles:
            menu_row.controls.append(self._create_mini_avatar(profile))
        menu_row.controls.append(ft.Column(controls=[
            ft.Container(width=60, height=60, shape=ft.BoxShape.CIRCLE, bgcolor=ft.Colors.WHITE24,
                         content=ft.Icon(ft.Icons.ADD, size=30, color=ft.Colors.GREY_50),
                         on_click=self._mini_add_profile),
            ft.Text(self.loc.get("profiles_add"), size=12, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, width=70))
        self.mini_profile_menu.update()

    def _create_mini_avatar(self, profile_data: dict):
        name = profile_data['name']
        if profile_data.get('avatar_b64'):
            avatar_content = ft.Image(src_base64=profile_data['avatar_b64'].split(',')[1], width=60, height=60,
                                      fit=ft.ImageFit.COVER, border_radius=30)
            bg_color = ft.Colors.TRANSPARENT
        else:
            avatar_content = ft.Icon(ft.Icons.PERSON_OUTLINE, size=30, color=ft.Colors.GREY_50)
            color_seed = sum(ord(c) for c in name)
            rand = random.Random(color_seed)
            bg_color = rand.choice([ft.Colors.BLUE_ACCENT_100, ft.Colors.GREEN_ACCENT_100, ft.Colors.RED_ACCENT_100,
                                    ft.Colors.PURPLE_ACCENT_100, ft.Colors.ORANGE_ACCENT_100,
                                    ft.Colors.TEAL_ACCENT_100])
        # --- ЗМІНЕНО: Передаємо весь об'єкт профілю в data ---
        avatar_circle = ft.Container(width=60, height=60, content=avatar_content, alignment=ft.alignment.center,
                                     shape=ft.BoxShape.CIRCLE, bgcolor=bg_color, data=profile_data,
                                     on_click=self._mini_select_profile, tooltip=name)
        return ft.Column(controls=[avatar_circle, ft.Text(name, size=12, weight=ft.FontWeight.W_500, no_wrap=True,
                                                          overflow=ft.TextOverflow.ELLIPSIS)],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, width=70)

    async def _mini_select_profile(self, e: ft.ControlEvent):
        # --- ЗМІНЕНО: Отримуємо весь об'єкт профілю ---
        new_profile_data = e.control.data
        await self.toggle_mini_profile_menu(e)

        current_profile_id = self.app_state.current_profile['id'] if self.app_state.current_profile else None
        if new_profile_data['id'] != current_profile_id:
            if self.profile_select_sound:
                self.profile_select_sound.play()
            self.main_content_container.opacity = 0
            self.main_content_container.update()
            await asyncio.sleep(0.25)
            self.app_state.current_profile = new_profile_data
            

            
            await asyncio.sleep(0.05)
            self.main_content_container.opacity = 1
            self.main_content_container.update()

    async def _mini_add_profile(self, e: ft.ControlEvent):
        await self.toggle_mini_profile_menu(e)
        await self.views["profiles"].open_create_profile_dialog(e)

    async def navigate(self, e: ft.ControlEvent | None = None, view_name: str | None = None):
        start_time = time.time() if OPTIMIZATION_ENABLED else 0
        logger.info(f"🧭 Navigate to: {view_name or 'default'}")
        try:
            # Додаємо анімацію переходу якщо доступна (працює в компільованій версії)
            if OPTIMIZATION_ENABLED and hasattr(self, 'animation_manager') and self.animation_manager is not None:
                try:
                    # Анімація fade out поточного view
                    for view in self.views.values():
                        if view.visible:
                            self.animation_manager.fade_out(view, duration=0.2)
                            await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"⚠️ Animation error: {e}")
            
            # Визначаємо який view показувати
            view_keys = list(self.views.keys())
            selected_index = self.navigation_rail.selected_index if self.navigation_rail else 0
            if e is not None and hasattr(e.control, 'selected_index') and e.control.selected_index is not None:
                selected_index = e.control.selected_index

            # Перевірка по view_name або по об'єкту
            is_profiles_view = (view_name == "profiles") or (view_name is None and self.app_state.current_profile is None)
            
            if view_name:
                key_to_show = view_name
            elif self.app_state.current_profile is None:
                key_to_show = "profiles"
            elif e is not None and hasattr(e.control, 'selected_index') and e.control.selected_index is not None:
                # Користувач клікнув на NavigationRail
                view_keys = ["transactions", "properties", "analytics"]
                if 0 <= e.control.selected_index < len(view_keys):
                    key_to_show = view_keys[e.control.selected_index]
                else:
                    key_to_show = "transactions"
            else:
                # Після вибору профілю за замовчуванням показуємо transactions
                key_to_show = "transactions"
            

            
            # Перевіряємо чи потрібно змінювати view
            current_active_view = None
            for key, view in self.views.items():
                if view is not None and hasattr(view, 'visible') and view.visible:
                    current_active_view = key
                    break
            
            # Якщо вже показуємо потрібний view, не робимо нічого
            if current_active_view == key_to_show:
                return
            
            # Безпечно встановлюємо видимість навігаційних елементів
            if self.navigation_rail is not None:
                self.navigation_rail.visible = not is_profiles_view
            if self.mini_profile_button is not None:
                self.mini_profile_button.visible = not is_profiles_view
            

            

                

            
            # Встановлюємо заголовок сторінки
            page_title = "Kalkor"
            if not is_profiles_view and self.app_state.current_profile:
                page_title = f"Kalkor - {self.app_state.current_profile['name']}"
            if self.page:
                self.page.title = page_title

            if not is_profiles_view and self.navigation_rail is not None: 
                self.navigation_rail.selected_index = selected_index
            
            # Обробляємо всі views
            for key, view in self.views.items():
                if view is None:
                    continue
                    
                is_active = (key == key_to_show)
                
                # Безпечно встановлюємо видимість
                try:
                    if (hasattr(view, 'visible') and 
                        view is not None and 
                        hasattr(view, '_set_attr_internal')):
                        view.visible = is_active
                        # Додатково встановлюємо opacity для неактивних views
                        if hasattr(view, 'opacity'):
                            view.opacity = 1.0 if is_active else 0.0
                except Exception as e:
                    logger.error(f"Error setting visibility for view {key}: {e}")
                    pass
                    
                # Пропускаємо неактивні views
                if not is_active:
                    continue
                    
                # Безпечно викликаємо on_view_hide для неактивних views
                if (not is_active and 
                    hasattr(view, 'on_view_hide') and 
                    view is not None and 
                    callable(getattr(view, 'on_view_hide', None))): 
                    try:
                        result = view.on_view_hide()
                        if hasattr(result, '__await__'):
                            await result
                    except Exception:
                        pass
            
            # Безпечно викликаємо on_view_show для активного view
            active_view = self.views.get(key_to_show)
            logger.info(f"Active view for {key_to_show}: {type(active_view).__name__ if active_view else 'None'}")
            if (active_view is not None and 
                hasattr(active_view, 'on_view_show') and 
                callable(getattr(active_view, 'on_view_show', None))): 
                try:
                    logger.info(f"Calling on_view_show for {key_to_show}")
                    await active_view.on_view_show()
                except Exception as ex:
                    logger.error(f"Error in on_view_show for {key_to_show}: {ex}")
                    pass
            
            # Додаємо анімацію fade in для нового view (працює в компільованій версії)
            if OPTIMIZATION_ENABLED and hasattr(self, 'animation_manager') and self.animation_manager is not None and active_view:
                try:
                    self.animation_manager.fade_in(active_view, duration=0.3)
                except Exception as e:
                    print(f"⚠️ Animation error: {e}")
            
            # Закриваємо калькулятор якщо він відкритий
            if hasattr(self, 'calculator_container') and self.calculator_container is not None and self.calculator_container.visible: 
                await self.close_calculator()
            
            # Безпечно закриваємо всі AlertDialog в overlay
            if self.page and hasattr(self.page, 'overlay'):
                for overlay_control in self.page.overlay:
                    if isinstance(overlay_control, ft.AlertDialog) and hasattr(overlay_control, 'open'):
                        try:
                            overlay_control.open = False
                        except Exception:
                            pass
                    # Додатково очищаємо всі Container з видимістю False
                    elif isinstance(overlay_control, ft.Container) and hasattr(overlay_control, 'visible'):
                        try:
                            if not overlay_control.visible:
                                overlay_control.opacity = 0.0
                        except Exception:
                            pass
            
            # Встановлюємо поточний view для оновлення локалізації
            self.current_view = active_view
            
            # Оновлюємо сторінку тільки один раз в кінці
            if self.page:
                self.page.update()
                
            # Записуємо метрики навігації
            if OPTIMIZATION_ENABLED:
                navigation_time = (time.time() - start_time) * 1000  # в мілісекундах
                record_ui_metric(f"navigate_{view_name or 'default'}", navigation_time, 0)
                
        except Exception as ex:
            logger.error(f"Error in navigate method: {ex}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            pass