import flet as ft
import base64
from typing import Callable, Optional, List
import asyncio
import os

from src.app.app_state import AppState
from src.data import data_manager as dm
from src.utils.localization import LocalizationManager
from src.utils import config as cfg
from src.utils.ui.helpers import (
    format_number, BaseDialog, SafeAsyncExecutor, 
    BUTTON_STYLE_PRIMARY, BUTTON_STYLE_SECONDARY, BUTTON_STYLE_DANGER,
    TEXT_FIELD_STYLE, create_loading_indicator, create_error_message
)
from src.utils.ui.date_picker import ModernDatePicker
from src.services.property_service import PropertyService, PropertyData
from src.utils.drag_drop_manager import DragDropManager
from src.views.base_view import BaseView

# Імпортуємо нові системи
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors
from src.utils.validators import DataValidator

# Імпорт lazy image loader
try:
    from src.utils.lazy_image_loader import get_image_loader
    LAZY_LOADER_ENABLED = True
except ImportError:
    LAZY_LOADER_ENABLED = False


logger = get_logger(__name__)


class PropertiesView(BaseView):
    """Modern Properties view: horizontal active list with DnD, sold list, add/edit/sell, totals, and transaction integration."""

    # Базові розміри карточок
    BASE_CARD_HEIGHT = 280
    BASE_CARD_WIDTH = 220
    BASE_IMG_WIDTH = 160
    GAP = 10
    
    # Поточні розміри (будуть розраховані адаптивно)
    CARD_HEIGHT = BASE_CARD_HEIGHT
    CARD_WIDTH = BASE_CARD_WIDTH
    IMG_WIDTH = BASE_IMG_WIDTH

    def __init__(self, app_state: AppState, loc: LocalizationManager):
        super().__init__(app_state, loc, visible=True, expand=True)
        self.selected_tab = "active"  # "active" | "sold"
        self._is_built = False
        self._update_lock = asyncio.Lock()
        
        # Реєструємо обробник зміни мови
        self.app_state.register_on_language_change(self._on_lang_change)
        
        # Ініціалізуємо сервіс для роботи з майном
        self.property_service = PropertyService(dm)
        
        # Ініціалізуємо DragDropManager (page буде встановлено пізніше)
        self.drag_drop_manager: Optional[DragDropManager] = None
        
        # Ініціалізуємо нові системи
        self.validator = DataValidator()
        logger.info("PropertiesView initialized with new systems")


        # Overlay/dialog controls
        self.file_picker: Optional[ft.FilePicker] = None
        self.add_edit_dialog: Optional[ft.AlertDialog] = None
        self.sell_dialog: Optional[ft.AlertDialog] = None
        self.confirm_dialog: Optional[ft.AlertDialog] = None

        # Add/edit form state
        self.editing_property_id: Optional[int] = None
        self.current_image_b64: Optional[str] = None
        self.input_name: Optional[ft.TextField] = None
        self.input_price: Optional[ft.TextField] = None
        self.preview_image: Optional[ft.Image] = None

        # Sell form state
        self.sell_price_input: Optional[ft.TextField] = None
        self.sell_notes_input: Optional[ft.TextField] = None

        # Main view controls
        self.main_property_view: Optional[ft.Column] = None
        self.list_container: Optional[ft.Container] = None
        self.total_label: Optional[ft.Text] = None
        self.total_value: Optional[ft.Text] = None
        self.tabs_row: Optional[ft.Container] = None
        self.btn_tab_active: Optional[ft.OutlinedButton] = None
        self.btn_tab_sold: Optional[ft.OutlinedButton] = None
        self.add_button: Optional[ft.ElevatedButton] = None

        # Subscriptions
        self.app_state.register_on_profile_change(self.handle_profile_change)
        self.app_state.register_on_language_change(self._on_lang_change)

        # Додаємо обробку подій зміни розміру вікна для очищення overlay
        self._setup_window_event_handlers()

    def _setup_window_event_handlers(self):
        """Налаштовує обробники подій вікна"""
        if self.page and hasattr(self.page, 'on_resize'):
            self.page.on_resize = self._handle_window_resize

    def _handle_window_resize(self, e):
        """Обробляє зміну розміру вікна"""
        try:
            self._calculate_adaptive_sizes(e.width, e.height)
            self._simple_overlay_cleanup()
        except Exception as e:
            logger.error(f"Error in window resize handler: {e}")

    def _calculate_adaptive_sizes(self, window_width: int, window_height: int):
        """Розраховує адаптивні розміри карточок на основі розміру вікна"""
        try:
            # Базові розміри для різних розмірів екрану
            if window_width < 800:  # Маленький екран
                scale_factor = 0.8
            elif window_width < 1200:  # Середній екран
                scale_factor = 1.0
            elif window_width < 1600:  # Великий екран
                scale_factor = 1.1
            else:  # Дуже великий екран
                scale_factor = 1.2
            
            # Розраховуємо нові розміри
            self.CARD_WIDTH = int(self.BASE_CARD_WIDTH * scale_factor)
            self.CARD_HEIGHT = int(self.BASE_CARD_HEIGHT * scale_factor)
            self.IMG_WIDTH = int(self.BASE_IMG_WIDTH * scale_factor)
            
        except Exception as e:
            logger.error(f"Error calculating adaptive sizes: {e}")
            # Використовуємо базові розміри як fallback
            self.CARD_WIDTH = self.BASE_CARD_WIDTH
            self.CARD_HEIGHT = self.BASE_CARD_HEIGHT
            self.IMG_WIDTH = self.BASE_IMG_WIDTH

    async def on_view_show(self):
        try:
            logger.info("PropertiesView on_view_show called")
            if self is None:
                logger.warning("PropertiesView is None")
                return
            # Перевіряємо чи маємо необхідні атрибути
            if not hasattr(self, '_set_attr_internal'):
                logger.error("PropertiesView missing _set_attr_internal attribute")
                return
                
            # Примусово будуємо UI кожного разу
            logger.info(f"PropertiesView _is_built: {self._is_built}")
            self._build_ui()
            self.controls.clear()
            self.controls.append(self.main_property_view)
            self._is_built = True
            logger.info("PropertiesView UI built successfully")
            
            # Примусово показуємо PropertiesView
            self.visible = True
            if hasattr(self, 'main_property_view'):
                self.main_property_view.visible = True
                logger.info(f"PropertiesView visible: {self.visible}, main_property_view visible: {self.main_property_view.visible}")

            # Розраховуємо адаптивні розміри при першому показі
            if self.page and hasattr(self.page, 'width') and hasattr(self.page, 'height'):
                self._calculate_adaptive_sizes(self.page.width, self.page.height)
            
            # Оновлюємо сторінку
            if self.page:
                self.page.update()

            # Перевіряємо та ініціалізуємо drag_drop_manager якщо потрібно
            if not self.drag_drop_manager and self.page:
                try:
                    self.drag_drop_manager = DragDropManager(self.page)
                except Exception as e:
            
                    self.drag_drop_manager = None

            # Безпечно очищаємо overlay при показі view (профілактика)
            try:
                if hasattr(self, '_simple_overlay_cleanup'):
                    self._simple_overlay_cleanup()
            except Exception:
                # Emergency cleanup
                try:
                    if self.page and hasattr(self.page, 'overlay'):
                        for overlay_item in self.page.overlay[:]:
                            if hasattr(overlay_item, 'visible') and overlay_item.visible:
                                try:
                                    overlay_item.visible = False
                                except Exception:
                                    pass
                except Exception:
                    pass

            # Додаємо file_picker тільки якщо потрібно
            if self.page and hasattr(self, 'file_picker') and self.file_picker is not None and self.file_picker not in self.page.overlay:
                self.page.overlay.append(self.file_picker)

            # Перевіряємо чи дані вже завантажені (попереднє завантаження)
            if not hasattr(self, '_data_preloaded') or not self._data_preloaded:
                # Виконуємо handle_profile_change тільки якщо дані ще не завантажені
                if self.page and self.app_state.current_profile:
                    print(f"🔍 First load: calling handle_profile_change for profile {self.app_state.current_profile.get('id')}")
                    await self.handle_profile_change(self.app_state.current_profile)
                    # Після завантаження даних примусово оновлюємо UI
                    print(f"🔍 First load: forcing UI refresh after data load")
                    await self._refresh_list(show_loading=False, force_refresh=True, skip_ui_update=False)
            else:
                # Дані вже завантажені, оновлюємо UI з кешованими даними
                if self.page:
                    await self._refresh_list(show_loading=False, force_refresh=False, skip_ui_update=False)
                self._data_preloaded = False  # Скидаємо флаг для наступного разу
                
            # Відновлюємо opacity при показі view
            if hasattr(self, 'opacity'):
                self.opacity = 1.0
            logger.info("PropertiesView on_view_show completed successfully")
        except Exception as e:
            # Fallback: спробуємо хоча б показати базовий UI
            try:
                if not self._is_built and self.page:
                    self._build_ui()
                    self.controls.clear()
                    self.controls.append(self.main_property_view)
                    self._is_built = True
                    if self.page and hasattr(self.page, 'update'):
                        self.page.update()
            except Exception:
                pass

    def set_page(self, page: ft.Page):
        """Встановлює page для PropertiesView"""
        if page is None:
    
            return
            
        self.page = page
        # Ініціалізуємо DragDropManager з page
        try:
            self.drag_drop_manager = DragDropManager(page)
        except Exception as e:
    
            self.drag_drop_manager = None

    def cleanup_resources(self):
        """Очищає ресурси PropertiesView"""
        try:
            # Очищаємо drag & drop ресурси
            if self.drag_drop_manager:
                self.drag_drop_manager.cleanup_all()
            
            # Очищаємо кеш
            if hasattr(self, '_active_props_cache'):
                self._active_props_cache.clear()
            
            # Очищаємо посилання на картки
            if hasattr(self, '_active_cards_row'):
                self._active_cards_row = None
            if hasattr(self, '_sold_cards_row'):
                self._sold_cards_row = None
        except Exception:
            pass

    async def on_view_hide(self):
        """Викликається при приховуванні view"""
        try:
            # Викликаємо базовий метод
            await super().on_view_hide()
            
            # Очищаємо ресурси
            self.cleanup_resources()
                    
            # Очищаємо overlay елементи
            if self.page and hasattr(self.page, 'overlay'):
                try:
                    for overlay_item in self.page.overlay[:]:
                        if (isinstance(overlay_item, ft.Container) and 
                            hasattr(overlay_item, 'visible') and 
                            overlay_item.visible):
                            overlay_item.visible = False
                            if hasattr(overlay_item, 'opacity'):
                                overlay_item.opacity = 0.0
                except Exception:
                    pass
        except Exception:
            pass


    def _build_ui(self):
        self.file_picker = ft.FilePicker(on_result=self._on_file_pick)

        self.main_property_view = ft.Column(visible=True, expand=True, spacing=20)

        # Header з покращеним дизайном
        self.total_label = ft.Text(
            self.loc.get("properties_total_value", default="Загальна вартість:"),
            size=16,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.GREY_600
        )
        self.total_value = ft.Text(
            "0", 
            weight=ft.FontWeight.BOLD,
            size=20,
            color=ft.Colors.GREEN_600
        )
        self.total_row = ft.Row(
            [self.total_label, self.total_value],
            alignment=ft.MainAxisAlignment.END,
            spacing=8,
        )



        # Сучасні таби з динамічною шириною для різних мов
        self.btn_tab_active = ft.Container(
            content=ft.Text(
                self.loc.get("properties_tabs_active", default="Активне"),
                size=16,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.WHITE,
                text_align=ft.TextAlign.CENTER,
            ),
            on_click=lambda e: self._switch_tab_async("active"),
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
            bgcolor=ft.Colors.BLUE_600,
            border_radius=ft.border_radius.only(top_left=12, bottom_left=12),
            width=140,  # Збільшено для російської мови
            alignment=ft.alignment.center,
        )
        self.btn_tab_sold = ft.Container(
            content=ft.Text(
                self.loc.get("properties_tabs_sold", default="Продане"),
                size=16,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.GREY_400,
                text_align=ft.TextAlign.CENTER,
            ),
            on_click=lambda e: self._switch_tab_async("sold"),
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
            bgcolor=ft.Colors.GREY_800,
            border_radius=ft.border_radius.only(top_right=12, bottom_right=12),
            width=140,  # Збільшено для російської мови
            alignment=ft.alignment.center,
        )
        self.tabs_container = ft.Container(
            content=ft.Row([self.btn_tab_active, self.btn_tab_sold], spacing=0),
            bgcolor=ft.Colors.GREY_900,
            border_radius=12,
            padding=ft.padding.all(4),
            margin=ft.margin.only(top=4),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)
            )
        )

        self.list_container = ft.Container(expand=True)

        # Створюємо кнопку додавання (тимчасово видалена з UI)
        self.add_button = ft.ElevatedButton(
            text=self.loc.get("properties_add_new", default="Додати майно"),
            icon=ft.Icons.ADD_CIRCLE,
            on_click=self._open_add_dialog,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE_600,
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=12),
                elevation=2,
            ),
            visible=True,  # Повертаємо кнопку в UI
        )

        # Створюємо динамічний header
        self.header_row = ft.Row(
            controls=[
                ft.Container(expand=True),  # Лівий відступ
                self.tabs_container,  # Таби в контейнері
                ft.Container(expand=True),  # Правий відступ
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # Створюємо окрему кнопку для під табами
        self.add_button_below = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE, size=20),
                ft.Text(
                    self.loc.get("properties_add_new", default="Додати нове майно"),
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                    size=14
                )
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            on_click=self._on_add_button_click,
            bgcolor=ft.Colors.BLUE_600,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=12),
                elevation=2,
            ),
            visible=True,  # Показуємо кнопку
        )
        
        # Створюємо рядок для кнопки додавання під табами
        self.add_button_row = ft.Row([
            ft.Container(expand=True),
            self.add_button_below,
            ft.Container(expand=True)
        ], alignment=ft.MainAxisAlignment.CENTER)
        self.add_button_row.visible = True  # Показуємо кнопку



        # Створюємо красивий заголовок сторінки
        self.page_title_text = ft.Text(
            self.loc.get("properties_title", default="Майно"),
            size=28,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        self.page_title = ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.DIAMOND_OUTLINED,
                    size=32,
                    color=ft.Colors.BLUE_400
                ),
                self.page_title_text
            ], spacing=12, alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.only(bottom=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.BLUE_400))
        )

        # Створюємо основний контент без фону (фон буде глобальним)
        main_content = ft.Column([
            self.page_title,
            self.header_row,
            self.add_button_row,  # Повертаємо рядок з кнопкою
            self.list_container
        ], spacing=20, expand=True)
        

        
        self.main_property_view.controls.clear()
        self.main_property_view.controls.append(main_content)
        
        # Оновлюємо header для поточної вкладки
        self._update_header_for_tab()
        
        # Оновлюємо стилі табів
        self._apply_tab_styles()
        
        # Оновлюємо позицію кнопки додавання
        self._update_add_button_position()

    def _update_add_button_position(self):
        """Оновлює позицію кнопки додавання залежно від стану"""
        if not hasattr(self, 'add_button') or self.add_button is None:
            logger.warning("🔧 No add_button found")
            return
            
        # Показуємо кнопку тільки для активного таба
        if self.selected_tab != "active":
            logger.info(f"🔧 Button hidden - not on active tab: {self.selected_tab}")
            self.add_button.visible = False
            if hasattr(self, 'add_button_below'):
                self.add_button_below.visible = False
            if hasattr(self, 'add_button_row'):
                self.add_button_row.visible = False
            return
            
        # Перевіряємо чи є активне майно
        has_active_properties = (hasattr(self, '_active_props_cache') and 
                               self._active_props_cache and 
                               len(self._active_props_cache) > 0)
        
        logger.info(f"🔧 Updating button position: has_properties={has_active_properties}, tab={self.selected_tab}")
        logger.info(f"🔧 Cache state: has_cache={hasattr(self, '_active_props_cache')}, cache_length={len(self._active_props_cache) if hasattr(self, '_active_props_cache') and self._active_props_cache else 0}")
        
        if has_active_properties:
            # Є майно - кнопка біля "Активне майно" (в заголовку секції)
            logger.info("🔧 Showing button in header (near 'Активне майно')")
            self._show_button_in_header()
        else:
            # Немає майна - кнопка під табами
            logger.info("🔧 Showing button below tabs")
            self._show_button_below_tabs()

    def _show_button_in_header(self):
        """Показує кнопку в заголовку секції (біля 'Активне майно')"""
        logger.info("🔧 _show_button_in_header called")
        
        # Приховуємо рядок з кнопкою під табами
        if hasattr(self, 'add_button_row'):
            self.add_button_row.visible = False
            logger.info("🔧 Hidden add_button_row")
            
        # Приховуємо кнопку під табами
        if hasattr(self, 'add_button_below'):
            self.add_button_below.visible = False
            logger.info("🔧 Hidden add_button_below")
            
        # Кнопка вже є в заголовку секції (біля "Активне майно"), просто показуємо її
        self.add_button.visible = True
        logger.info(f"🔧 Button visible set to: {self.add_button.visible}")

    def _show_button_below_tabs(self):
        """Показує кнопку під табами"""
        logger.info("🔧 _show_button_below_tabs called")
        
        # Приховуємо кнопку в заголовку секції
        self.add_button.visible = False
        logger.info("🔧 Hidden add_button in header")
        
        # Показуємо кнопку під табами
        if hasattr(self, 'add_button_below'):
            self.add_button_below.visible = True
            logger.info(f"🔧 add_button_below visible set to: {self.add_button_below.visible}")
            
        # Показуємо рядок з кнопкою під табами
        if hasattr(self, 'add_button_row'):
            self.add_button_row.visible = True
            logger.info(f"🔧 add_button_row visible set to: {self.add_button_row.visible}")

    def _on_add_button_click(self, e):
        """Обробник кліку на кнопку додавання майна"""
        try:
            # Використовуємо threading для виклику асинхронного методу
            import threading
            def run_async():
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._open_property_overlay("add"))
                    loop.close()
                except Exception as ex:
                    logger.error(f"❌ Error in async thread: {ex}")
            
            thread = threading.Thread(target=run_async, daemon=True)
            thread.start()
        except Exception as ex:
            logger.error(f"❌ Error opening property overlay: {ex}")
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(self.loc.get("properties_error_open_dialog", "Помилка відкриття діалогу додавання майна")),
                        bgcolor=ft.Colors.RED_600
                    )
                )

    def _apply_tab_styles(self):
        is_active = self.selected_tab == "active"
        if self.btn_tab_active and self.btn_tab_sold:
            # Активний таб
            self.btn_tab_active.bgcolor = ft.Colors.BLUE_600 if is_active else ft.Colors.GREY_800
            self.btn_tab_active.content.color = ft.Colors.WHITE if is_active else ft.Colors.GREY_400
            self.btn_tab_active.border_radius = ft.border_radius.only(top_left=8, bottom_left=8) if is_active else ft.border_radius.only(top_left=8, bottom_left=8)
            
            # Неактивний таб
            self.btn_tab_sold.bgcolor = ft.Colors.BLUE_600 if not is_active else ft.Colors.GREY_800
            self.btn_tab_sold.content.color = ft.Colors.WHITE if not is_active else ft.Colors.GREY_400
            self.btn_tab_sold.border_radius = ft.border_radius.only(top_right=8, bottom_right=8) if not is_active else ft.border_radius.only(top_right=8, bottom_right=8)
        


    async def handle_profile_change(self, profile_data: Optional[dict]):
        has_profile = bool(profile_data)
        if has_profile:
            # Виконуємо switch_tab синхронно для швидшого завантаження
            # Якщо сторінка не видима, не оновлюємо UI
            await self.switch_tab("active", from_profile_change=True, force=True, skip_ui_update=not self.visible)
            # Встановлюємо флаг попереднього завантаження
            self._data_preloaded = True
        # UI оновлюється в switch_tab -> _refresh_list, тому не робимо додаткового оновлення

    def _switch_tab_async(self, new_tab: str):
        if self.page:
            self.page.run_task(self.switch_tab, new_tab)

    async def switch_tab(self, new_tab: str, from_profile_change: bool = False, force: bool = False, skip_ui_update: bool = False):
        if new_tab not in {"active", "sold"}:
            return
        if new_tab == self.selected_tab and not force:
            return
        async with self._update_lock:
            self.selected_tab = new_tab
            self._update_header_for_tab()
            self._update_add_button_position()
            
            # Оновлюємо стилі табів
            self._apply_tab_styles()
            
            # Прибираємо показ завантаження при переключенні табів
            # show_loading = (new_tab == "active" and force)
            await self._refresh_list(show_loading=False, force_refresh=force, skip_ui_update=skip_ui_update)
            
            # UI оновлюється в _refresh_list, тому не робимо додаткового оновлення

    async def _refresh_list(self, show_loading: bool = True, use_cache: bool = False, force_refresh: bool = False, skip_ui_update: bool = False):
        """Оновлює список майна.
        show_loading: показувати індикатор під час завантаження (True за замовчуванням)
        use_cache: використовувати локальний кеш без походу в БД (для реордеру)
        force_refresh: завжди завантажувати з БД (для повернення майна)
        skip_ui_update: пропустити оновлення UI (для попереднього завантаження)
        """
        # Захист від повторних викликів
        if hasattr(self, '_refreshing') and self._refreshing:
            return
        
        self._refreshing = True
        
        try:
            profile = self.app_state.current_profile
            if not profile:
                return
        
            # Перевіряємо чи дані вже завантажені і сторінка видима
            if hasattr(self, '_data_preloaded') and self._data_preloaded and self.visible and not force_refresh:

                # Дані завантажені, але потрібно оновити UI
                if self.list_container and hasattr(self, '_active_props_cache'):
                    status = "active" if self.selected_tab == "active" else "sold"
                    props = self._active_props_cache if status == "active" else []
                    
                    # Будуємо контент з кешованих даних
                    content = (
                        await self._build_active_list(props) if status == "active" 
                        else self._build_sold_list(props)
                    )
                    
                    # Оновлюємо контент
                    if self.list_container.content != content:
                        self.list_container.content = content
                    
                    # Оновлюємо UI
                    if self.page and not skip_ui_update:
                        self.page.update()
            
                return
            
            # Ensure UI controls exist
            if not self.list_container or not self.main_property_view:
                self._build_ui()

            status = "active" if self.selected_tab == "active" else "sold"
            
            # Завантажуємо майно та підсумок паралельно для швидшого завантаження
            if use_cache and not force_refresh and status == "active" and hasattr(self, "_active_props_cache"):
                print(f"🔍 Using cache: {len(self._active_props_cache)} items")
                props = list(self._active_props_cache)
                summary = None
            else:
                print(f"🔍 Loading from DB: force_refresh={force_refresh}, use_cache={use_cache}, status={status}")
                # Завантажуємо дані паралельно
                props_task = SafeAsyncExecutor.execute(
                    self.property_service.get_properties, 
                    profile["id"], 
                    status
                )
                
                summary_task = None
                if not use_cache or force_refresh:
                    summary_task = SafeAsyncExecutor.execute(
                        self.property_service.get_property_summary,
                        profile["id"]
                    )
                
                # Чекаємо на завершення обох задач
                props = await props_task
                summary = await summary_task if summary_task else None
                
                logger.info(f"🔄 Properties loaded: count={len(props) if props else 0}, status={status}")
                
                if status == "active":
                    self._active_props_cache = list(props)
                    logger.info(f"🔄 Active cache updated: length={len(self._active_props_cache)}")
                    try:
                        self._current_active_ids = [int(p.get("id")) for p in props if p.get("id") is not None]
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to convert property IDs to int: {e}")
                        self._current_active_ids = [p.get("id") for p in props if p.get("id") is not None]
                    
                    # Оновлюємо позицію кнопки після оновлення кешу
                    self._update_add_button_position()

            # Оновлюємо загальну вартість
            if self.total_value:
                if summary:
                    if status == "active":
                        self.total_value.value = format_number(summary["active_total"])
                    else:
                        self.total_value.value = format_number(summary["sold_total"])
                else:
                    self.total_value.value = "0"

            # Будуємо контент
            content = (
                await self._build_active_list(props) if status == "active" 
                else self._build_sold_list(props)
            )
            
            # Оновлюємо контент тільки якщо він змінився
            if self.list_container:
                print(f"🔍 Updating list_container content: has_container={bool(self.list_container)}, content_changed={self.list_container.content != content}")
                self.list_container.content = content
                print(f"🔍 Content updated successfully")
                
                # Оновлюємо header після зміни контенту
                if status == "active":
                    self._update_header_for_tab()
                
        except Exception as e:
            logger.error(f"Error refreshing property list: {e}")
            if self.list_container:
                self.list_container.content = create_error_message(
                    f"{self.loc.get('properties_errors_loading', default='Помилка завантаження:')} {str(e)}"
                )
        finally:
            self._refreshing = False
            # Оновлюємо header після завершення оновлення
            if self.selected_tab == "active":
                self._update_header_for_tab()
            # Оновлюємо UI тільки один раз після всіх змін, якщо не пропускаємо оновлення
            if self.page and not skip_ui_update:
                self.page.update()

    async def _build_active_list(self, props: List[dict]) -> ft.Control:
        print(f"🔍 _build_active_list called with {len(props) if props else 0} properties")
        # Зберігаємо кеш для швидкого оновлення без блимання
        self._active_props_cache = list(props)

        # Якщо немає майна, показуємо placeholder
        if not props:
            try:
                self._current_active_ids = []
            except Exception:
                self._current_active_ids = []
            
            return self._placeholder(
                self.loc.get("properties_list_empty", default="Список майна порожній.\nНатисніть 'Додати майно' щоб почати.")
            )

        try:
            self._current_active_ids = [int(p.get("id")) for p in props]
        except Exception:
            self._current_active_ids = [p.get("id") for p in props]

        # Створюємо сучасний dashboard для активного майна
        dashboard = self._build_active_dashboard(props)
        
        return dashboard

    def _build_sold_list(self, props: List[dict]) -> ft.Control:
        print(f"🔍 _build_sold_list called with {len(props) if props else 0} properties")
        if not props:
            return self._placeholder(
                self.loc.get("properties_list_empty_sold", default="У вас ще немає проданого майна.")
            )
        
        # Створюємо сучасний dashboard
        return self._build_sold_dashboard(props)

    def _create_draggable_card(self, card_content: ft.Control, prop_id: int, group_name: str, swap_callback, card_width: int = None, card_height: int = None) -> ft.DragTarget:
        """Створює draggable картку використовуючи DragDropManager"""
        if not self.drag_drop_manager:
            return ft.Container(content=card_content)
        
        width = card_width or self.CARD_WIDTH
        height = card_height or self.CARD_HEIGHT
        
        return self.drag_drop_manager.create_draggable_card(
            card_content=card_content,
            item_id=prop_id,
            group_name=group_name,
            swap_callback=swap_callback,
            card_width=width,
            card_height=height
        )

    def _create_form_divider(self) -> ft.Container:
        """Створює розділювач для форм"""
        return ft.Container(
            content=ft.Divider(
                height=1,
                color=ft.Colors.WHITE24,
                thickness=1
            ),
            margin=ft.margin.symmetric(vertical=20)
        )
    
    def _create_cards_row(self, cards: List[ft.DragTarget], spacing: int = 12) -> ft.Row:
        """
        Створює рядок з draggable картками
        """
        print(f"🔍 _create_cards_row called with {len(cards)} cards, drag_drop_manager={bool(self.drag_drop_manager)}")
        if not self.drag_drop_manager:
            logger.error("❌ DragDropManager not initialized")
            return ft.Row(cards, spacing=spacing)
        
        result = self.drag_drop_manager.create_draggable_row(cards, spacing)
        print(f"🔍 _create_cards_row created row with {len(result.controls) if hasattr(result, 'controls') else 'unknown'} controls")
        return result

    def _active_card_body(self, prop: dict) -> ft.Container:
        """Створює тіло картки для активного майна"""
        image_b64 = prop.get("image_b64")
        name = prop.get("name", "")
        price = prop.get("price", 0)

        # Красива картинка з покращеним дизайном
        if image_b64 and image_b64.strip() and "," in image_b64:
            img = ft.Container(
                content=ft.Image(
                    src_base64=image_b64.split(",")[1],
                    width=self.CARD_WIDTH - 20, 
                    height=140, 
                    fit=ft.ImageFit.COVER,
                ),
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        elif image_b64 and image_b64.strip():
            img = ft.Container(
                content=ft.Image(
                    src=image_b64, 
                    width=self.CARD_WIDTH - 20, 
                    height=140, 
                    fit=ft.ImageFit.COVER,
                ),
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        else:
            img = ft.Container(
                width=self.CARD_WIDTH - 20, 
                height=140, 
                bgcolor=ft.Colors.GREY_800,
                border_radius=12,
                content=ft.Column([
                    ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.GREY_400, size=40),
                    ft.Text(self.loc.get("properties_image_no_photo", default="Немає фото"), size=12, color=ft.Colors.GREY_500)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                alignment=ft.alignment.center,
                border=ft.border.all(1, ft.Colors.GREY_600)
            )

        # Покращений заголовок
        title = ft.Text(
            name, 
            weight=ft.FontWeight.BOLD, 
            size=16, 
            no_wrap=True, 
            overflow=ft.TextOverflow.ELLIPSIS,
            color=ft.Colors.GREY_800
        )
        
        # Красива ціна з іконкою без контейнера
        price_text = ft.Row([
            ft.Icon(ft.Icons.ATTACH_MONEY, color=ft.Colors.GREEN_600, size=16),
            ft.Text(
                f"{int(price):,}".replace(",", " "), 
                color=ft.Colors.GREEN_600, 
                size=18,
                weight=ft.FontWeight.BOLD
            )
        ], spacing=4)
        
        # Дата покупки (спочатку пробуємо purchase_date, потім fallback на created_timestamp)
        purchase_dt = prop.get("purchase_date", "")
        if not purchase_dt:
            purchase_dt = prop.get("created_timestamp", "")
            
        if purchase_dt and isinstance(purchase_dt, str):
            try:
                # Конвертуємо ISO формат в читабельний
                from datetime import datetime
                dt_obj = datetime.fromisoformat(purchase_dt.replace('Z', '+00:00'))
                formatted_date = dt_obj.strftime("%d.%m.%Y")
            except:
                formatted_date = purchase_dt[:10] if len(purchase_dt) >= 10 else purchase_dt
        else:
            formatted_date = self.loc.get("properties_misc_unknown", default="Невідомо")
            
        date_text = ft.Row([
            ft.Icon(ft.Icons.CALENDAR_TODAY, color=ft.Colors.GREY_500, size=14),
            ft.Text(
                f"{self.loc.get('properties_misc_purchase_date', default='Куплено:')} {formatted_date}",
                color=ft.Colors.GREY_500,
                size=12
            )
        ], spacing=4)
        
        # Компактні кнопки дій справа вертикально
        actions = ft.Column([
            ft.IconButton(
                icon=ft.Icons.SELL_OUTLINED, 
                tooltip=self.loc.get("properties_actions_sell", default="Продати"),
                on_click=lambda e, p=prop: self._open_sell_dialog_async(p), 
                icon_size=16,
                icon_color=ft.Colors.GREEN_600,  # Зелений як форма продажу
            ),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED, 
                tooltip=self.loc.get("properties_actions_edit", default="Редагувати"),
                on_click=lambda e, p=prop: self._open_edit_dialog_async(p), 
                icon_size=16,
                icon_color=ft.Colors.AMBER_600,  # Оранжевий як форма редагування
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_FOREVER, 
                tooltip=self.loc.get("properties_actions_delete", default="Видалити"),
                on_click=lambda e, p=prop: self._confirm_delete_async(p, False), 
                icon_size=16,
                icon_color=ft.Colors.RED_600,
            )
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Основний контент зліва
        left_content = ft.Column([
            img, 
            ft.Container(height=12),  # Відступ
            title, 
            ft.Container(height=8),   # Відступ
            price_text, 
            ft.Container(height=6),   # Відступ
            date_text,  # Дата додавання
            ft.Container(height=8),   # Додатковий відступ після дати
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START, expand=True)

        # Нижній рядок з кнопками справа
        bottom_row = ft.Row([
            ft.Container(expand=True),  # Розтягуємо простір зліва
            actions  # Кнопки справа
        ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Основний контент
        content_col = ft.Column([
            left_content,  # Основний контент
            ft.Container(height=16),  # Збільшений відступ
            bottom_row  # Кнопки внизу справа
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START)
        
        # Створюємо картку для активного майна (без сірого фільтра)
        card_container = ft.Container(
            content=content_col,
            width=self.CARD_WIDTH,
            height=self.CARD_HEIGHT,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            border_radius=16,
            padding=ft.padding.all(10),
            border=ft.border.all(1, ft.Colors.GREY_700),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
        )
        
        return card_container

    def _modern_sold_card(self, prop: dict) -> ft.Container:
        """Створює сучасну картку для проданого майна з такою ж структурою, як активне"""
        
        image_b64 = prop.get("image_b64")
        name = prop.get("name", "")
        purchase_price = float(prop.get("price", 0))
        selling_price = float(prop.get("selling_price", 0))
        sold_dt = prop.get("sold_timestamp", "")
        profit = selling_price - purchase_price
        roi = (profit / purchase_price * 100) if purchase_price > 0 else 0
        
        # Визначаємо колір залежно від результату
        if profit > 0:
            result_color = ft.Colors.GREEN_600
            result_bg = ft.Colors.GREEN_900
            result_icon = ft.Icons.TRENDING_UP
        else:
            result_color = ft.Colors.RED_600
            result_bg = ft.Colors.RED_900
            result_icon = ft.Icons.TRENDING_DOWN

        # Красива картинка з покращеним дизайном (сіра для проданого майна)
        if image_b64 and "," in image_b64:
            img = ft.Container(
                content=ft.Image(
                    src_base64=image_b64.split(",")[1],
                    width=self.CARD_WIDTH - 20, 
                    height=140, 
                    fit=ft.ImageFit.COVER,
                    color=ft.Colors.GREY_400,
                    color_blend_mode=ft.BlendMode.SATURATION,
                ),
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        elif image_b64:
            img = ft.Container(
                content=ft.Image(
                    src=image_b64, 
                    width=self.CARD_WIDTH - 20, 
                    height=140, 
                    fit=ft.ImageFit.COVER,
                    color=ft.Colors.GREY_400,
                    color_blend_mode=ft.BlendMode.SATURATION,
                ),
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        else:
            img = ft.Container(
                width=self.CARD_WIDTH - 20, 
                height=140, 
                bgcolor=ft.Colors.GREY_800,
                border_radius=12,
                content=ft.Column([
                    ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.GREY_400, size=40),
                    ft.Text(self.loc.get("properties_image_no_photo", default="Немає фото"), size=12, color=ft.Colors.GREY_500)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                alignment=ft.alignment.center,
                border=ft.border.all(1, ft.Colors.GREY_600)
            )

        # Покращений заголовок
        title = ft.Text(
            name, 
            weight=ft.FontWeight.BOLD, 
            size=16, 
            no_wrap=True, 
            overflow=ft.TextOverflow.ELLIPSIS,
            color=ft.Colors.GREY_800
        )
        
        # Красива ціна продажу з іконкою
        price_text = ft.Row([
            ft.Icon(ft.Icons.ATTACH_MONEY, color=ft.Colors.GREEN_600, size=16),
            ft.Text(
                f"{int(selling_price):,}".replace(",", " "), 
                color=ft.Colors.GREEN_600, 
                size=18,
                weight=ft.FontWeight.BOLD
            )
        ], spacing=4)
        
        # Інформація про прибуток внизу картки (ширша і ближче до кнопок)
        profit_info = ft.Container(
            content=ft.Row([
                ft.Icon(result_icon, color=ft.Colors.WHITE, size=14),
                ft.Text(
                    f"{format_number(profit)} ({roi:.1f}%)",
                    color=ft.Colors.WHITE,
                    size=12,
                    weight=ft.FontWeight.BOLD
                )
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=result_bg,
            border_radius=6,
            margin=ft.margin.only(top=4, right=8),  # Відступ справа для кнопок
            width=160  # Збільшена ширина
        )
        
        # Кнопки дій (повернення над видаленням)
        actions = ft.Column([
            # Кнопка повернення в активне
            ft.IconButton(
                icon=ft.Icons.UNDO, 
                tooltip=self.loc.get("properties_restore_restore_to_active", default="Повернути в активне"),
                on_click=lambda e, p=prop: self._handle_restore_click(p), 
                icon_size=16,
                icon_color=ft.Colors.BLUE_600,
            ),
            # Кнопка видалення
            ft.IconButton(
                icon=ft.Icons.DELETE_FOREVER, 
                tooltip=self.loc.get("properties_restore_delete_forever", default="Видалити назавжди"),
                on_click=lambda e, p=prop: self._confirm_delete_async(p, True), 
                icon_size=16,
                icon_color=ft.Colors.RED_600,
            )
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Основний контент зліва
        left_content = ft.Column([
            img, 
            ft.Container(height=12),  # Відступ
            title, 
            ft.Container(height=8),   # Відступ
            price_text, 
            ft.Container(height=6),   # Відступ
            profit_info,  # Інформація про прибуток
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START, expand=True)

        # Нижній рядок з кнопками справа
        bottom_row = ft.Row([
            ft.Container(expand=True),  # Розтягуємо простір зліва
            actions  # Кнопки справа
        ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Основний контент
        content_col = ft.Column([
            left_content,  # Основний контент
            ft.Container(height=16),  # Відступ
            bottom_row  # Кнопки внизу справа
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START)
        
        # Створюємо картку з сірим фільтром та інтерактивністю
        card_container = ft.Container(
            content=content_col,
            width=self.CARD_WIDTH,
            height=self.CARD_HEIGHT,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            border_radius=16,
            padding=ft.padding.all(10),
            border=ft.border.all(1, ft.Colors.GREY_700),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)
            ),
            # Додаємо сірий фільтр до всієї картки
            opacity=0.6,
        )
        
        # Обгортаємо в GestureDetector для кліку
        interactive_card = ft.GestureDetector(
            content=card_container,
            on_tap=lambda e: self._on_sold_card_click(e),
        )
        
        return interactive_card
        
        return card_container



    def _update_header_for_tab(self):
        """Оновлює header залежно від вибраної вкладки"""
        logger.info(f"🔄 _update_header_for_tab called, selected_tab={self.selected_tab}")
        
        if not hasattr(self, 'header_row'):
            logger.info("🔄 Header update skipped - no header_row")
            return
        
        # Захист від повторних викликів
        if hasattr(self, '_header_updating') and self._header_updating:
            logger.info("🔄 Header update skipped - already updating")
            return
        
        self._header_updating = True
        
        try:
            # Очищаємо header
            self.header_row.controls.clear()
            
            # Завжди центруємо таби, незалежно від вкладки
            self.header_row.controls.extend([
                ft.Container(expand=True),  # Лівий відступ
                self.tabs_container,  # Таби по центру
                ft.Container(expand=True),  # Правий відступ
            ])
            

        finally:
            self._header_updating = False

    def _build_sold_dashboard(self, props: List[dict]) -> ft.Control:
        """Створює сучасний dashboard для проданого майна"""
        
        # Розраховуємо статистику
        total_profit = 0
        total_invested = 0
        total_sold = 0
        profitable_count = 0
        
        for prop in props:
            purchase_price = float(prop.get("price", 0))
            selling_price = float(prop.get("selling_price", 0))
            profit = selling_price - purchase_price
            
            total_invested += purchase_price
            total_sold += selling_price
            total_profit += profit
            if profit > 0:
                profitable_count += 1
        
        avg_roi = (total_profit / total_invested * 100) if total_invested > 0 else 0
        success_rate = (profitable_count / len(props) * 100) if props else 0
        
        # Створюємо метрики
        metrics_row = ft.Row([
            # Загальний прибуток
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.TRENDING_UP, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.GREEN_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Text(
                        f"{format_number(total_profit)}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_total_profit", default="Загальний прибуток"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.GREEN_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Рентабельність
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.PERCENT, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.BLUE_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Text(
                        f"{avg_roi:.1f}%",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_avg_profitability", default="Середня рентабельність"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.BLUE_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Кількість продажів
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.PURPLE_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Text(
                        str(len(props)),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_sold_count", default="Продано майна"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.PURPLE_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Успішність
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.STAR, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.AMBER_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Text(
                        f"{success_rate:.1f}%",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_successful_deals", default="Успішних угод"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.AMBER_700,
                border_radius=16,
                expand=True,
            )
        ], spacing=0)
        
        # Створюємо draggable картки продажів (аналогічно активному майну)
        sold_cards = []
        for i, prop in enumerate(props):
            # Створюємо картку з drag & drop функціональністю
            sold_card = self._create_draggable_card(self._modern_sold_card(prop), prop.get("id"), "props_swap", self._on_swap_accept_async)
            sold_cards.append(sold_card)
        
        # Створюємо Row з картками та зберігаємо посилання для подальшого оновлення
        sold_cards_row = self._create_cards_row(sold_cards)
        self._sold_cards_row = sold_cards_row
        
        # Об'єднуємо все в dashboard
        return ft.Column([
            # Метрики
            ft.Container(
                content=metrics_row,
                margin=ft.margin.only(bottom=20)
            ),
            
            # Заголовок секції
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.HISTORY, color=ft.Colors.WHITE70, size=24),
                    ft.Text(
                        self.loc.get("properties_stats_sales_history", default="Історія продажів"),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    )
                ], spacing=12),
                margin=ft.margin.only(bottom=16)
            ),
            
            # Картки продажів з drag & drop (без відступів зліва)
            ft.Container(
                content=sold_cards_row,
                expand=True,
                margin=ft.margin.only(left=0)  # Прибираємо лівий відступ
            )
        ], expand=True)

    def _build_active_dashboard(self, props: List[dict]) -> ft.Control:
        """Створює сучасний dashboard для активного майна"""
        
        # Розраховуємо статистику
        total_value = 0
        total_count = len(props)
        avg_value = 0
        
        for prop in props:
            total_value += float(prop.get("price", 0))
        
        avg_value = total_value / total_count if total_count > 0 else 0
        
        # Створюємо метрики
        metrics_row = ft.Row([
            # Загальна вартість
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.BLUE_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                ft.Text(
                        f"{format_number(total_value)}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_total_value_active", default="Загальна вартість"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.BLUE_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Кількість майна
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.GREEN_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                ft.Text(
                        str(total_count),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_active_count", default="Активне майно"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.GREEN_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Середня вартість
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.CALCULATE, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.PURPLE_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                ft.Text(
                        f"{format_number(avg_value)}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_avg_value", default="Середня вартість"),
                    size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.PURPLE_700,
                border_radius=16,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            
            # Потенційний прибуток
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.TRENDING_UP, color=ft.Colors.WHITE, size=24),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.AMBER_600,
                        border_radius=12,
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Text(
                        "∞",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        self.loc.get("properties_stats_potential_profit", default="Потенційний прибуток"),
                        size=12,
                        color=ft.Colors.WHITE70
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(8),
                bgcolor=ft.Colors.AMBER_700,
                border_radius=16,
                expand=True,
            )
        ], spacing=0)
        
        # Створюємо картки активного майна (горизонтальний ряд)
        active_cards = []
        print(f"🔍 Creating {len(props)} active cards")
        for idx, prop in enumerate(props):
            print(f"🔍 Creating card {idx+1}: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            active_cards.append(self._create_draggable_card(self._active_card_body(prop), prop.get("id"), "props_swap", self._on_swap_accept_async))
        print(f"🔍 Created {len(active_cards)} active cards")
        
        # Створюємо Row з картками та зберігаємо посилання для подальшого оновлення
        cards_row = self._create_cards_row(active_cards)
        self._active_cards_row = cards_row
        
        # Об'єднуємо все в dashboard
        return ft.Column([
            # Метрики
                ft.Container(
                content=metrics_row,
                margin=ft.margin.only(bottom=20)
                ),
            
            # Заголовок секції з кнопкою додавання
                ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.WHITE70, size=24),
                    ft.Text(
                        self.loc.get("properties_stats_active_count", default="Активне майно"),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Container(
                        content=self.add_button,
                        margin=ft.margin.only(left=12)
                    )
                ], spacing=12),
                margin=ft.margin.only(bottom=16)
            ),
            
            # Картки активного майна (горизонтальний ряд)
            ft.Container(
                    content=cards_row,
                expand=True
            )
        ], expand=True)

    def _placeholder(self, text: str) -> ft.Container:
        """Створює placeholder з текстом"""
        # Розділяємо текст на рядки, якщо є переноси
        text_lines = text.split('\n')
        
        controls = [
            ft.Container(
                content=ft.Icon(ft.Icons.HOME_WORK_OUTLINED, size=60, color=ft.Colors.GREY_400),
                padding=ft.padding.all(20),
                bgcolor=ft.Colors.GREY_800,
                border_radius=30,
                margin=ft.margin.only(bottom=20)
            ),
        ]
        
        # Додаємо кожен рядок тексту
        for i, line in enumerate(text_lines):
            if line.strip():  # Пропускаємо порожні рядки
                controls.append(
                    ft.Text(
                        line.strip(),
                        size=18 if i == 0 else 14,  # Перший рядок більший
                        weight=ft.FontWeight.W_500 if i == 0 else ft.FontWeight.NORMAL,
                        color=ft.Colors.GREY_300 if i == 0 else ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER,
                    )
                )
        
        return ft.Container(
            content=ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            alignment=ft.alignment.center,
            height=300,
            border_radius=16,
            bgcolor=ft.Colors.GREY_900,
            border=ft.border.all(1, ft.Colors.GREY_700),
            padding=ft.padding.all(40),
        )

    def _on_swap_accept(self, e: ft.DragTargetEvent, target_prop_id: int):
        """Обробляє drop подію через DragDropManager"""
        if self.page:
            self.page.run_task(self._on_swap_accept_async, target_prop_id)

    def _on_drag_start(self, dragged_id: int | str | None):
        """Обробляє початок перетягування через DragDropManager"""
        if self.drag_drop_manager and dragged_id is not None:
            try:
                item_id = int(dragged_id) if isinstance(dragged_id, str) else dragged_id
                self.drag_drop_manager._on_drag_start(item_id)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert dragged_id to int: {e}")

    async def _on_swap_accept_async(self, target_prop_id: int):
        """Міняє місцями перетягувану картку з цільовою та зберігає порядок."""
        logger.info(f"🔄 Swap accept called for target_prop_id: {target_prop_id}")
        
        if not self.drag_drop_manager:
            logger.error("❌ DragDropManager not initialized")
            return
        
        profile = self.app_state.current_profile
        if not profile:
            logger.error("❌ No profile")
            return
        
        selected_tab = getattr(self, "selected_tab", "active")
        if selected_tab not in ["active", "sold"]:
            logger.error(f"❌ Invalid tab: {selected_tab}")
            return
        
        logger.info(f"📍 Processing swap for tab: {selected_tab}, profile: {profile.get('id')}")

        try:
            # Отримуємо поточний порядок залежно від типу майна
            current_ids = []
            logger.info(f"🔄 Getting current order for tab: {selected_tab}")
            
            if selected_tab == "active":
                # Для активного майна використовуємо кеш або завантажуємо з БД
                if hasattr(self, "_current_active_ids") and self._current_active_ids:
                    current_ids = [int(pid) for pid in self._current_active_ids]
                else:
                    props_fresh = await SafeAsyncExecutor.execute(
                        self.property_service.get_properties,
                        profile["id"],
                        "active",
                    )
                    current_ids = [int(p.get("id")) for p in props_fresh]
                    self._active_props_cache = list(props_fresh)
                    self._current_active_ids = list(current_ids)
            else:
                # Для проданого майна завжди завантажуємо з БД
                logger.info("🔄 Getting sold properties from DB")
                sold_props = await self.property_service.get_properties(profile["id"], "sold")
                current_ids = [int(prop.get("id")) for prop in sold_props]
                logger.info(f"✅ Got {len(current_ids)} sold properties: {current_ids}")
            
            if not current_ids:
                logger.error("❌ No current_ids found")
                return

            # Визначаємо callback для оновлення порядку в БД
            async def update_order_callback(new_order: List[int]):
                if selected_tab == "active":
                    await SafeAsyncExecutor.execute(
                        self.property_service.update_properties_order,
                        profile["id"], 
                        new_order,
                    )
                    # Оновлюємо кеш
                    self._current_active_ids = list(new_order)
                else:
                    # Отримуємо повні об'єкти проданого майна для оновлення порядку
                    sold_props = await self.property_service.get_properties(profile["id"], "sold")
                    ordered_sold_props = []
                    for prop_id in new_order:
                        for prop in sold_props:
                            if prop.get("id") == prop_id:
                                ordered_sold_props.append(prop)
                                break
                    logger.info(f"🔄 Saving sold properties order to DB: {[prop.get('id') for prop in ordered_sold_props]}")
                    await self.property_service.update_sold_properties_order(profile["id"], ordered_sold_props)
                    logger.info("✅ Sold properties order saved to DB")

            # Визначаємо callback для оновлення UI (для обох типів майна)
            async def refresh_ui_callback(new_order: List[int]):
                if selected_tab == "active":
                    try:
                        logger.info("🔄 Updating active dashboard without flickering")
                        # Оновлюємо кеш з новим порядком
                        cache_list = list(getattr(self, "_active_props_cache", []))
                        new_cache = []
                        for prop_id in new_order:
                            for prop in cache_list:
                                if prop.get("id") == prop_id:
                                    new_cache.append(prop)
                                    break
                        
                        self._active_props_cache = new_cache
                        
                        # Використовуємо збережене посилання на Row з картками
                        if hasattr(self, '_active_cards_row') and self._active_cards_row:
                            cards_row = self._active_cards_row
                            # Створюємо нові картки в правильному порядку
                            new_cards = []
                            for prop in new_cache:
                                new_cards.append(self._create_draggable_card(
                                    self._active_card_body(prop), 
                                    prop.get("id"), 
                                    "props_swap", 
                                    self._on_swap_accept_async
                                ))
                            
                            # Оновлюємо тільки controls в Row, не створюючи новий об'єкт
                            cards_row.controls.clear()
                            cards_row.controls.extend(new_cards)
                            
                            if self.page:
                                self.page.update()
                                logger.info("✅ Active cards reordered without flickering")
                            return
                        
                        # Фолбек: якщо не знайшли Row, оновлюємо повністю
                        logger.info("🔄 Fallback: updating entire dashboard")
                        new_active_dashboard = self._build_active_dashboard(new_cache)
                        if self.list_container:
                            self.list_container.content = new_active_dashboard
                            if self.page:
                                self.page.update()
                                logger.info("✅ Active dashboard updated with fallback")
                    except Exception as ex:
                        logger.error(f"❌ Error updating active cache: {ex}")
                        await self._refresh_list(show_loading=False, use_cache=False)
                elif selected_tab == "sold":
                    try:
                        logger.info("🔄 Updating sold dashboard without flickering")
                        # Отримуємо продане майно з новим порядком
                        sold_props = await self.property_service.get_properties(profile["id"], "sold")
                        new_sold_props = []
                        for prop_id in new_order:
                            for prop in sold_props:
                                if prop.get("id") == prop_id:
                                    new_sold_props.append(prop)
                                    break
                        
                        # Використовуємо збережене посилання на Row з картками
                        if hasattr(self, '_sold_cards_row') and self._sold_cards_row:
                            cards_row = self._sold_cards_row
                            # Створюємо нові картки в правильному порядку
                            new_cards = []
                            for prop in new_sold_props:
                                new_cards.append(self._create_draggable_card(
                                    self._modern_sold_card(prop), 
                                    prop.get("id"), 
                                    "props_swap", 
                                    self._on_swap_accept_async
                                ))
                            
                            # Оновлюємо тільки controls в Row, не створюючи новий об'єкт
                            cards_row.controls.clear()
                            cards_row.controls.extend(new_cards)
                            
                            if self.page:
                                self.page.update()
                                logger.info("✅ Sold cards reordered without flickering")
                            return
                        
                        # Фолбек: якщо не знайшли Row, оновлюємо повністю
                        logger.info("🔄 Fallback: updating entire sold dashboard")
                        await self._refresh_list(show_loading=False, use_cache=False)
                        logger.info("✅ Sold dashboard updated with fallback")
                    except Exception as ex:
                        logger.error(f"❌ Failed to update sold dashboard: {ex}")
                        await self._refresh_list(show_loading=False, use_cache=False)

            # Використовуємо DragDropManager для обробки swap
            success = await self.drag_drop_manager.handle_swap_async(
                target_id=target_prop_id,
                current_ids=current_ids,
                update_order_callback=update_order_callback,
                refresh_ui_callback=refresh_ui_callback
            )
            
            if not success:
                logger.error("❌ Swap operation failed")
                await self._refresh_list(show_loading=False, use_cache=False)
                    
        except Exception as ex:
            logger.error(f"❌ Error in swap operation: {ex}")
            await self._refresh_list(show_loading=False, use_cache=False)



    def _open_add_dialog(self, e):
        if self.page:
            self.page.run_task(self._open_add_dialog_async)

    async def _open_add_dialog_async(self):
        """Відкриває уніфікований оверлей форми для додавання майна"""
        await self._open_property_overlay(mode="add")
    
    def _close_simple_dialog(self):
        """Закриває всі відкриті AlertDialog в overlay"""
        try:
            if self.page:
                for overlay_item in self.page.overlay[:]:
                    if isinstance(overlay_item, ft.AlertDialog) and overlay_item.open:
                        overlay_item.open = False
                        self.page.overlay.remove(overlay_item)
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error in _close_simple_dialog: {e}")

    def _simple_overlay_cleanup(self):
        """Простий спосіб очищення overlay"""
        try:
            if not self.page or not hasattr(self.page, 'overlay'):
                return

            # Закриваємо всі відкриті елементи
            for item in self.page.overlay[:]:
                if (item is not None and 
                    hasattr(item, 'open') and 
                    hasattr(item, '_set_attr_internal') and
                    callable(getattr(item, 'open', None))):
                    try:
                        item.open = False
                    except Exception:
                        pass

            # Зберігаємо тільки file_picker, якщо він є
            preserved_items = []
            if hasattr(self, 'file_picker') and self.file_picker is not None and self.file_picker in self.page.overlay:
                preserved_items.append(self.file_picker)

            # Повністю очищаємо overlay
            self.page.overlay.clear()

            # Повертаємо збережені елементи
            for item in preserved_items:
                if item is not None:
                    self.page.overlay.append(item)

            # Очищаємо атрибути
            if hasattr(self, '_add_property_overlay'):
                delattr(self, '_add_property_overlay')

            # Оновлюємо сторінку
            if self.page:
                self.page.update()

        except Exception:
            # Аварійна спроба
            try:
                if self.page and hasattr(self.page, 'overlay') and hasattr(self.page, 'update'):
                    # Безпечно очищаємо overlay
                    overlay_copy = self.page.overlay[:]
                    self.page.overlay.clear()
                    
                    # Повертаємо тільки file_picker якщо він є
                    if hasattr(self, 'file_picker') and self.file_picker is not None:
                        self.page.overlay.append(self.file_picker)
                    
                    self.page.update()
            except Exception:
                # Фінальна спроба - просто оновлюємо сторінку
                try:
                    if self.page and hasattr(self.page, 'update'):
                        self.page.update()
                except Exception:
                    pass

    def _close_form_container(self):
        try:
            if self.page:
                self._simple_overlay_cleanup()

                # Додаткові очищення для форми
                if hasattr(self, 'preview_container') and self.preview_container is not None:
                    try:
                        if hasattr(self.preview_container, 'visible') and hasattr(self.preview_container, '_set_attr_internal'):
                            self.preview_container.visible = False
                    except Exception:
                        pass

                # Очищаємо зображення при закритті форми
                self.current_image_b64 = None


        except Exception:
            pass
    

    def _submit_edit_property(self, prop_id: int, name: str, price: str):
        """Обробляє редагування майна"""
        try:
            # Валідація
            if not name or not name.strip():
                return
            
            if not price or not price.strip():
                return
            
            try:
                price_value = float(price)
                if price_value <= 0:
                    return
            except ValueError:
                return
            
            # Отримуємо дату покупки
            purchase_date = self.input_purchase_date.get_date_string() if self.input_purchase_date else None
            
            # Закриваємо форму
            self._close_form_container()
            
            # Запускаємо асинхронне редагування
            if self.page:
                self.page.run_task(self._save_edit_property_async, prop_id, name, price_value, purchase_date)
        except Exception:
            pass

    def _submit_sell_property(self, prop_id: int, price: str):
        """Обробляє продаж майна"""
        try:
            # Валідація
            if not price or not price.strip():
                return
            
            try:
                selling_price = float(price)
                if selling_price <= 0:
                    return
            except ValueError:
                return
            
            # Закриваємо форму
            self._close_form_container()
            
            # Запускаємо асинхронне продаж
            if self.page:
                self.page.run_task(self._save_sell_property_async, prop_id, selling_price)
        except Exception:
            pass

    
    async def _show_success_message(self, message: str):
        """Показує повідомлення про успіх"""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_700
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _show_error_message(self, message: str):
        """Показує повідомлення про помилку"""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_700
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _pick_photo(self):
        """Обробляє вибір фото"""
        if self.page and self.file_picker:
            self.file_picker.pick_files(
                allowed_extensions=["jpg", "jpeg", "png", "gif"],
                allow_multiple=False
            )

    def _clear_photo(self):
        """Очищає вибране/вставлене фото та ховає прев'ю"""
        self.current_image_b64 = None
        if hasattr(self, 'preview_container') and self.preview_container is not None:
            try:
                if hasattr(self.preview_container, 'visible') and hasattr(self.preview_container, '_set_attr_internal'):
                    self.preview_container.visible = False
            except Exception:
                pass
        if self.page:
            self.page.update()

    def _paste_from_clipboard(self):
        """Вставляє зображення з буфера обміну (Windows/macOS/Linux)"""
        try:
            import io
            from PIL import Image, ImageGrab

            image_bytes: bytes | None = None

            # 1) Пробуємо дістати зображення безпосередньо з буфера
            grabbed = ImageGrab.grabclipboard()
            if isinstance(grabbed, Image.Image):
                buffer = io.BytesIO()
                grabbed.save(buffer, format='PNG')
                image_bytes = buffer.getvalue()
            elif isinstance(grabbed, list) and grabbed:
                # Деякі системи кладуть у буфер шлях(и) до файлу(ів)
                first_path = grabbed[0]
                try:
                    with open(first_path, 'rb') as f:
                        image_bytes = f.read()
                except Exception:
                    image_bytes = None

            if not image_bytes:
                # Немає зображення у буфері
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(self.loc.get("properties_image_clipboard_no_image", default="В буфері обміну немає зображення")),
                        bgcolor=ft.Colors.RED_700
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                return

            # 2) Компресуємо та конвертуємо у Base64 через сервіс
            self.current_image_b64 = PropertyService.image_to_base64(image_bytes)
            if not self.current_image_b64:
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(self.loc.get("properties_image_image_processing_error", default="Не вдалося обробити зображення з буфера")),
                        bgcolor=ft.Colors.RED_700
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                return

            # 3) Оновлюємо прев'ю
            pass
            self._update_preview()
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(self.loc.get("properties_image_image_pasted", default="Зображення вставлено з буфера обміну!")),
                    bgcolor=ft.Colors.GREEN_700
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{self.loc.get('properties_error_paste', 'Помилка при вставці')}: {str(e)}"),
                    bgcolor=ft.Colors.RED_700
                )
                self.page.snack_bar.open = True
                self.page.update()

    async def _paste_from_clipboard_async(self):
        """Асинхронно вставляє зображення з буфера обміну"""
        try:
            if not self.page:
                return
            image_data = self.page.clipboard.get_image()
            if not image_data:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(self.loc.get("properties_image_clipboard_no_image", "В буфері обміну немає зображення")), bgcolor=ft.Colors.RED_700)
                self.page.snack_bar.open = True
                self.page.update()
                return
            b64 = base64.b64encode(image_data).decode("utf-8")
            self.current_image_b64 = f"data:image/png;base64,{b64}"
            pass
            # Показуємо превʼю через уніфікований блок
            self._update_preview()
            self.page.snack_bar = ft.SnackBar(content=ft.Text(self.loc.get("properties_image_image_pasted", "Зображення вставлено з буфера обміну!")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()
        except Exception:
            pass

    def _open_edit_dialog_async(self, prop: dict):
        if self.page:
            self.page.run_task(self._open_property_overlay, "edit", prop)

    async def _open_property_overlay(self, mode: str, prop: Optional[dict] = None):
        """Відкриває уніфікований оверлей форми для add/edit/sell."""
        if not self.page:
            return

        # Очищаємо overlay перед відкриттям нового
        self._simple_overlay_cleanup()
        
        # Очищаємо форму для режиму додавання
        if mode == "add":
            if hasattr(self, 'preview_container') and self.preview_container is not None:
                try:
                    if hasattr(self.preview_container, 'visible') and hasattr(self.preview_container, '_set_attr_internal'):
                        self.preview_container.visible = False
                except Exception:
                    pass
        
        title_text = self.loc.get("properties_add_dialog_title", default="Додати нове майно") if mode == "add" else (self.loc.get("properties_edit_dialog_title", default="Редагувати майно") if mode == "edit" else self.loc.get("properties_sell_dialog_title", default="Продати майно"))

        # Поля вводу
        name_field = ft.TextField(label=self.loc.get("properties_name_label", default="Назва майна"), width=520, **TEXT_FIELD_STYLE)
        price_field = ft.TextField(label=self.loc.get("properties_price_label", default="Ціна"), width=520, input_filter=ft.NumbersOnlyInputFilter(), **TEXT_FIELD_STYLE)
        
        # Лейбл та відображення дати покупки
        purchase_date_label = ft.Text(
            self.loc.get("properties_purchase_date_label", default="Дата покупки"),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        # Відображення поточної дати
        self.purchase_date_display = ft.Text(
            "",  # Буде заповнено пізніше
            size=14,
            color=ft.Colors.WHITE70,
            weight=ft.FontWeight.NORMAL
        )
        
        # Кнопка календаря
        calendar_button = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            tooltip="Відкрити календар",
            icon_color=ft.Colors.WHITE,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.AMBER_600 if mode == "edit" else ft.Colors.BLUE_600,
                shape=ft.RoundedRectangleBorder(radius=4)
            )
        )
        
        # Date picker (тільки календар)
        purchase_date_picker = ModernDatePicker(
            page=self.page,
            mode=mode,  # Передаємо режим (add/edit)
            localization_manager=self.loc  # Передаємо локалізацію
        )
        
        # Встановлюємо callback для оновлення відображення дати
        def on_date_changed(selected_date):
            self.purchase_date_display.value = selected_date.strftime("%d.%m.%Y")
            if self.page:
                self.page.update()
        
        purchase_date_picker.on_date_changed = on_date_changed
        
        # Прив'язуємо кнопку календаря до date picker
        calendar_button.on_click = purchase_date_picker._toggle_calendar
        
        # Ініціалізуємо поточну дату для нового майна
        if mode == "add":
            from datetime import date
            today = date.today()
            purchase_date_picker.set_date(today)
            self.purchase_date_display.value = today.strftime("%d.%m.%Y")
        
        # Зберігаємо посилання на поля для використання в _submit_add_edit_async
        self.input_name = name_field
        self.input_price = price_field
        self.input_purchase_date = purchase_date_picker
        
        # Для режиму продажу робимо назву тільки для читання
        if mode == "sell":
            name_field.read_only = True
            name_field.disabled = True
            # Для date picker в режимі продажу просто не дозволяємо зміни
            purchase_date_picker.disabled = True

        # Якщо редагуємо або продаємо — підставляємо значення
        if prop:
            name_field.value = prop.get("name", "")
            # Встановлюємо дату в picker та відображення
            purchase_date_str = prop.get("purchase_date", "")
            if purchase_date_str:
                purchase_date_picker.set_date_from_string(purchase_date_str)
                # Встановлюємо відображення дати
                try:
                    from datetime import datetime
                    dt_obj = datetime.strptime(purchase_date_str, "%Y-%m-%d")
                    self.purchase_date_display.value = dt_obj.strftime("%d.%m.%Y")
                except:
                    self.purchase_date_display.value = purchase_date_str[:10] if len(purchase_date_str) >= 10 else purchase_date_str
            else:
                # Якщо дата не встановлена, показуємо поточну дату
                from datetime import date
                self.purchase_date_display.value = date.today().strftime("%d.%m.%Y")
            if mode == "sell":
                # В режимі продажу показуємо поточну ціну майна як початкове значення
                try:
                    price_field.value = str(int(float(prop.get("price", 0))))
                except Exception:
                    price_field.value = str(prop.get("price", 0))
            else:
                # В режимі редагування показуємо поточну ціну
                try:
                    price_field.value = str(int(float(prop.get("price", 0))))
                except Exception:
                    price_field.value = str(prop.get("price", 0))
            
                            # Для редагування встановлюємо зображення з пропа
                if mode == "edit" and prop.get("image_b64"):
                    self.current_image_b64 = prop.get("image_b64")

        # Кнопки фото (тільки для add/edit, не для sell)
        if mode != "sell":
            photo_buttons = ft.Row([
                ft.Container(content=ft.ElevatedButton(self.loc.get("properties_add_photo", default="Додати фото"), on_click=lambda e: self._pick_photo(), icon=ft.Icons.PHOTO_CAMERA,
                                                      style=ft.ButtonStyle(padding=ft.padding.all(14), shape=ft.RoundedRectangleBorder(radius=10), color=ft.Colors.WHITE, bgcolor=ft.Colors.GREY_700))),
                ft.Container(content=ft.ElevatedButton(self.loc.get("properties_paste_from_clipboard", default="Вставити з буфера"), on_click=lambda e: self._paste_from_clipboard(), icon=ft.Icons.CONTENT_PASTE,
                                                      style=ft.ButtonStyle(padding=ft.padding.all(14), shape=ft.RoundedRectangleBorder(radius=10), color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_700)))
            ], spacing=10)
        else:
            photo_buttons = ft.Container(height=0)  # Порожній контейнер для sell

        # Попередній перегляд (тільки для add/edit, не для sell)
        if mode != "sell":
            self.preview_container = ft.Container(
                content=ft.Column([
                    ft.Text(self.loc.get("properties_preview", default="Попередній перегляд:"), size=16, color=ft.Colors.WHITE70, weight=ft.FontWeight.W_500),
                    ft.Container(content=ft.Text(self.loc.get("properties_no_image", default="Немає зображення"), size=14, color=ft.Colors.GREY_500), width=280, height=200,
                                 bgcolor=ft.Colors.GREY_800, border_radius=12, alignment=ft.alignment.center, border=ft.border.all(1, ft.Colors.GREY_600))
                ], spacing=12),
                visible=False,
            )
            # Якщо є картинка у стані — показуємо превʼю (після створення preview_container)
            if getattr(self, 'current_image_b64', None):
                self._update_preview()
        else:
            self.preview_container = ft.Container(height=0)  # Порожній контейнер для sell

        # Тіло форми
        if mode == "sell":
            # Для продажу додаємо розрахунок маржі
            margin_label = ft.Text(self.loc.get("properties_margin_calculation", default="Розрахунок маржі:"), size=16, color=ft.Colors.WHITE70, weight=ft.FontWeight.W_500)
            margin_result = ft.Text("", size=14, color=ft.Colors.GREY_500)
            
            def update_margin(e):
                try:
                    original_price = float(prop.get("price", 0)) if prop and prop.get("price") else 0
                    selling_price = float(price_field.value or 0)
                    if selling_price > 0 and original_price > 0:
                        margin = selling_price - original_price
                        margin_percent = (margin / original_price) * 100
                        if margin > 0:
                            margin_result.value = f"+{int(margin):,} $\n(+{margin_percent:.1f}%)".replace(",", " ")
                            margin_result.color = ft.Colors.GREEN_400
                        else:
                            margin_result.value = f"{int(margin):,} $\n({margin_percent:.1f}%)".replace(",", " ")
                            margin_result.color = ft.Colors.RED_400
                    else:
                        margin_result.value = self.loc.get("properties_enter_sell_price", default="Введіть ціну продажу")
                        margin_result.color = ft.Colors.GREY_500
                    margin_result.update()
                except:
                    margin_result.value = self.loc.get("properties_calculation_error", default="Помилка розрахунку")
                    margin_result.color = ft.Colors.GREY_500
                    margin_result.update()
            
            # Додаємо обробник для введення ціни та оновлення маржі
            def on_price_change(e):
                # Очищаємо поле від недопустимих символів
                original_value = e.control.value
                cleaned_value = ''.join(filter(str.isdigit, original_value))
                
                if original_value != cleaned_value:
                    e.control.value = cleaned_value
                    e.control.update()
                
                # Оновлюємо розрахунок маржі
                update_margin(e)
            
            price_field.on_change = on_price_change
            
            # Встановлюємо початковий розрахунок маржі
            if prop and prop.get("price"):
                try:
                    original_price = float(prop.get("price", 0))
                    if original_price > 0:
                        margin_result.value = f"{self.loc.get('properties_current_price', default='Поточна ціна:')}\n{int(original_price):,} $".replace(",", " ")
                        margin_result.color = ft.Colors.GREY_500
                except:
                    margin_result.value = self.loc.get("properties_enter_sell_price", default="Введіть ціну продажу")
                    margin_result.color = ft.Colors.GREY_500
            
            # Створюємо рядок для розрахунку маржі з кнопками навпроти
            margin_and_buttons_row = ft.Row([
                ft.Column([
                    margin_label,
                    margin_result
                ], spacing=5, expand=True),
                ft.Column([
                    ft.Container(height=0),  # Відступ для вирівнювання з розрахунком маржі
                    ft.Row([
                        ft.ElevatedButton(self.loc.get("properties_cancel", default="Скасувати"), on_click=lambda e: self._close_form_container(), style=BUTTON_STYLE_DANGER, width=None, height=None),
                        ft.Container(width=15),
                        ft.ElevatedButton(self.loc.get("properties_sell", default="Продати"), on_click=lambda e: on_submit(), style=BUTTON_STYLE_PRIMARY, width=None, height=None)
                    ], spacing=0)
                ], alignment=ft.MainAxisAlignment.END)
            ], alignment=ft.MainAxisAlignment.START, spacing=20)
            
            self.form_body = ft.Column([
                ft.Container(height=5),  # Зменшений відступ зверху
                name_field, 
                ft.Container(height=16), 
                price_field,  # Тепер поле ціни має вбудований лейбл
                ft.Container(height=16),
                margin_and_buttons_row  # Розрахунок маржі з кнопками
            ], spacing=0)
        else:
            # Для режимів add/edit створюємо структуру з кнопками внизу
            if mode == "edit":
                # Для редагування - аналогічно до продажу, але з фото та прев'ю
                self.form_body = ft.Column([
                    ft.Container(height=2),  # Мінімальний відступ зверху
                    
                    # Група 1: Назва та ціна
                    name_field, 
                    ft.Container(height=12), 
                    price_field,  # Тепер поле ціни має вбудований лейбл
                    
                    # Розділювач 1
                    self._create_form_divider(),
                    
                    # Група 2: Дата покупки
                    ft.Row([
                        purchase_date_label,
                        calendar_button
                    ], spacing=5, alignment=ft.MainAxisAlignment.START),
                    ft.Container(height=6),
                    # Відображення дати
                    self.purchase_date_display,
                    ft.Container(height=12),
                    # Date picker (тільки календар)
                    purchase_date_picker,
                    
                    # Розділювач 2
                    self._create_form_divider(),
                    
                    # Група 3: Фото та прев'ю
                    photo_buttons,  # Кнопки фото
                    ft.Container(height=8),
                    self.preview_container,  # Прев'ю зображення
                    ft.Container(height=8)
                    # Кнопки будуть додані пізніше
                ], spacing=0)
            else:
                # Для додавання - оновлена структура
                self.form_body = ft.Column([
                    # Група 1: Назва та ціна
                    name_field, 
                    ft.Container(height=16), 
                    price_field, 
                    
                    # Розділювач 1
                    self._create_form_divider(),
                    
                    # Група 2: Дата покупки
                    ft.Row([
                        purchase_date_label,
                        calendar_button
                    ], spacing=5, alignment=ft.MainAxisAlignment.START),
                    ft.Container(height=6),
                    # Відображення дати
                    self.purchase_date_display,
                    ft.Container(height=12),
                    # Date picker (тільки календар)
                    purchase_date_picker, 
                    
                    # Розділювач 2
                    self._create_form_divider(),
                    
                    # Група 3: Фото та прев'ю
                    photo_buttons, 
                    ft.Container(height=12), 
                    self.preview_container
                ], spacing=0, scroll=ft.ScrollMode.AUTO)
        # Кнопки дій (створюємо після форми)
        cancel_button = ft.ElevatedButton(self.loc.get("properties_cancel", default="Скасувати"), on_click=lambda e: self._close_form_container(), style=BUTTON_STYLE_DANGER, width=None, height=None)

        def on_submit():
            if mode == "add":
                # Використовуємо новий метод через _submit_add_edit_async
                self._submit_add_edit()
            elif mode == "edit":
                # Використовуємо існуючий пайплайн оновлення через сервіс
                try:
                    if not name_field.value or not name_field.value.strip():
                        return
                    if not price_field.value or not price_field.value.strip():
                        return
                    price_value = float(price_field.value)
                    if price_value <= 0:
                        return
                except Exception:
                    return
                if self.page and prop:
                    # Отримуємо дату покупки
                    purchase_date = self.input_purchase_date.get_date_string() if self.input_purchase_date else None
                    self.page.run_task(self._save_edit_property_async, prop.get("id"), name_field.value, price_value, purchase_date)
            elif mode == "sell":
                # Для продажу використаємо ціну як selling_price
                try:
                    if not price_field.value or not price_field.value.strip():
                        return
                    selling_price = float(price_field.value)
                    if selling_price <= 0:
                        return
                except Exception:
                    return
                if self.page and prop:
                    self.page.run_task(self._save_sell_property_async, prop.get("id"), selling_price)

        action_text = self.loc.get("properties_add", default="Додати") if mode == "add" else (self.loc.get("properties_save", default="Зберегти") if mode == "edit" else self.loc.get("properties_sell", default="Продати"))
        submit_button = ft.ElevatedButton(action_text, on_click=lambda e: on_submit(), style=BUTTON_STYLE_PRIMARY, width=None, height=None)
        
        # Додаємо кнопки до форми редагування
        if mode == "edit":
            edit_buttons_row = ft.Row([
                ft.Container(expand=True),  # Розтягуємо простір зліва
                ft.Row([
                    cancel_button,
                    ft.Container(width=15),
                    submit_button
                ], spacing=0)
            ], alignment=ft.MainAxisAlignment.END)
            self.form_body.controls.append(edit_buttons_row)
            # Для edit режиму кнопки вже в формі, тому внизу не потрібні
            actions_row = ft.Container(height=0)
        elif mode == "sell":
            # Для sell режиму кнопки вже в формі (в margin_and_buttons_row), тому внизу не потрібні
            actions_row = ft.Container(height=0)
        else:
            # Тільки для add режиму кнопки внизу
            actions_row = ft.Row([cancel_button, ft.Container(width=15), submit_button], alignment=ft.MainAxisAlignment.END)

        # Адаптивна висота діалогу - автоматично підлаштовується під контент
        # Визначаємо оптимальну висоту залежно від режиму та розміру екрану
        if mode == "sell":
            base_height = 380  # Зменшена висота для продажу щоб прибрати пусте місце
        elif mode == "edit":
            base_height = 450  # Зменшена висота для редагування
        else:  # add mode
            base_height = 400  # Стандартна форма для додавання
        
        # Адаптуємо до розміру екрану
        if self.page and isinstance(self.page.height, (int, float)):
            try:
                screen_height = int(self.page.height)
                max_screen_height = int(screen_height * 0.8)  # 80% від висоти екрану
                dialog_height = min(base_height, max_screen_height)
            except Exception:
                dialog_height = base_height
        else:
            dialog_height = base_height

        # Визначаємо колір іконки та рамки залежно від режиму
        if mode == "sell":
            icon_bgcolor = ft.Colors.GREEN_600
            border_color = ft.Colors.GREEN_400
        elif mode == "edit":
            icon_bgcolor = ft.Colors.AMBER_600
            border_color = ft.Colors.AMBER_400
        else:  # add mode
            icon_bgcolor = ft.Colors.BLUE_500
            border_color = ft.Colors.BLUE_400

        # Визначаємо чи потрібен скролл залежно від режиму
        scroll_mode = None if mode == "sell" else ft.ScrollMode.AUTO

        form_container = ft.Container(
                content=ft.Column([
                    ft.Container(content=ft.Row([
                        ft.Container(content=ft.Icon(ft.Icons.HOME_WORK, color=ft.Colors.WHITE, size=32), padding=ft.padding.all(12), bgcolor=icon_bgcolor, border_radius=12, margin=ft.margin.only(right=15)),
                        ft.Text(title_text, size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                    ], alignment=ft.MainAxisAlignment.CENTER), padding=ft.padding.only(bottom=20), margin=ft.margin.only(bottom=10), border=ft.border.only(bottom=ft.border.BorderSide(1, border_color))),
                    ft.Container(content=self.form_body, padding=ft.padding.symmetric(horizontal=15, vertical=8)),
                    ft.Container(content=actions_row, padding=ft.padding.symmetric(horizontal=15, vertical=10))
                ], scroll=scroll_mode),
                padding=ft.padding.all(18), bgcolor=ft.Colors.GREY_900, border_radius=20, border=ft.border.all(2, border_color),
                width=600, height=dialog_height, alignment=ft.alignment.center,
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=20, color=ft.Colors.with_opacity(0.45, ft.Colors.BLACK), offset=ft.Offset(0, 8))
            )

        self.form_container = form_container
        centered_container = ft.Container(content=form_container, alignment=ft.alignment.center, expand=True)
        backdrop = ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK), on_click=lambda e: self._close_form_container())
        overlay_stack = ft.Stack([backdrop, centered_container], expand=True)
        self._add_property_overlay = overlay_stack
        self.page.overlay.append(overlay_stack)
        self.page.update()

    def _ensure_add_edit_dialog(self):
        # старий діалог більше не використовується — уніфікований оверлей форми
        return

    def _reset_add_edit_form(self):
        if hasattr(self, 'input_name'):
            self.input_name.value = ""
        if hasattr(self, 'input_price'):
            self.input_price.value = ""
        if hasattr(self, 'input_purchase_date'):
            # Скидаємо date picker до поточної дати
            from datetime import date
            self.input_purchase_date.set_date(date.today())
        if hasattr(self, 'purchase_date_display'):
            # Скидаємо відображення дати до поточної дати
            from datetime import date
            self.purchase_date_display.value = date.today().strftime("%d.%m.%Y")
        if hasattr(self, 'preview_image') and self.preview_image is not None:
            try:
                if hasattr(self.preview_image, 'visible') and hasattr(self.preview_image, '_set_attr_internal'):
                    self.preview_image.visible = False
            except Exception:
                pass

    def _submit_add_edit(self):
        if self.page:
            self.page.run_task(self._submit_add_edit_async)

    async def _submit_add_edit_async(self):
        """Валідує та зберігає майно"""
        try:
            # Отримуємо дані з полів
            name = self.input_name.value.strip() if self.input_name else ""
            price_str = self.input_price.value.strip() if self.input_price else ""
            purchase_date = self.input_purchase_date.get_date_string() if self.input_purchase_date else ""
            
            # Валідація назви
            if not name:
                await self._toast(self.loc.get("properties_error_name_empty", default="Введіть назву"), error=True)
                return
            
            # Валідація ціни
            if not price_str:
                await self._toast(self.loc.get("properties_error_price_empty", default="Введіть ціну"), error=True)
                return
            
            try:
                price = float(price_str.replace(',', '.'))
                if price <= 0:
                    await self._toast(
                        self.loc.get("properties_error_price_negative", default="Ціна не може бути від'ємною"),
                        error=True
                    )
                    return
            except (ValueError, TypeError):
                await self._toast(self.loc.get("properties_error_price_invalid", default="Невірний формат ціни"), error=True)
                return
            
            # Додаткова валідація
            if len(name) > 100:
                await self._toast(self.loc.get("properties_name_too_long", default="Назва занадто довга (максимум 100 символів)"), error=True)
                return
            
            if price > 999999999:
                await self._toast(self.loc.get("properties_price_too_large", default="Ціна занадто велика"), error=True)
                return

            # Date picker завжди повертає валідну дату, тому валідація не потрібна

            profile = self.app_state.current_profile
            if not profile:
                await self._toast(self.loc.get("properties_profile_not_found", default="Профіль не знайдено"), error=True)
                return

            # Створюємо об'єкт PropertyData для валідації
            property_data = PropertyData(
                name=name,
                price=price,
                image_b64=getattr(self, 'current_image_b64', None) or "",
                purchase_date=purchase_date if purchase_date else None
            )
            
            # Валідуємо через сервіс
            errors = property_data.validate()
            if errors:
                await self._toast("; ".join(errors), error=True)
                return

            # Зберігаємо майно
            if not self.editing_property_id:
                # Додаємо нове майно
                new_id = await SafeAsyncExecutor.execute(
                    self.property_service.add_property,
                    profile["id"],
                    property_data
                )
                
                if new_id:
                    # Очищаємо кеш
                    
                    # Повідомляємо інші представлення про зміни
                    try:
                        self.app_state.notify_transactions_change()
                    except Exception:
                        pass
                    
                    await self._toast(self.loc.get("properties_success_add", default="Додано"))
                else:
                    await self._toast(self.loc.get("properties_error_adding", default="Помилка при додаванні майна"), error=True)
                    return
            else:
                # Оновлюємо існуюче майно
                success = await SafeAsyncExecutor.execute(
                    self.property_service.update_property,
                    self.editing_property_id,
                    property_data
                )
                
                if success:
                    # Очищаємо кеш
                    await self._toast(self.loc.get("properties_success_save", default="Збережено"))
                else:
                    await self._toast(self.loc.get("properties_error_saving", default="Помилка при збереженні майна"), error=True)
                    return

            # Закриваємо overlay форму та оновлюємо список
            self._close_form_container()
            
            # Додаємо затримку перед оновленням списку
            await asyncio.sleep(0.1)
            
            # Оновлюємо список з пропуском UI оновлення
            await self._refresh_list(skip_ui_update=True)
            
            # Оновлюємо позицію кнопки після додавання майна
            self._update_add_button_position()
            
            # Оновлюємо UI окремо
            if self.page:
                self.page.update()
            
        except Exception as e:
            logger.error(f"Error in _submit_add_edit_async: {e}")
            await self._toast(f"{self.loc.get('properties_error', default='Помилка:')} {str(e)}", error=True)

    def _on_file_pick(self, e: ft.FilePickerResultEvent):
        """Обробляє вибір файлу з оптимізацією зображення"""
        if not e.files:
            return
        
        try:
            file_path = e.files[0].path
            if not file_path:
                raise ValueError("Не вдалося отримати шлях до файлу")
            
            # Перевіряємо розмір файлу (максимум 10MB)
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB
                raise ValueError("Файл занадто великий (максимум 10MB)")
            
            # Читаємо файл
            with open(file_path, "rb") as f:
                data = f.read()
            
            if not data:
                raise ValueError(self.loc.get("properties_file_empty", default="Файл порожній"))
            
            # Оптимізуємо зображення через сервіс
            self.current_image_b64 = PropertyService.image_to_base64(data)
            
            # Додаємо детальне логування для діагностики
            if not self.current_image_b64:
                raise ValueError(self.loc.get("properties_image_processing_failed", default="Не вдалося обробити зображення"))
            
            # Оновлюємо попередній перегляд
            self._update_preview()
            
            # Показуємо повідомлення про успіх
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(self.loc.get("properties_photo_added_success", default="Фото додано успішно!")),
                    bgcolor=ft.Colors.GREEN_700
                )
                self.page.snack_bar.open = True
                self.page.update()
                
        except Exception as e:
            logger.error(f"Error processing image file: {e}")
            # Скидаємо зображення
            self.current_image_b64 = None
            self._update_preview()
            
            if self.page:
                error_message = str(e)
                if "занадто великий" in error_message:
                    error_message = self.loc.get("properties_file_too_large", default="Файл занадто великий (максимум 10MB)")
                elif "не вдалося обробити" in error_message:
                    error_message = self.loc.get("properties_unsupported_format", default="Непідтримуваний формат зображення")
                
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{self.loc.get('properties_photo_upload_error', default='Помилка при завантаженні фото:')} {error_message}"),
                    bgcolor=ft.Colors.RED_700
                )
                self.page.snack_bar.open = True
                self.page.update()

    def _open_sell_dialog_async(self, prop: dict):
        if self.page:
            self.page.run_task(self._open_property_overlay, "sell", prop)

    async def _save_edit_property_async(self, prop_id: int, name: str, price_value: float, purchase_date: str = None):
        try:
            property_data = PropertyData(
                name=name, 
                price=price_value, 
                image_b64=getattr(self, 'current_image_b64', None) or "",
                purchase_date=purchase_date
            )
            await SafeAsyncExecutor.execute(self.property_service.update_property, prop_id, property_data)
            self._close_form_container()
            await self._refresh_list(force_refresh=True)  # Примусово оновлюємо з БД
            await self._show_success_message(self.loc.get("properties_success_save", default="Збережено"))
        except Exception as e:
            await self._show_error_message(str(e))

    async def _save_sell_property_async(self, prop_id: int, selling_price: float):
        try:
            await SafeAsyncExecutor.execute(self.property_service.sell_property, prop_id, selling_price, "")
            self._close_form_container()
            
            # Переключаємося на вкладку "Продане" після продажу
            await self.switch_tab("sold", force=True)
            
            await self._show_success_message(self.loc.get("properties_success_sold", default="Продано"))
        except Exception as e:
            await self._show_error_message(str(e))

    def _ensure_sell_dialog(self):
        # старий діалог більше не використовується — уніфікований оверлей форми
            return

    def _confirm_sell(self):
        if self.page:
            self.page.run_task(self._confirm_sell_async)

    async def _confirm_sell_async(self):
        """Безпечно продає майно через сервіс"""
        try:
            prop = self.sell_dialog.data if self.sell_dialog else None
            if not prop:
                logger.error("No property data in sell dialog")
                await self._toast("Дані майна не знайдено", error=True)
                return
            
            profile = self.app_state.current_profile
            if not profile:
                logger.error("No current profile")
                await self._toast(self.loc.get("properties_profile_not_found", default="Профіль не знайдено"), error=True)
                return
            
            # Валідація ціни продажу
            price_str = self.sell_price_input.value.strip() if self.sell_price_input else ""
            if not price_str:
                await self._toast("Введіть ціну продажу", error=True)
                return
            
            try:
                selling_price = float(price_str.replace(',', '.'))
                if selling_price <= 0:
                    await self._toast("Ціна продажу має бути більше 0", error=True)
                    return
                if selling_price > 999999999:
                    await self._toast(self.loc.get("properties_price_too_large", default="Ціна занадто велика"), error=True)
                    return
            except (ValueError, TypeError):
                await self._toast("Невірний формат ціни", error=True)
                return

            # Валідація нотаток
            notes = self.sell_notes_input.value.strip() if self.sell_notes_input else ""
            if len(notes) > 500:
                await self._toast("Нотатки занадто довгі (максимум 500 символів)", error=True)
                return

            # Продаємо через сервіс
            if prop and prop.get("id"):
                success = await SafeAsyncExecutor.execute(
                    self.property_service.sell_property,
                    prop.get("id"),
                    selling_price,
                    notes
                )
                
                if not success:
                    await self._toast("Помилка при продажу майна", error=True)
                    return
            
            # Інвалідуємо кеш
            # property_cache.invalidate_properties(profile["id"])  # Видалено після очищення
            
            # Сповіщаємо інші в'ю про зміну транзакцій
            try:
                self.app_state.notify_transactions_change()
            except Exception:
                pass
            
            self._close_form_container()  # Закриваємо overlay форму
            
            # Переключаємося на вкладку "Продане" після продажу
            await self.switch_tab("sold", force=True)
            
            await self._toast(self.loc.get("properties_success_sold", default="Продано"))
            
        except Exception as e:
            logger.error(f"Error selling property: {e}")
            await self._toast(f"Помилка при продажу: {str(e)}", error=True)

    def _confirm_delete_async(self, prop: dict, from_sold: bool):
        """Запускає асинхронний процес видалення майна"""
        logger.info(f"🔄 Delete button clicked for property: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
        if self.page:
            self.page.run_task(self._delete_property_async, prop, from_sold)
        else:
            logger.error("❌ No page available for delete operation")

    async def _delete_property_async(self, prop: dict, from_sold: bool):
        """Сучасний асинхронний процес видалення майна"""
        try:
            logger.info(f"🔄 Starting modern property delete for: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            
            # Крок 1: Показуємо діалог підтвердження
            confirmed = await self._show_delete_confirmation(prop)
            if not confirmed:
                logger.info("❌ Delete operation cancelled by user")
                return
            
            # Крок 2: Показуємо індикатор завантаження
            await self._show_loading_indicator("Видаляємо майно...")
            
            # Крок 3: Виконуємо видалення
            success = await self._perform_delete_operation(prop)
            if not success:
                await self._hide_loading_indicator()
                await self._show_toast("Помилка при видаленні майна", error=True)
                return
            
            # Крок 4: Оновлюємо дані та кеш
            await self._update_data_after_delete(prop)
            
            # Крок 5: Приховуємо індикатор завантаження
            await self._hide_loading_indicator()
            
            # Крок 6: Показуємо повідомлення про успіх
            await self._show_toast("Майно видалено успішно!")
            
            logger.info(f"✅ Property delete completed successfully for: {prop.get('name', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"❌ Error in delete operation: {e}")
            await self._hide_loading_indicator()
            await self._show_toast(f"Помилка при видаленні: {str(e)}", error=True)

    async def _show_delete_confirmation(self, prop: dict) -> bool:
        """Показує діалог підтвердження видалення"""
        try:
            # Створюємо діалог підтвердження
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(self.loc.get("properties_confirm_delete", default="Підтвердити видалення")),
                content=ft.Text(f"{self.loc.get('properties_confirm_delete_content', 'Видалити майно')} '{prop.get('name', 'Unknown')}'?\n\n{self.loc.get('properties_confirm_delete_warning', 'Цю дію не можна відмінити.')}"),
                actions=[
                    ft.TextButton(self.loc.get("properties_cancel", default="Скасувати"), on_click=lambda e: self._close_dialog_sync(dialog, False)),
                    ft.ElevatedButton(
                        self.loc.get("properties_delete", "Видалити"),
                        bgcolor=ft.Colors.RED_700,
                        color=ft.Colors.WHITE,
                        on_click=lambda e: self._close_dialog_sync(dialog, True)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            # Додаємо діалог до overlay
            if self.page and dialog not in self.page.overlay:
                self.page.overlay.append(dialog)
            
            # Відкриваємо діалог
            dialog.open = True
            self.page.update()
            
            # Чекаємо результат
            return await self._wait_for_dialog_result(dialog)
            
        except Exception as e:
            logger.error(f"❌ Error showing delete confirmation: {e}")
            return False

    async def _perform_delete_operation(self, prop: dict) -> bool:
        """Виконує операцію видалення майна"""
        try:
            logger.info(f"🔄 Performing delete operation for property: {prop.get('name', 'Unknown')}")
            logger.info(f"🔄 Property object: {prop}")
            
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile")
                return False
            
            # Видаляємо через сервіс
            if prop and prop.get("id"):
                property_id = prop.get("id")
                logger.info(f"🔄 Calling delete_property with ID: {property_id}")
                success = await SafeAsyncExecutor.execute(
                    self.property_service.delete_property,
                    property_id
                )
                
                if not success:
                    logger.error("❌ Delete operation failed")
                    return False
                
                logger.info(f"✅ Delete operation completed successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error in delete operation: {e}")
            return False

    async def _update_data_after_delete(self, prop: dict):
        """Оновлює дані та кеш після видалення"""
        try:
            logger.info(f"🔄 Updating data and cache after delete...")
            
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile")
                return
            
            # Інвалідуємо кеш
            # property_cache.invalidate_properties(profile["id"])  # Видалено після очищення
            
            # Сповіщаємо інші в'ю про зміну транзакцій
            try:
                self.app_state.notify_transactions_change()
            except Exception:
                pass
            
            # Оновлюємо список
            await self._refresh_list()
            
            # Додаємо логування стану кешу після оновлення
            logger.info(f"🔍 Cache state after refresh: has_cache={hasattr(self, '_active_props_cache')}, cache_length={len(self._active_props_cache) if hasattr(self, '_active_props_cache') and self._active_props_cache else 0}")
            
            # Оновлюємо header для показу/приховування кнопки "+"
            self._update_header_for_tab()
            
            # Оновлюємо позицію кнопки після видалення майна
            self._update_add_button_position()
            
            logger.info(f"✅ Data and cache updated successfully")
            
        except Exception as e:
            logger.error(f"❌ Error updating data after delete: {e}")

    async def _open_dialog(self, dialog: ft.AlertDialog):
        if not self.page:
            logger.error("❌ No page available for _open_dialog")
            return
        logger.info(f"🔧 Opening dialog: {dialog}")

        # Спочатку додаємо діалог до overlay, якщо його там немає
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
            logger.info("🔧 Dialog added to overlay")

        # Відкриваємо діалог
        dialog.open = True

        # Оновлюємо сторінку
        self.page.update()
        logger.info(f"🔧 Dialog opened successfully, dialog.open = {dialog.open}")

        # Спробуємо також оновити сам діалог
        try:
            dialog.update()
            logger.info("🔧 Dialog.update() called")
        except Exception as e:
            logger.error(f"❌ Error updating dialog: {e}")

    def _close_dialog_sync(self, dialog: ft.AlertDialog, result: bool):
        """Закриває діалог та встановлює результат"""
        try:
            dialog.open = False
            dialog._result = result  # Встановлюємо результат безпосередньо
            self.page.update()
            logger.info(f"🔘 Dialog closed with result: {result}")
        except Exception as e:
            logger.error(f"❌ Error in _close_dialog_sync: {e}")

    async def _close_dialog(self, dialog: Optional[ft.AlertDialog]):
        """Асинхронно закриває діалог через overlay"""
        if not self.page:
            logger.error("❌ Cannot close dialog - no page")
            return
        
        try:
            if dialog:
                # Закриваємо конкретний діалог
                logger.info(f"🔧 Closing specific dialog: {dialog}")
                dialog.open = False
                if dialog in self.page.overlay:
                    self.page.overlay.remove(dialog)
                    logger.info("✅ Dialog removed from overlay")
            else:
                # Закриваємо всі відкриті діалоги в overlay
                logger.info("🔧 Closing all dialogs in overlay")
                dialogs_to_remove = []
                for overlay_item in self.page.overlay:
                    if isinstance(overlay_item, ft.AlertDialog) and overlay_item.open:
                        dialogs_to_remove.append(overlay_item)
                
                for dialog_to_remove in dialogs_to_remove:
                    dialog_to_remove.open = False
                    self.page.overlay.remove(dialog_to_remove)
                    logger.info("✅ Dialog removed from overlay")
            
            if self.page:
                self.page.update()
                logger.info("✅ Dialog(s) closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing dialog: {e}")

    async def _toast(self, text: str, error: bool = False):
        if not self.page:
            return
        pass
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(text), bgcolor=(ft.Colors.RED_700 if error else ft.Colors.GREEN_700)
        )
        self.page.snack_bar.open = True
        self.page.update()



    def _update_preview(self):
        """Оновлює попередній перегляд зображення"""
        if not hasattr(self, 'preview_container') or not self.current_image_b64:
            return
            
        try:
            # Очищаємо попередній контент
            self.preview_container.content.controls.clear()
            
            # Додаємо заголовок
            self.preview_container.content.controls.append(
                ft.Text(self.loc.get("properties_preview", "Попередній перегляд:"), size=16, color=ft.Colors.WHITE70, weight=ft.FontWeight.W_500)
            )
            
            # Додаємо зображення
            if "," in self.current_image_b64:
                image = ft.Image(
                    src_base64=self.current_image_b64.split(",")[1],
                    width=280,
                    height=200,
                    fit=ft.ImageFit.COVER,
                    border_radius=12,
                )
            else:
                image = ft.Image(
                    src=self.current_image_b64,
                    width=280,
                    height=200,
                    fit=ft.ImageFit.COVER,
                    border_radius=12,
                )
            
            # Кнопка видалення зображення
            remove_btn = ft.IconButton(
                icon=ft.Icons.CLOSE, 
                tooltip="Прибрати", 
                on_click=lambda e: self._clear_photo(),
                icon_color=ft.Colors.GREY_50, 
                bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )

            image_container = ft.Stack([
                ft.Container(content=image, border_radius=12, border=ft.border.all(1, ft.Colors.GREY_600)),
                ft.Container(content=remove_btn, right=6, top=6),
            ], width=280, height=200)
            
            self.preview_container.content.controls.append(image_container)
            if self.preview_container is not None:
                try:
                    self.preview_container.visible = True
                except Exception:
                    pass
            
            # Вмикаємо скрол лише коли є прев'ю
            if hasattr(self, 'form_body'):
                self.form_body.scroll = ft.ScrollMode.ADAPTIVE
            
            # Оновлюємо сторінку
            if self.page:
                self.page.update()
        except Exception:
            pass
            # Якщо помилка — ховаємо блок прев'ю
            if hasattr(self, 'preview_container') and self.preview_container is not None:
                try:
                    if hasattr(self.preview_container, 'visible') and hasattr(self.preview_container, '_set_attr_internal'):
                        self.preview_container.visible = False
                except Exception:
                    pass
            if hasattr(self, 'form_body'):
                self.form_body.scroll = None
            if self.page:
                self.page.update()

    def _confirm_restore_sync(self, prop: dict):
        """Створює діалог підтвердження повернення - спрощена версія"""
        try:
            logger.info(f"🔄 Creating restore confirmation dialog for property: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")

            # Перевіряємо профіль
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile found")
                return

            logger.info(f"✅ Profile found: {profile.get('name', 'Unknown')}")

            if not self.page:
                logger.error("❌ Page is None")
                return

            # Очищаємо overlay перед створенням діалогу
            logger.info("🔧 Cleaning overlay before creating dialog...")
            self._simple_overlay_cleanup()

            # Створюємо діалог підтвердження
            confirm_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(self.loc.get("properties_restore_property", default="Повернути майно?")),
                content=ft.Text(f"{self.loc.get('properties_restore_confirm', 'Ви дійсно хочете повернути')} '{prop.get('name', '')}' {self.loc.get('properties_restore_to_active', 'в активне майно')}?"),
                actions=[
                    ft.TextButton("Скасувати", on_click=lambda e: self._handle_cancel_restore(confirm_dialog)),
                    ft.TextButton("Повернути", on_click=lambda e: self._handle_confirm_restore(prop, confirm_dialog)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            logger.info("🔧 Setting up restore confirmation dialog...")

            # Додаємо діалог до overlay
            self.page.overlay.append(confirm_dialog)
            confirm_dialog.open = True

            # Оновлюємо сторінку
            self.page.update()

            logger.info("✅ Restore confirmation dialog opened successfully")

        except Exception as e:
            logger.error(f"❌ Error in _confirm_restore_sync: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")

            # При помилці також очищаємо overlay
            try:
                self._simple_overlay_cleanup()
            except:
                pass

    def _handle_cancel_restore(self, dialog: ft.AlertDialog):
        """Обробляє кнопку 'Скасувати' в діалозі повернення"""
        try:
            logger.info("🔘 Button 'Скасувати' clicked in dialog")

            # Закриваємо діалог і очищаємо overlay
            dialog.open = False
            if dialog in self.page.overlay:
                self.page.overlay.remove(dialog)
            self.page.update()

            logger.info("✅ Restore dialog cancelled")
        except Exception as e:
            logger.error(f"❌ Error in _handle_cancel_restore: {e}")
            # Аварійне очищення при помилці
            try:
                self._simple_overlay_cleanup()
            except:
                pass

    def _handle_confirm_restore(self, prop: dict, dialog: ft.AlertDialog):
        """Обробляє кнопку 'Повернути' в діалозі повернення"""
        try:
            logger.info("🔘 Button 'Повернути' clicked in dialog")

            # НЕ закриваємо діалог тут - це зробить функція повернення
            # Просто запускаємо процес повернення
            self._handle_perform_restore_wrapper(prop, dialog)

        except Exception as e:
            logger.error(f"❌ Error in _handle_confirm_restore: {e}")
            # При помилці закриваємо діалог і очищаємо overlay
            try:
                dialog.open = False
                if dialog in self.page.overlay:
                    self.page.overlay.remove(dialog)
                self.page.update()
                self._simple_overlay_cleanup()
            except:
                pass

    async def _confirm_restore_async(self, prop: dict):
        """Асинхронно створює діалог підтвердження повернення"""
        try:
            logger.info(f"🔄 Starting restore confirmation for property: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile found")
                await self._toast(self.loc.get("properties_profile_not_found", default="Профіль не знайдено"), error=True)
                return
            
            logger.info(f"✅ Profile found: {profile.get('name', 'Unknown')}")
            
            # Створюємо діалог підтвердження
            confirm_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(self.loc.get("properties_restore_property", default="Повернути майно?")),
                content=ft.Text(f"{self.loc.get('properties_restore_confirm', 'Ви дійсно хочете повернути')} '{prop.get('name', '')}' {self.loc.get('properties_restore_to_active', 'в активне майно')}?"),
                actions=[
                    ft.TextButton("Скасувати", on_click=lambda e: self._close_dialog_sync(confirm_dialog)),
                    ft.TextButton("Повернути", on_click=lambda e: self._handle_perform_restore_wrapper(prop, confirm_dialog)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            if self.page:
                # Додаємо діалог до overlay
                self.page.overlay.append(confirm_dialog)
                confirm_dialog.open = True
                self.page.update()
                logger.info("✅ Restore confirmation dialog opened")
            else:
                logger.error("❌ Page is None in _confirm_restore_async")
                
        except Exception as e:
            logger.error(f"❌ Error in _confirm_restore_async: {e}")
            await self._toast(f"{self.loc.get('properties_error', default='Помилка:')} {str(e)}", error=True)

    async def _handle_perform_restore(self, prop: dict, dialog: ft.AlertDialog):
        """Виконує повернення майна з проданого в активне - переписано з нуля"""
        logger.info(f"🔄 Starting property restore for: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")

        try:
            # 1. Перевіряємо профіль
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile found")
                await self._show_error_toast("Профіль не знайдено")
                return

            logger.info(f"✅ Profile found: {profile.get('name', 'Unknown')}")

            # 2. НЕ закриваємо діалог тут - зробимо це після всіх операцій
            # Це запобігає проблемам з overlay

            # 3. Виконуємо повернення через сервіс
            logger.info("🔄 Executing property restore service...")
            success = await SafeAsyncExecutor.execute(
                self.property_service.restore_property,
                prop.get("id")
            )

            if not success:
                logger.error("❌ Property restore service failed")
                await self._show_error_toast("Помилка при поверненні майна")
                return

            logger.info("✅ Property restore service completed successfully")

            # 4. Тепер закриваємо діалог після успішного виконання операції
            logger.info("🔄 Closing dialog after successful restore...")
            await self._close_dialog(dialog)

            # 5. Очищаємо весь overlay перед оновленням UI
            logger.info("🔄 Cleaning overlay before UI update...")
            self._simple_overlay_cleanup()

            # 6. Оновлюємо дані
            logger.info("🔄 Updating data and cache...")
            # property_cache.invalidate_properties(profile["id"])  # Видалено після очищення
            self.app_state.notify_transactions_change()

            # 7. Переключаємося на вкладку "active" якщо зараз на "sold"
            if self.selected_tab == "sold":
                logger.info("🔄 Switching to active tab after restore...")
                await self.switch_tab("active", force=True)
            else:
                # 8. Оновлюємо UI для поточної вкладки з примусовим оновленням
                logger.info("🔄 Refreshing UI for current tab...")
                await self._refresh_list(force_refresh=True)

            # 9. Показуємо повідомлення про успіх
            logger.info("✅ Property restored successfully")
            await self._show_success_toast("Майно повернуто в активне")

        except Exception as e:
            logger.error(f"❌ Error in property restore: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")

            # При помилці закриваємо діалог і очищаємо overlay
            try:
                await self._close_dialog(dialog)
                self._simple_overlay_cleanup()
            except:
                pass

            await self._show_error_toast(f"Помилка при поверненні: {str(e)}")

    async def _show_success_toast(self, message: str):
        """Показує повідомлення про успіх"""
        try:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=ft.Colors.GREEN_700
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error showing success toast: {e}")

    async def _show_error_toast(self, message: str):
        """Показує повідомлення про помилку"""
        try:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=ft.Colors.RED_700
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error showing error toast: {e}")

    def _handle_restore_click(self, prop: dict):
        """Обробляє клік по кнопці повернення - нова сучасна реалізація"""
        try:
            logger.info(f"🔄 Restore button clicked for property: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            
            if not self.page:
                logger.error("❌ Page is None")
                return
                
            # Запускаємо асинхронний процес повернення
            self.page.run_task(self._restore_property_async, prop)
            
        except Exception as e:
            logger.error(f"❌ Error in _handle_restore_click: {e}")

    async def _restore_property_async(self, prop: dict):
        """Сучасна асинхронна реалізація повернення майна"""
        try:
            logger.info(f"🔄 Starting modern property restore for: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            
            # 1. Перевіряємо профіль
            profile = self.app_state.current_profile
            if not profile:
                logger.error("❌ No current profile found")
                await self._show_toast("Профіль не знайдено", error=True)
                return

            # 2. Показуємо діалог підтвердження
            confirmed = await self._show_restore_confirmation(prop)
            if not confirmed:
                logger.info("🔄 Restore cancelled by user")
                return

            # 3. Показуємо індикатор завантаження
            await self._show_loading_indicator("Повертаємо майно...")

            # 4. Виконуємо повернення
            success = await self._perform_restore_operation(prop, profile)
            if not success:
                await self._hide_loading_indicator()
                await self._show_toast("Помилка при поверненні майна", error=True)
                return

            # 5. Оновлюємо дані та кеш
            await self._update_data_after_restore(profile)

            # 6. Переключаємося на активну вкладку
            await self._switch_to_active_tab()

            # 7. Приховуємо індикатор завантаження
            await self._hide_loading_indicator()

            # 8. Показуємо повідомлення про успіх
            await self._show_toast("Майно успішно повернуто в активне", success=True)

            logger.info("✅ Property restore completed successfully")

        except Exception as e:
            logger.error(f"❌ Error in _restore_property_async: {e}")
            await self._hide_loading_indicator()
            await self._show_toast(f"Помилка: {str(e)}", error=True)

    async def _show_restore_confirmation(self, prop: dict) -> bool:
        """Показує діалог підтвердження повернення"""
        try:
            # Створюємо діалог
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(self.loc.get("properties_restore_property", default="Повернути майно?")),
                content=ft.Text(f"{self.loc.get('properties_restore_confirm', 'Ви дійсно хочете повернути')} '{prop.get('name', '')}' {self.loc.get('properties_restore_to_active', 'в активне майно')}?"),
                actions=[
                    ft.TextButton(self.loc.get("properties_cancel", default="Скасувати"), on_click=lambda e: self._close_dialog_sync(dialog, False)),
                    ft.TextButton("Повернути", on_click=lambda e: self._close_dialog_sync(dialog, True)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            # Додаємо до overlay
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()

            # Очікуємо результат
            result = await self._wait_for_dialog_result(dialog)
            
            # Очищаємо overlay
            self._simple_overlay_cleanup()
            
            return result

        except Exception as e:
            logger.error(f"❌ Error in _show_restore_confirmation: {e}")
            return False

    async def _wait_for_dialog_result(self, dialog: ft.AlertDialog) -> bool:
        """Очікує результат діалогу"""
        try:
            # Очікуємо поки діалог закриється
            while dialog.open:
                await asyncio.sleep(0.1)
            
            # Повертаємо результат
            return getattr(dialog, '_result', False)
        except Exception as e:
            logger.error(f"❌ Error in _wait_for_dialog_result: {e}")
            return False

    async def _show_loading_indicator(self, message: str):
        """Показує індикатор завантаження"""
        try:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Row([
                        ft.ProgressRing(width=16, height=16, stroke_width=2),
                        ft.Text(message)
                    ], spacing=10),
                    bgcolor=ft.Colors.BLUE_700
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error in _show_loading_indicator: {e}")

    async def _hide_loading_indicator(self):
        """Приховує індикатор завантаження"""
        try:
            if self.page and self.page.snack_bar:
                self.page.snack_bar.open = False
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error in _hide_loading_indicator: {e}")

    async def _perform_restore_operation(self, prop: dict, profile: dict) -> bool:
        """Виконує операцію повернення майна"""
        try:
            logger.info(f"🔄 Performing restore operation for property: {prop.get('name', 'Unknown')}")
            
            # Виконуємо повернення через сервіс
            success = await SafeAsyncExecutor.execute(
                self.property_service.restore_property,
                prop.get("id")
            )

            if success:
                logger.info("✅ Restore operation completed successfully")
                return True
            else:
                logger.error("❌ Restore operation failed")
                return False

        except Exception as e:
            logger.error(f"❌ Error in _perform_restore_operation: {e}")
            return False

    async def _update_data_after_restore(self, profile: dict):
        """Оновлює дані та кеш після повернення"""
        try:
            logger.info("🔄 Updating data and cache after restore...")
            
            # Інвалідуємо кеш
            # property_cache.invalidate_properties(profile["id"])  # Видалено після очищення
            
            # Повідомляємо про зміни
            self.app_state.notify_transactions_change()
            
            logger.info("✅ Data and cache updated successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in _update_data_after_restore: {e}")

    async def _switch_to_active_tab(self):
        """Переключається на активну вкладку"""
        try:
            logger.info("🔄 Switching to active tab...")
            
            if self.selected_tab != "active":
                await self.switch_tab("active", force=True)
            else:
                # Якщо вже на активній вкладці, просто оновлюємо дані
                await self._refresh_list(force_refresh=True)
            
            logger.info("✅ Switched to active tab successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in _switch_to_active_tab: {e}")

    async def _show_toast(self, message: str, error: bool = False, success: bool = False):
        """Показує повідомлення користувачу"""
        try:
            if self.page:
                bgcolor = ft.Colors.RED_700 if error else (ft.Colors.GREEN_700 if success else ft.Colors.BLUE_700)
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=bgcolor
                )
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as e:
            logger.error(f"❌ Error in _show_toast: {e}")

    def _test_dialog_sync(self):
        """Створює простий тестовий діалог для перевірки кнопок"""
        try:
            logger.info("🧪 Creating test dialog")
            
            # Спробуємо Banner замість AlertDialog
            test_banner = ft.Banner(
                bgcolor=ft.Colors.AMBER_100,
                leading=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER, size=20),
                content=ft.Text(
                    "Це тестовий банер для перевірки кнопок"
                ),
                actions=[
                    ft.TextButton("Тест 1", on_click=lambda e: logger.info("🔘 Test button 1 clicked")),
                    ft.TextButton("Тест 2", on_click=lambda e: logger.info("🔘 Test button 2 clicked")),
                ],
            )
            
            if self.page:
                self.page.banner = test_banner
                test_banner.open = True
                self.page.update()
                logger.info("✅ Test banner opened")
            else:
                logger.error("❌ Page is None in _test_dialog_sync")
                
        except Exception as e:
            logger.error(f"❌ Error in _test_dialog_sync: {e}")

    def _handle_perform_restore_wrapper(self, prop: dict, dialog: ft.AlertDialog):
        """Wrapper для виклику асинхронного методу повернення"""
        try:
            logger.info(f"🔄 _handle_perform_restore_wrapper called for property: {prop.get('name', 'Unknown')} (ID: {prop.get('id')})")
            if self.page:
                self.page.run_task(self._handle_perform_restore, prop, dialog)
                logger.info("✅ Task scheduled successfully")
            else:
                logger.error("❌ Page is None in _handle_perform_restore_wrapper")
        except Exception as e:
            logger.error(f"❌ Error in _handle_perform_restore_wrapper: {e}")

    def _on_sold_card_click(self, e):
        """Обробляє клік по картці проданого майна"""
        try:
            # Знаходимо Container всередині GestureDetector
            container = e.control.content
            if hasattr(container, 'opacity'):
                # При кліку робимо картку кольоровою назавжди
                container.opacity = 1.0
                logger.info("✅ Card opacity set to 1.0")
                
                # Також прибираємо сірий фільтр з зображень
                self._remove_gray_filter_from_images(container)
                logger.info("✅ Gray filter removal completed")
                
                if self.page:
                    self.page.update()
                    logger.info("✅ Page updated after click")
        except Exception as ex:
            logger.error(f"Error in _on_sold_card_click: {ex}")

    def _remove_gray_filter_from_images(self, container):
        """Прибирає сірий фільтр з усіх зображень в контейнері"""
        try:
            # Перевіряємо сам контейнер
            if isinstance(container, ft.Image):
                container.color = None
                container.color_blend_mode = None
                logger.info("✅ Removed gray filter from direct Image")
                return
            
            # Перевіряємо content контейнера
            if hasattr(container, 'content'):
                if isinstance(container.content, ft.Image):
                    container.content.color = None
                    container.content.color_blend_mode = None
                    logger.info("✅ Removed gray filter from Image in content")
                else:
                    # Рекурсивно перевіряємо content
                    self._remove_gray_filter_from_images(container.content)
            
            # Перевіряємо controls якщо є
            if hasattr(container, 'controls'):
                for control in container.controls:
                    self._remove_gray_filter_from_images(control)
                    
        except Exception as ex:
            logger.error(f"Error removing gray filter: {ex}")
    
    async def _on_lang_change(self, lang_code: str):
        """Обробник зміни мови"""
        # Викликаємо базовий метод
        await super()._on_lang_change(lang_code)
        
        # Оновлюємо заголовок сторінки
        if hasattr(self, 'page_title_text'):
            self.page_title_text.value = self.loc.get("properties_title", default="Майно")
        
        # Легке оновлення локалізації без перезавантаження даних
        self._update_localization()
        
        # Пересоздаємо всі карточки майна з новими перекладами
        await self._recreate_cards_with_new_language()
        
        if self.page:
            self.page.update()
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        try:
            # Закриваємо всі діалоги майна
            dialog_attributes = [
                'add_property_dialog', 'edit_property_dialog', 'sell_property_dialog',
                'confirm_delete_dialog', 'confirm_restore_dialog'
            ]
            
            for attr_name in dialog_attributes:
                if hasattr(self, attr_name):
                    dialog = getattr(self, attr_name)
                    if dialog and hasattr(dialog, 'open'):
                        dialog.open = False
            
            # Викликаємо базовий метод для закриття загальних діалогів
            super()._close_all_dialogs()
        except Exception as e:
            print(f"Error closing property dialogs: {e}")
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # Відновлюємо фокус на активному текстовому полі
            if hasattr(self, 'sell_price_input') and self.sell_price_input:
                self.sell_price_input.focus()
            elif hasattr(self, 'sell_notes_input') and self.sell_notes_input:
                self.sell_notes_input.focus()
            elif hasattr(self, 'input_name') and self.input_name:
                self.input_name.focus()
            elif hasattr(self, 'input_price') and self.input_price:
                self.input_price.focus()
            else:
                # Fallback до базового методу
                super()._restore_focus()
        except Exception as e:
            print(f"Error restoring focus in properties view: {e}")
    
    def _update_localization(self):
        """Оновлює переклади при зміні мови"""
        try:
            # Оновлюємо заголовки та кнопки
            if hasattr(self, 'total_label'):
                self.total_label.value = self.loc.get("properties_total_value", default="Загальна вартість:")
            
            if hasattr(self, 'btn_tab_active') and self.btn_tab_active and hasattr(self.btn_tab_active, 'content') and self.btn_tab_active.content:
                self.btn_tab_active.content.value = self.loc.get("properties_tab_active", default="Активне")
                # Динамічно встановлюємо ширину залежно від мови
                current_lang = self.loc.current_language
                if current_lang == 'ru':
                    self.btn_tab_active.width = 150  # Більше місця для російської
                else:
                    self.btn_tab_active.width = 140
            
            if hasattr(self, 'btn_tab_sold') and self.btn_tab_sold and hasattr(self.btn_tab_sold, 'content') and self.btn_tab_sold.content:
                self.btn_tab_sold.content.value = self.loc.get("properties_tab_sold", default="Продане")
                # Динамічно встановлюємо ширину залежно від мови
                current_lang = self.loc.current_language
                if current_lang == 'ru':
                    self.btn_tab_sold.width = 150  # Більше місця для російської
                else:
                    self.btn_tab_sold.width = 140
            
            # Оновлюємо кнопку додавання
            if hasattr(self, 'add_button'):
                self.add_button.text = self.loc.get("properties_add_new", default="Додати майно")
            
            # Оновлюємо загальну вартість (заголовок)
            if hasattr(self, 'total_label'):
                self.total_label.value = self.loc.get("properties_total_value", default="Загальна вартість:")
            
            # Оновлюємо діалоги, якщо вони відкриті
            self._update_dialog_localization()
            
            # Оновлюємо всі картки майна (якщо вони відрендерені)
            self._update_cards_localization()
            
            # Оновлюємо dashboard статистики
            self._update_dashboard_localization()
            
            # Оновлюємо placeholder повідомлення
            self._update_placeholder_localization()
            
            # Оновлюємо повідомлення про помилки
            self._update_error_messages_localization()
            
            # Оновлюємо snackbar повідомлення
            self._update_snackbar_localization()
                
        except Exception as ex:
            logger.error(f"Error updating localization in PropertiesView: {ex}")
    
    def _update_cards_localization(self):
        """Оновлює переклади в картках майна"""
        try:
            # Оновлюємо tooltip'и кнопок
            if hasattr(self, 'list_container') and hasattr(self.list_container, 'content'):
                self._update_cards_content_localization(self.list_container.content)
            
            # Оновлюємо всі карточки майна
            self._update_all_cards()
        except Exception as ex:
            logger.error(f"Error updating cards localization: {ex}")
    
    def _update_all_cards(self):
        """Оновлює всі карточки майна при зміні мови"""
        try:
            # Оновлюємо карточки в list_container
            if hasattr(self, 'list_container') and hasattr(self.list_container, 'content'):
                self._update_cards_in_container(self.list_container.content)
        except Exception as ex:
            logger.error(f"Error updating all cards: {ex}")
    
    def _update_cards_in_container(self, content):
        """Рекурсивно оновлює карточки в контейнері"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо Text елементи в картках
                    if isinstance(control, ft.Text):
                        if hasattr(control, 'value'):
                            # Оновлюємо дати
                            if "Додано:" in control.value:
                                # Зберігаємо дату, але оновлюємо префікс
                                parts = control.value.split(" ", 1)
                                if len(parts) > 1:
                                    control.value = f"{self.loc.get('properties_added_date', default='Додано:')} {parts[1]}"
                            elif "Невідомо" in control.value:
                                control.value = control.value.replace("Невідомо", self.loc.get("properties_unknown", default="Невідомо"))
                            elif "Немає фото" in control.value:
                                control.value = self.loc.get("properties_no_photo", default="Немає фото")
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_cards_in_container(control)
        except Exception as ex:
            logger.error(f"Error updating cards in container: {ex}")
    
    def _update_dashboard_localization(self):
        """Оновлює переклади в dashboard статистиках"""
        try:
            # Оновлюємо dashboard в list_container
            if hasattr(self, 'list_container') and hasattr(self.list_container, 'content'):
                self._update_dashboard_in_container(self.list_container.content)
        except Exception as ex:
            logger.error(f"Error updating dashboard localization: {ex}")
    
    def _update_dashboard_in_container(self, content):
        """Рекурсивно оновлює dashboard статистики в контейнері"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо Text елементи в dashboard
                    if isinstance(control, ft.Text):
                        if hasattr(control, 'value'):
                            # Оновлюємо статистики
                            if "Загальний прибуток" in control.value:
                                control.value = self.loc.get("properties_total_profit", default="Загальний прибуток")
                            elif "Середня рентабельність" in control.value:
                                control.value = self.loc.get("properties_avg_profitability", default="Середня рентабельність")
                            elif "Продано майна" in control.value:
                                control.value = self.loc.get("properties_sold_count", default="Продано майна")
                            elif "Успішних угод" in control.value:
                                control.value = self.loc.get("properties_successful_deals", default="Успішних угод")
                            elif "Загальна вартість" in control.value:
                                control.value = self.loc.get("properties_total_value_active", default="Загальна вартість")
                            elif "Активне майно" in control.value:
                                control.value = self.loc.get("properties_active_count", default="Активне майно")
                            elif "Середня вартість" in control.value:
                                control.value = self.loc.get("properties_avg_value", default="Середня вартість")
                            elif "Потенційний прибуток" in control.value:
                                control.value = self.loc.get("properties_potential_profit", default="Потенційний прибуток")
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_dashboard_in_container(control)
        except Exception as ex:
            logger.error(f"Error updating dashboard in container: {ex}")
    
    def _update_placeholder_localization(self):
        """Оновлює переклади в placeholder повідомленнях"""
        try:
            # Оновлюємо placeholder в list_container
            if hasattr(self, 'list_container') and hasattr(self.list_container, 'content'):
                self._update_placeholder_in_container(self.list_container.content)
        except Exception as ex:
            logger.error(f"Error updating placeholder localization: {ex}")
    
    def _update_placeholder_in_container(self, content):
        """Рекурсивно оновлює placeholder повідомлення в контейнері"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо Text елементи в placeholder
                    if isinstance(control, ft.Text):
                        if hasattr(control, 'value'):
                            # Оновлюємо повідомлення
                            if "Немає майна" in control.value:
                                control.value = self.loc.get("properties_list_empty", default="Немає майна")
                            elif "Немає проданого майна" in control.value:
                                control.value = self.loc.get("properties_list_empty_sold", default="Немає проданого майна")
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_placeholder_in_container(control)
        except Exception as ex:
            logger.error(f"Error updating placeholder in container: {ex}")
    
    def _update_error_messages_localization(self):
        """Оновлює переклади в повідомленнях про помилки"""
        try:
            # Оновлюємо повідомлення про помилки в list_container
            if hasattr(self, 'list_container') and hasattr(self.list_container, 'content'):
                self._update_error_messages_in_container(self.list_container.content)
        except Exception as ex:
            logger.error(f"Error updating error messages localization: {ex}")
    
    def _update_error_messages_in_container(self, content):
        """Рекурсивно оновлює повідомлення про помилки в контейнері"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо Text елементи в повідомленнях про помилки
                    if isinstance(control, ft.Text):
                        if hasattr(control, 'value'):
                            # Оновлюємо повідомлення про помилки
                            if "Помилка завантаження:" in control.value:
                                # Зберігаємо деталі помилки, але оновлюємо префікс
                                parts = control.value.split(":", 1)
                                if len(parts) > 1:
                                    control.value = f"{self.loc.get('properties_loading_error', default='Помилка завантаження:')}{parts[1]}"
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_error_messages_in_container(control)
        except Exception as ex:
            logger.error(f"Error updating error messages in container: {ex}")
    
    def _update_snackbar_localization(self):
        """Оновлює переклади в snackbar повідомленнях"""
        try:
            # Оновлюємо snackbar в page overlay
            if self.page and hasattr(self.page, 'overlay'):
                for overlay_item in self.page.overlay:
                    if isinstance(overlay_item, ft.SnackBar):
                        if hasattr(overlay_item, 'content') and hasattr(overlay_item.content, 'value'):
                            # Оновлюємо повідомлення в snackbar
                            if "В буфері обміну немає зображення" in overlay_item.content.value:
                                overlay_item.content.value = self.loc.get("properties_clipboard_no_image", default="В буфері обміну немає зображення")
                            elif "Зображення вставлено з буфера обміну!" in overlay_item.content.value:
                                overlay_item.content.value = self.loc.get("properties_image_pasted", default="Зображення вставлено з буфера обміну!")
                            elif "Фото додано успішно!" in overlay_item.content.value:
                                overlay_item.content.value = self.loc.get("properties_photo_added_success", default="Фото додано успішно!")
        except Exception as ex:
            logger.error(f"Error updating snackbar localization: {ex}")
    
    async def _recreate_cards_with_new_language(self):
        """Пересоздає всі карточки майна з новими перекладами"""
        try:
            if not hasattr(self, 'list_container') or not self.list_container:
                return
            
            # Отримуємо поточний стан
            current_tab = self.selected_tab
            
            # Пересоздаємо контент для поточної вкладки
            if current_tab == "active":
                await self._refresh_active_list()
            elif current_tab == "sold":
                await self._refresh_sold_list()
                
        except Exception as ex:
            logger.error(f"Error recreating cards with new language: {ex}")
    
    async def _refresh_active_list(self):
        """Оновлює список активного майна з новими перекладами"""
        try:
            if hasattr(self, '_active_props_cache') and self._active_props_cache:
                content = await self._build_active_list(self._active_props_cache)
                if self.list_container:
                    self.list_container.content = content
        except Exception as ex:
            logger.error(f"Error refreshing active list: {ex}")
    
    async def _refresh_sold_list(self):
        """Оновлює список проданого майна з новими перекладами"""
        try:
            # Отримуємо дані проданого майна з бази даних
            profile = self.app_state.current_profile
            if profile:
                sold_props = await self.property_service.get_properties(profile["id"], "sold")
                content = self._build_sold_list(sold_props)
                if self.list_container:
                    self.list_container.content = content
        except Exception as ex:
            logger.error(f"Error refreshing sold list: {ex}")
    
    def _update_cards_content_localization(self, content):
        """Рекурсивно оновлює переклади в контенті карток"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо IconButton tooltip'и
                    if isinstance(control, ft.IconButton):
                        if hasattr(control, 'tooltip'):
                            if "Повернути в активне" in control.tooltip:
                                control.tooltip = self.loc.get("properties_restore_to_active", default="Повернути в активне")
                            elif "Видалити назавжди" in control.tooltip:
                                control.tooltip = self.loc.get("properties_delete_forever", default="Видалити назавжди")
                            elif "Продати" in control.tooltip:
                                control.tooltip = self.loc.get("properties_sell_button", default="Продати")
                            elif "Редагувати" in control.tooltip:
                                control.tooltip = self.loc.get("properties_action_edit", default="Редагувати")
                            elif "Видалити" in control.tooltip:
                                control.tooltip = self.loc.get("properties_action_delete", default="Видалити")
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_cards_content_localization(control)
        except Exception as ex:
            logger.error(f"Error updating cards content localization: {ex}")
    
    def _update_dialog_localization(self):
        """Оновлює переклади в відкритих діалогах"""
        try:
            if not self.page or not hasattr(self.page, 'overlay'):
                return
                
            # Оновлюємо всі AlertDialog в overlay
            for overlay_item in self.page.overlay:
                if isinstance(overlay_item, ft.AlertDialog):
                    # Оновлюємо заголовок діалогу
                    if hasattr(overlay_item, 'title') and hasattr(overlay_item.title, 'value'):
                        if "Додати" in overlay_item.title.value and "майно" in overlay_item.title.value.lower():
                            overlay_item.title.value = self.loc.get("properties_add_dialog_title", default="Додати майно")
                        elif "Редагувати" in overlay_item.title.value and "майно" in overlay_item.title.value.lower():
                            overlay_item.title.value = self.loc.get("properties_edit_dialog_title", default="Редагувати майно")
                        elif "Продати" in overlay_item.title.value and "майно" in overlay_item.title.value.lower():
                            overlay_item.title.value = self.loc.get("properties_sell_dialog_title", default="Продати майно")
                    
                    # Оновлюємо поля вводу в діалозі
                    if hasattr(overlay_item, 'content') and hasattr(overlay_item.content, 'controls'):
                        self._update_dialog_content_localization(overlay_item.content)
                        
        except Exception as ex:
            logger.error(f"Error updating dialog localization: {ex}")
    
    def _update_dialog_content_localization(self, content):
        """Рекурсивно оновлює переклади в контенті діалогу"""
        try:
            if hasattr(content, 'controls'):
                for control in content.controls:
                    # Оновлюємо TextField
                    if isinstance(control, ft.TextField):
                        if hasattr(control, 'label'):
                            if "Назва майна" in control.label:
                                control.label = self.loc.get("properties_name_label", default="Назва майна")
                            elif "Ціна" in control.label:
                                control.label = self.loc.get("properties_price_label", default="Ціна")
                    
                    # Оновлюємо Text елементи
                    elif isinstance(control, ft.Text):
                        if hasattr(control, 'value'):
                            if "Попередній перегляд" in control.value:
                                control.value = self.loc.get("properties_preview", default="Попередній перегляд:")
                            elif "Немає зображення" in control.value:
                                control.value = self.loc.get("properties_no_image", default="Немає зображення")
                            elif "Розрахунок маржі" in control.value:
                                control.value = self.loc.get("properties_margin_calculation", default="Розрахунок маржі:")
                            elif "Додано:" in control.value:
                                control.value = control.value.replace("Додано:", self.loc.get("properties_added_date", default="Додано:"))
                            elif "Невідомо" in control.value:
                                control.value = control.value.replace("Невідомо", self.loc.get("properties_unknown", default="Невідомо"))
                    
                    # Оновлюємо кнопки
                    elif isinstance(control, ft.ElevatedButton):
                        if hasattr(control, 'text'):
                            if control.text == "Зберегти":
                                control.text = self.loc.get("common_save", default="Зберегти")
                            elif control.text == "Скасувати":
                                control.text = self.loc.get("properties_cancel", default="Скасувати")
                            elif control.text == "Додати":
                                control.text = self.loc.get("properties_add", default="Додати")
                            elif control.text == "Продати":
                                control.text = self.loc.get("properties_sell", default="Продати")
                            elif control.text == "Додати фото":
                                control.text = self.loc.get("properties_add_photo", default="Додати фото")
                            elif control.text == "Вставити з буфера":
                                control.text = self.loc.get("properties_paste_from_clipboard", default="Вставити з буфера")
                    
                    # Рекурсивно обробляємо вкладені елементи
                    elif hasattr(control, 'controls'):
                        self._update_dialog_content_localization(control)
                        
        except Exception as ex:
            logger.error(f"Error updating dialog content localization: {ex}")
    