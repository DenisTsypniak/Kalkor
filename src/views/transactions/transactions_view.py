# --- START OF FILE src/views/transactions/transactions_view.py ---

import flet as ft
from functools import partial
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Callable, Any
import asyncio
import re

from src.app.app_state import AppState
from src.data import data_manager as dm
from src.utils import config as cfg
from src.utils.ui.helpers import format_number, create_amount_display
from src.utils.localization import LocalizationManager
from src.views.base_view import BaseView

# Імпортуємо нові системи
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors
from src.utils.validators import DataValidator
from src.utils.virtualized_list import VirtualizedList, VirtualizationConfig

logger = get_logger(__name__)



class TransactionsView(BaseView):
    _OTHER_CATEGORY_KEY = "##OTHER_INTERNAL_KEY##"
    TRANSACTIONS_PER_PAGE = 20

    def __init__(self, app_state: AppState, toggle_global_calculator_func: Callable, loc: LocalizationManager):
        super().__init__(app_state, loc, visible=False, expand=True)
        self.toggle_global_calculator_func = toggle_global_calculator_func
        self.time_filter = cfg.TIME_FILTER_ALL
        self.is_first_load = True
        self.category_to_delete = None
        self.dialog_selected_type = cfg.TRANSACTION_TYPE_INCOME
        
        # Ініціалізуємо нові системи
        self.validator = DataValidator()
        self.category_type_to_add = None
        self.current_balance = 0.0
        self.editing_transaction_id: int | None = None
        self.hovered_category_name: str | None = None
        self.small_items_cache = []
        self.large_items_cache = []
        self.is_legend_expanded = False
        
        # Ініціалізуємо VirtualizedList
        self.virtualized_list = None
        self.virtualization_config = VirtualizationConfig(
            item_height=80,
            container_height=400,
            buffer_size=5,
            scroll_threshold=0.1
        )

        self.merge_source_categories: list[ft.Checkbox] = []
        self.merge_target_name_field: ft.TextField | None = None
        self.merge_dialog_button: ft.ElevatedButton | None = None

        self.current_offset = 0
        self.has_more_transactions = True
        self.is_loading_more = False

        # Змінні для заголовків (для оновлення локалізації)
        self.stats_title_text = None
        self.history_title_text = None
        self.chart_title_text = None
        self.date_header_text = None
        self.type_header_text = None
        self.category_header_text = None
        self.amount_header_text = None
        self.actions_header_text = None

        self.load_more_button = ft.ElevatedButton(
            text=self.loc.get("load_more_button", default="Завантажити ще"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self.load_more_transactions,
            visible=True
        )
        self.loading_more_indicator = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self.load_more_container = ft.Container(
            content=ft.Row(
                controls=[self.loading_more_indicator, self.load_more_button],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10
            ),
            padding=ft.padding.only(top=10, bottom=10),
            visible=False
        )

        # --- КЛЮЧОВА ЗМІНА: UI більше не будується в __init__ ---
        self._is_built = False
        self.app_state.register_on_profile_change(self.handle_profile_change)
        self.app_state.register_on_language_change(self._on_lang_change)
        # Оновлюємо історію, коли інші екрани додають/видаляють транзакції
        self.app_state.register_on_transactions_change(self._on_transactions_change)

    async def on_view_show(self):
        """Викликається при показі view"""
        try:
            # Викликаємо базовий метод
            await super().on_view_show()
            
            # Перевіряємо чи маємо необхідні атрибути
            if not hasattr(self, '_set_attr_internal'):
                return
                
            if not self._is_built:
                self._rebuild_full_view()
                self._is_built = True
            await self._setup_overlays()
            await self.refresh_data()
        except Exception:
            pass

    async def on_view_hide(self):
        """Викликається при приховуванні view"""
        try:
            # Викликаємо базовий метод
            await super().on_view_hide()
            
            # Очищаємо overlay елементи (тільки ті, що належать цьому view)
            if self.page and hasattr(self.page, 'overlay'):
                try:
                    for overlay_item in self.page.overlay[:]:
                        if (isinstance(overlay_item, ft.AlertDialog) and 
                            hasattr(overlay_item, 'open') and 
                            overlay_item.open):
                            overlay_item.open = False
                except Exception:
                    pass
        except Exception:
            pass

    async def refresh_data(self):
        """Оновлює дані транзакцій"""
        try:
            if (self.app_state.current_profile and 
                self._is_built and 
                self.page and 
                hasattr(self, 'update_ui_data') and 
                self.update_ui_data is not None and
                callable(self.update_ui_data)):
                await self.update_ui_data(reset_pagination=True)
        except Exception:
            pass

    def _rebuild_full_view(self):
        """Перебудовує повний view"""
        self._create_controls()
        self._build_ui()
        self._create_dialogs()
        self.update_filter_buttons_style(update_page=False)
        self.controls.clear()
        self.controls.append(ft.Stack([self.no_profile_placeholder, self.main_content], expand=True))

    def _update_localization(self):
        # Якщо UI ще не збудовано, нічого не оновлюємо
        if not self._is_built:
            return

        self.no_profile_placeholder.content.value = self.loc.get("transactions_placeholder")
        self.balance_label_text.value = self.loc.get("transactions_balance")
        self.edit_balance_icon.tooltip = self.loc.get("transactions_edit_balance_tooltip")
        
        # Оновлення заголовків
        if self.stats_title_text:
            self.stats_title_text.value = self.loc.get("transactions_stats_title")
        if self.history_title_text:
            self.history_title_text.value = self.loc.get("transactions_history_title")
        if self.chart_title_text:
            self.chart_title_text.value = self.loc.get("transactions_chart_title")
        
        # Оновлення заголовків таблиці
        if self.date_header_text:
            self.date_header_text.value = self.loc.get("transactions_date_header")
        if self.type_header_text:
            self.type_header_text.value = self.loc.get("transactions_type_header")
        if self.category_header_text:
            self.category_header_text.value = self.loc.get("transactions_category_header")
        if self.amount_header_text:
            self.amount_header_text.value = self.loc.get("transactions_amount_header")
        if self.actions_header_text:
            self.actions_header_text.value = self.loc.get("transactions_actions_header")
        
        # Безпечне оновлення локалізації з перевіркою структури
        try:
            if hasattr(self, 'main_content') and hasattr(self.main_content, 'controls') and len(self.main_content.controls) > 0:
                main_control = self.main_content.controls[0]
                if hasattr(main_control, 'content') and hasattr(main_control.content, 'content') and hasattr(main_control.content.content, 'controls'):
                    controls = main_control.content.content.controls
                    if len(controls) > 1 and hasattr(controls[1], 'controls') and len(controls[1].controls) > 2:
                        income_column = controls[1].controls[1].content
                        expense_column = controls[1].controls[2].content
                        if hasattr(income_column, 'controls') and len(income_column.controls) > 0:
                            income_column.controls[0].value = self.loc.get("transactions_income")
                        if hasattr(expense_column, 'controls') and len(expense_column.controls) > 0:
                            expense_column.controls[0].value = self.loc.get("transactions_expense")
        except Exception as e:
            print(f"Error updating transactions localization: {e}")
        self.day_filter_button.text = self.loc.get("transactions_filter_day")
        self.week_filter_button.text = self.loc.get("transactions_filter_week")
        self.month_filter_button.text = self.loc.get("transactions_filter_month")
        self.all_time_filter_button.text = self.loc.get("transactions_filter_all")
        self.add_transaction_button.tooltip = self.loc.get("transactions_add_tooltip")
        self.calculator_button.tooltip = self.loc.get("transactions_calculator_tooltip")
        # Оновлення заголовків таблиці (якщо потрібно)
        # Ці елементи оновлюються автоматично при перебудові UI
        self.dialog_category_dropdown.label = self.loc.get("transactions_dialog_category_label")
        self.add_category_button.tooltip = self.loc.get("transactions_dialog_add_category_tooltip")
        self.dialog_calculator_button.tooltip = self.loc.get("transactions_calculator_tooltip")
        self.cancel_button.text = self.loc.get("transactions_dialog_cancel_button")
        self.edit_balance_dialog.title.value = self.loc.get("transactions_edit_balance_dialog_title")
        self.edit_balance_input.label = self.loc.get("transactions_edit_balance_dialog_label")
        self.edit_balance_dialog.actions[0].text = self.loc.get("transactions_dialog_cancel_button")
        self.edit_balance_dialog.actions[1].text = self.loc.get("transactions_edit_balance_dialog_save_button")
        self.add_category_dialog.actions[0].text = self.loc.get("transactions_dialog_cancel_button")
        self.new_category_dialog_textfield.label = self.loc.get("transactions_new_category_dialog_label")
        self.add_category_dialog.actions[1].text = self.loc.get("transactions_new_category_dialog_add_button")
        self.confirm_delete_category_dialog.title.value = self.loc.get("transactions_confirm_delete_category_title")
        self.confirm_delete_category_dialog.actions[0].text = self.loc.get("profiles_confirm_delete_yes_button")
        self.confirm_delete_category_dialog.actions[1].text = self.loc.get("profiles_confirm_delete_no_button")
        self.load_more_button.text = self.loc.get("load_more_button", default="Завантажити ще")

        self.merge_category_button.tooltip = self.loc.get("transactions_dialog_merge_category_tooltip")
        self.merge_categories_dialog.title.value = self.loc.get("transactions_merge_dialog_title")
        self.merge_target_name_field.label = self.loc.get("transactions_merge_dialog_new_name_label")
        self.merge_categories_dialog.actions[0].text = self.loc.get("transactions_dialog_cancel_button")
        self.merge_categories_dialog.actions[1].text = self.loc.get("transactions_merge_dialog_merge_button")
        self.confirm_merge_dialog.title.value = self.loc.get("transactions_merge_confirm_title")
        self.confirm_merge_dialog.actions[0].text = self.loc.get("profiles_confirm_delete_yes_button")
        self.confirm_merge_dialog.actions[1].text = self.loc.get("profiles_confirm_delete_no_button")

    async def _on_lang_change(self, lang_code: str):
        # Викликаємо базовий метод
        await super()._on_lang_change(lang_code)
        
        # Оновлюємо заголовок сторінки
        if hasattr(self, 'page_title_text'):
            self.page_title_text.value = self.loc.get("transactions_title", default="Транзакції")
        
        # Легке оновлення локалізації без перезавантаження даних, щоб уникнути мерехтіння
        self._update_localization()
        # Не перезавантажуємо дані тут, щоб не було сірої "паузи" при зміні мови
        # Дані оновляться природно при наступних діях користувача
        self.update()
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        try:
            # Закриваємо всі діалоги транзакцій
            dialog_attributes = [
                'edit_balance_dialog', 'add_category_dialog', 'confirm_delete_category_dialog',
                'merge_categories_dialog', 'new_category_dialog'
            ]
            
            for attr_name in dialog_attributes:
                if hasattr(self, attr_name):
                    dialog = getattr(self, attr_name)
                    if dialog and hasattr(dialog, 'open'):
                        dialog.open = False
            
            # Викликаємо базовий метод для закриття загальних діалогів
            super()._close_all_dialogs()
        except Exception as e:
            print(f"Error closing transaction dialogs: {e}")
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # Відновлюємо фокус на активному текстовому полі
            if hasattr(self, 'amount_input') and self.amount_input:
                self.amount_input.focus()
            elif hasattr(self, 'notes_input') and self.notes_input:
                self.notes_input.focus()
            else:
                # Fallback до базового методу
                super()._restore_focus()
        except Exception as e:
            print(f"Error restoring focus in transactions view: {e}")

    def _create_controls(self):
        self.no_profile_placeholder = ft.Container(
            content=ft.Text(self.loc.get("transactions_placeholder"), style="headlineSmall",
                            text_align=ft.TextAlign.CENTER, color=ft.Colors.ON_SURFACE_VARIANT),
            alignment=ft.alignment.center, expand=True, visible=True)
        self.stats_income = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        self.stats_expense = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        self.balance_display_text = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        self.edit_balance_icon = ft.IconButton(icon=ft.Icons.EDIT_NOTE_OUTLINED, on_click=self.open_edit_balance_dialog,
                                               tooltip=self.loc.get("transactions_edit_balance_tooltip"))
        self.balance_label_text = ft.Text(self.loc.get("transactions_balance"))
        balance_label_row = ft.Row(controls=[self.balance_label_text, self.edit_balance_icon], spacing=4,
                                   alignment=ft.MainAxisAlignment.CENTER,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.balance_view_column = ft.Column([balance_label_row, self.balance_display_text],
                                             horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self.day_filter_button = ft.ElevatedButton(self.loc.get("transactions_filter_day"),
                                                   on_click=lambda e: self.page.run_task(
                                                       self.filter_transactions_by_time, e), data=cfg.TIME_FILTER_DAY)
        self.week_filter_button = ft.ElevatedButton(self.loc.get("transactions_filter_week"),
                                                    on_click=lambda e: self.page.run_task(
                                                        self.filter_transactions_by_time, e), data=cfg.TIME_FILTER_WEEK)
        self.month_filter_button = ft.ElevatedButton(self.loc.get("transactions_filter_month"),
                                                     on_click=lambda e: self.page.run_task(
                                                         self.filter_transactions_by_time, e),
                                                     data=cfg.TIME_FILTER_MONTH)
        self.all_time_filter_button = ft.ElevatedButton(self.loc.get("transactions_filter_all"),
                                                        on_click=lambda e: self.page.run_task(
                                                            self.filter_transactions_by_time, e),
                                                        data=cfg.TIME_FILTER_ALL)
        self.time_filter_buttons = [self.day_filter_button, self.week_filter_button, self.month_filter_button,
                                    self.all_time_filter_button]
        self.history_list = ft.ListView(expand=True, auto_scroll=False, spacing=4)
        self.pie_chart = ft.PieChart(sections=[], sections_space=2, center_space_radius=45,
                                     on_chart_event=self.on_pie_chart_hover, expand=True,
                                     animate=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT))
        self.chart_legend_switcher = ft.AnimatedSwitcher(content=ft.Column(),
                                                         transition=ft.AnimatedSwitcherTransition.FADE, duration=200,
                                                         reverse_duration=100)
        self.chart_legend_container = ft.Container(content=self.chart_legend_switcher, width=180,
                                                   on_hover=self._on_legend_area_hover)
        self.main_content = ft.Column(visible=False, expand=True, spacing=20, scroll=ft.ScrollMode.ADAPTIVE)
        self.main_content.padding = ft.padding.only(left=20, top=20, bottom=20, right=20)

        self.add_transaction_button = ft.IconButton(icon=ft.Icons.ADD, tooltip=self.loc.get("transactions_add_tooltip"),
                                                    on_click=self.open_transaction_dialog, icon_color=ft.Colors.WHITE,
                                                    bgcolor=ft.Colors.GREEN_700, icon_size=24)
        self.calculator_button = ft.IconButton(icon=ft.Icons.CALCULATE_OUTLINED,
                                               tooltip=self.loc.get("transactions_calculator_tooltip"),
                                               on_click=lambda e: self.page.run_task(self.toggle_global_calculator_func,
                                                                                     e, None, None),
                                               icon_color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_GREY_700,
                                               icon_size=24)

    def _build_ui(self):
        stats_content_row = ft.Row(
            controls=[ft.Container(content=self.balance_view_column, expand=True, alignment=ft.alignment.center),
                      ft.Container(content=ft.Column([ft.Text(self.loc.get("transactions_income")), self.stats_income],
                                                     horizontal_alignment=ft.CrossAxisAlignment.CENTER), expand=True,
                                   alignment=ft.alignment.center), ft.Container(
                    content=ft.Column([ft.Text(self.loc.get("transactions_expense")), self.stats_expense],
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER), expand=True,
                    alignment=ft.alignment.center)])
        self.stats_title_text = ft.Text(self.loc.get("transactions_stats_title"), style="titleLarge")
        stats_card = ft.Card(content=ft.Container(padding=15, content=ft.Column(
            [self.stats_title_text, stats_content_row])))
        self.date_header_text = ft.Text(self.loc.get("transactions_date_header"), weight=ft.FontWeight.BOLD)
        self.type_header_text = ft.Text(self.loc.get("transactions_type_header"), weight=ft.FontWeight.BOLD)
        self.category_header_text = ft.Text(self.loc.get("transactions_category_header"), weight=ft.FontWeight.BOLD)
        self.amount_header_text = ft.Text(self.loc.get("transactions_amount_header"), weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT)
        self.actions_header_text = ft.Text(self.loc.get("transactions_actions_header"), weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        
        history_header = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Container(content=self.date_header_text, width=110),
            ft.Container(content=self.type_header_text, width=80),
            ft.Container(content=self.category_header_text, expand=True), 
            ft.Container(content=self.amount_header_text, width=120), 
            ft.Container(content=self.actions_header_text, width=80)])

        self.history_title_text = ft.Text(self.loc.get("transactions_history_title"), style="titleLarge")
        history_section = ft.Column(col={"lg": 7, "md": 12},
                                    controls=[self.history_title_text,
                                              ft.Container(content=ft.Column([history_header, ft.Divider(height=5),
                                                                              ft.Container(content=self.history_list,
                                                                                           height=225)]),
                                                           border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=8,
                                                           padding=10)])
        self.chart_title_text = ft.Text(self.loc.get("transactions_chart_title"), style="titleLarge")
        chart_header = ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                              controls=[self.chart_title_text])
        chart_and_legend_row = ft.Row(
            controls=[ft.Container(content=self.pie_chart, expand=True, alignment=ft.alignment.center),
                      ft.Container(content=self.chart_legend_container, alignment=ft.alignment.center_right,
                                   padding=ft.padding.only(top=20))], vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER, expand=True)
        chart_section = ft.Column(col={"lg": 5, "md": 12},
                                  controls=[chart_header, ft.Container(content=chart_and_legend_row, height=250)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        main_layout = ft.ResponsiveRow(controls=[history_section, chart_section],
                                       vertical_alignment=ft.CrossAxisAlignment.START, expand=True, spacing=20)
        actions_header_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Row(controls=self.time_filter_buttons, alignment=ft.MainAxisAlignment.START),
                ft.Container(content=ft.Row([self.calculator_button, self.add_transaction_button], spacing=10),
                             margin=ft.margin.only(right=20))])
        # Створюємо красивий заголовок сторінки
        self.page_title_text = ft.Text(
            self.loc.get("transactions_title", default="Транзакції"),
            size=28,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        self.page_title = ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.PAYMENT_OUTLINED,
                    size=32,
                    color=ft.Colors.GREEN_400
                ),
                self.page_title_text
            ], spacing=12, alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.only(bottom=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREEN_400))
        )

        # Створюємо основний контент без фону (фон буде глобальним)
        main_content = ft.Column([
            self.page_title,
            stats_card, 
            actions_header_row, 
            main_layout
        ], expand=True)
        
        self.main_content.controls.clear()
        self.main_content.controls.append(main_content)

    def _create_dialogs(self):
        self.dialog_title = ft.Text(self.loc.get("transactions_dialog_new_title"), style="headlineSmall")
        self.edit_balance_input = ft.TextField(label=self.loc.get("transactions_edit_balance_dialog_label"),
                                               autofocus=True, input_filter=ft.NumbersOnlyInputFilter())
        self.new_category_dialog_textfield = ft.TextField(label=self.loc.get("transactions_new_category_dialog_label"),
                                                          autofocus=True)
        self.dialog_income_card = ft.Container(content=ft.Row([ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE),
                                                               ft.Text(self.loc.get("transactions_income").upper(),
                                                                       weight=ft.FontWeight.BOLD, size=16)],
                                                              alignment=ft.MainAxisAlignment.CENTER),
                                               data=cfg.TRANSACTION_TYPE_INCOME,
                                               on_click=lambda e: self.page.run_task(self.update_dialog_view,
                                                                                     e.control.data), height=50,
                                               border_radius=8, expand=True, animate=ft.Animation(300, "ease"))
        self.dialog_expense_card = ft.Container(content=ft.Row([ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE),
                                                                ft.Text(self.loc.get("transactions_expense").upper(),
                                                                        weight=ft.FontWeight.BOLD, size=16)],
                                                               alignment=ft.MainAxisAlignment.CENTER),
                                                data=cfg.TRANSACTION_TYPE_EXPENSE,
                                                on_click=lambda e: self.page.run_task(self.update_dialog_view,
                                                                                      e.control.data), height=50,
                                                border_radius=8, expand=True, animate=ft.Animation(300, "ease"))
        self.dialog_category_dropdown = ft.Dropdown(label=self.loc.get("transactions_dialog_category_label"),
                                                    dense=True, expand=True)
        self.add_category_button = ft.IconButton(icon=ft.Icons.ADD, on_click=self.open_add_category_dialog,
                                                 tooltip=self.loc.get("transactions_dialog_add_category_tooltip"))

        self.merge_category_button = ft.IconButton(icon=ft.Icons.MERGE_TYPE, on_click=self.open_merge_categories_dialog,
                                                   tooltip=self.loc.get("transactions_dialog_merge_category_tooltip"))
        self.dialog_category_row = ft.Row(
            [self.dialog_category_dropdown, self.add_category_button, self.merge_category_button], visible=True)

        self.dialog_description_input = ft.TextField(label=self.loc.get("transactions_dialog_description_label"),
                                                     dense=True)
        self.dialog_amount_input = ft.TextField(label=self.loc.get("transactions_dialog_amount_label"), dense=True,
                                                prefix_text="$ ",
                                                on_change=self.on_amount_change)
        self.dialog_submit_button = ft.ElevatedButton(icon=ft.Icons.CHECK_CIRCLE_OUTLINE, height=45,
                                                      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                                      on_click=self.add_or_update_transaction_action)
        self.dialog_calculator_button = ft.IconButton(icon=ft.Icons.CALCULATE_OUTLINED,
                                                      on_click=self.open_calculator_from_dialog,
                                                      tooltip=self.loc.get("transactions_calculator_tooltip"))
        self.cancel_button = ft.ElevatedButton(self.loc.get("transactions_dialog_cancel_button"),
                                               on_click=self.close_transaction_dialog_button, height=45,
                                               style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                                                    bgcolor=ft.Colors.WHITE24))
        dialog_content_column = ft.Container(content=ft.Column(
            [self.dialog_title, ft.Row([self.dialog_income_card, self.dialog_expense_card], spacing=10),
             self.dialog_category_row, self.dialog_description_input, self.dialog_amount_input, ft.Row(
                [self.dialog_calculator_button, ft.Container(expand=True), self.cancel_button,
                 self.dialog_submit_button], spacing=10)], spacing=15, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER), width=400, padding=20, border_radius=12,
            bgcolor="#2D2F31", scale=ft.Scale(0.9), opacity=0,
            animate_scale=ft.Animation(250, "easeOutCubic"),
            animate_opacity=ft.Animation(150, "easeIn"))
        self.transaction_dialog_content = dialog_content_column

        self.transaction_dialog_overlay = ft.Stack(
            [
                ft.Container(
                    expand=True,
                    bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK),
                    on_click=self.close_transaction_dialog_button,
                    animate_opacity=ft.Animation(200, "ease"),
                    opacity=0
                ),
                ft.Container(
                    content=self.transaction_dialog_content,
                    alignment=ft.alignment.center,
                    expand=True
                )
            ],
            expand=True,
            visible=False,
        )

        self.add_category_dialog = ft.AlertDialog(modal=True,
                                                  title=ft.Text(self.loc.get("transactions_new_category_dialog_title")),
                                                  content=self.new_category_dialog_textfield, actions=[
                ft.ElevatedButton(self.loc.get("transactions_dialog_cancel_button"),
                                  on_click=lambda e: self.close_sub_dialog(self.add_category_dialog),
                                  bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                ft.ElevatedButton(self.loc.get("transactions_new_category_dialog_add_button"),
                                  on_click=self.add_new_category_action, bgcolor=ft.Colors.GREEN_700,
                                  color=ft.Colors.WHITE)], actions_alignment=ft.MainAxisAlignment.END,
                                                  on_dismiss=lambda e: self.close_sub_dialog(self.add_category_dialog))
        self.confirm_delete_category_dialog = ft.AlertDialog(modal=True, title=ft.Text(
            self.loc.get("transactions_confirm_delete_category_title")), content=ft.Text(), actions=[
            ft.ElevatedButton(self.loc.get("profiles_confirm_delete_yes_button"),
                              style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_700),
                              on_click=self.confirm_delete_category_action),
            ft.ElevatedButton(self.loc.get("profiles_confirm_delete_no_button"),
                              on_click=lambda e: self.close_sub_dialog(self.confirm_delete_category_dialog))],
                                                             actions_alignment=ft.MainAxisAlignment.END,
                                                             on_dismiss=lambda e: self.close_sub_dialog(
                                                                 self.confirm_delete_category_dialog))
        self.edit_balance_dialog = ft.AlertDialog(modal=True,
                                                  title=ft.Text(self.loc.get("transactions_edit_balance_dialog_title")),
                                                  content=self.edit_balance_input, actions=[
                ft.ElevatedButton(self.loc.get("transactions_dialog_cancel_button"),
                                  on_click=lambda e: self.close_sub_dialog(self.edit_balance_dialog),
                                  bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                ft.ElevatedButton(self.loc.get("transactions_edit_balance_dialog_save_button"),
                                  on_click=self.save_balance_correction, bgcolor=ft.Colors.GREEN_700,
                                  color=ft.Colors.WHITE)], actions_alignment=ft.MainAxisAlignment.END,
                                                  on_dismiss=lambda e: self.close_sub_dialog(self.edit_balance_dialog))

        self.merge_target_name_field = ft.TextField(
            label=self.loc.get("transactions_merge_dialog_new_name_label"),
            on_change=self.validate_merge_button
        )
        self.merge_dialog_button = ft.ElevatedButton(
            self.loc.get("transactions_merge_dialog_merge_button"),
            on_click=self.merge_categories_action,
            disabled=True,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE
        )
        self.merge_categories_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.loc.get("transactions_merge_dialog_title")),
            content=ft.Column([
                ft.ListView(controls=self.merge_source_categories, spacing=0, height=150, expand=False),
                self.merge_target_name_field
            ], tight=True, spacing=15),
            actions=[
                ft.TextButton(self.loc.get("transactions_dialog_cancel_button"),
                              on_click=lambda e: self.close_sub_dialog(self.merge_categories_dialog)),
                self.merge_dialog_button
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        # --- НОВИЙ, ВИПРАВЛЕНИЙ БЛОК ---
        self.confirm_merge_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.loc.get("transactions_merge_confirm_title")),
            content=ft.Text(),
            actions=[
                ft.ElevatedButton(self.loc.get("profiles_confirm_delete_no_button"),
                                  on_click=lambda e: self.close_sub_dialog(self.confirm_merge_dialog)),
                ft.ElevatedButton(
                    self.loc.get("transactions_merge_dialog_merge_button"),  # <--- ПРАВИЛЬНИЙ ТЕКСТ
                    on_click=self.confirm_merge_action,
                    bgcolor=ft.Colors.RED_700,  # Залишаємо червоний колір, бо дія незворотня
                    color=ft.Colors.WHITE,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

    def on_amount_change(self, e: ft.ControlEvent):
        control = e.control
        original_value = control.value

        cleaned_value = re.sub(r'[^0-9.]', '', original_value)

        parts = cleaned_value.split('.')
        if len(parts) > 1:
            cleaned_value = parts[0] + '.' + "".join(parts[1:])

        if control.value != cleaned_value:
            control.value = cleaned_value
            control.update()

    async def _setup_overlays(self):
        """Налаштовує overlay елементи"""
        if self.page:
            if self.transaction_dialog_overlay not in self.page.overlay: self.page.overlay.append(
                self.transaction_dialog_overlay)
            if self.add_category_dialog not in self.page.overlay: self.page.overlay.append(self.add_category_dialog)
            if self.confirm_delete_category_dialog not in self.page.overlay: self.page.overlay.append(
                self.confirm_delete_category_dialog)
            if self.edit_balance_dialog not in self.page.overlay: self.page.overlay.append(self.edit_balance_dialog)
            if self.merge_categories_dialog not in self.page.overlay: self.page.overlay.append(
                self.merge_categories_dialog)
            if self.confirm_merge_dialog not in self.page.overlay: self.page.overlay.append(self.confirm_merge_dialog)

    async def open_calculator_from_dialog(self, e):
        initial_value = self.dialog_amount_input.value
        await self.toggle_global_calculator_func(e, initial_value, self.handle_calculator_result)

    async def handle_calculator_result(self, result: str | None):
        if result is not None:
            self.dialog_amount_input.value = result
            if self.page: self.page.update()

    async def handle_profile_change(self, profile_data: dict | None):
        if not self._is_built: return
        is_profile_selected = bool(profile_data)
        self.main_content.visible, self.no_profile_placeholder.visible = is_profile_selected, not is_profile_selected
        if is_profile_selected:
            if self.is_first_load:
                self.time_filter = cfg.TIME_FILTER_DAY
                self.is_first_load = False
            await self.update_ui_data(reset_pagination=True)
        if self.visible and self.page: self.update()

    async def open_transaction_dialog(self, e: ft.ControlEvent, trans_to_edit: dict | None = None):
        background = self.transaction_dialog_overlay.controls[0]

        self.transaction_dialog_overlay.visible = True
        self.page.update()
        await asyncio.sleep(0.01)

        if trans_to_edit:
            self.editing_transaction_id = trans_to_edit['id']
            self.dialog_title.value = self.loc.get("transactions_dialog_edit_title")
            self.dialog_description_input.value = trans_to_edit['description']
            self.dialog_amount_input.value = str(trans_to_edit['amount'])
            await self.update_dialog_view(trans_to_edit['type'])
            if trans_to_edit['type'] == cfg.TRANSACTION_TYPE_INCOME:
                self.dialog_category_dropdown.value = trans_to_edit['category']
        else:
            self.editing_transaction_id = None
            self.dialog_title.value = self.loc.get("transactions_dialog_new_title")
            self.dialog_description_input.value, self.dialog_amount_input.value = "", ""
            await self.update_dialog_view(cfg.TRANSACTION_TYPE_INCOME)

        background.opacity = 1
        self.transaction_dialog_content.scale = ft.Scale(1.0)
        self.transaction_dialog_content.opacity = 1
        self.page.update()
        self.dialog_description_input.focus()

    async def close_transaction_dialog(self):
        background = self.transaction_dialog_overlay.controls[0]
        background.opacity = 0
        self.transaction_dialog_content.scale = ft.Scale(0.9)
        self.transaction_dialog_content.opacity = 0
        self.page.update()
        await asyncio.sleep(0.25)
        self.transaction_dialog_overlay.visible = False
        self.editing_transaction_id = None
        self.page.update()

    async def close_transaction_dialog_button(self, e=None):
        await self.close_transaction_dialog()

    async def open_edit_transaction_dialog(self, trans: dict, e: ft.ControlEvent):
        await self.open_transaction_dialog(e, trans_to_edit=trans)

    async def update_dialog_view(self, selected_type: str):
        self.dialog_selected_type = selected_type
        is_income = self.dialog_selected_type == cfg.TRANSACTION_TYPE_INCOME
        self.dialog_income_card.bgcolor, self.dialog_income_card.border = (ft.Colors.GREEN_700, ft.border.all(2,
                                                                                                              ft.Colors.GREEN_400)) if is_income else (
            ft.Colors.WHITE12, None)
        self.dialog_expense_card.bgcolor, self.dialog_expense_card.border = (ft.Colors.RED_700, ft.border.all(2,
                                                                                                              ft.Colors.RED_400)) if not is_income else (
            ft.Colors.WHITE12, None)
        self.dialog_category_row.visible = is_income
        if is_income: await self.populate_category_dropdown()
        if self.editing_transaction_id:
            self.dialog_submit_button.text = self.loc.get("transactions_dialog_save_button")
            self.dialog_submit_button.icon = ft.Icons.SAVE_OUTLINED
            self.dialog_submit_button.bgcolor = ft.Colors.GREEN_700
        else:
            self.dialog_submit_button.text, self.dialog_submit_button.bgcolor = (
                self.loc.get("transactions_dialog_add_income_button"), ft.Colors.GREEN_700) if is_income else (
                self.loc.get("transactions_dialog_add_expense_button"), ft.Colors.RED_700)
            self.dialog_submit_button.icon = ft.Icons.CHECK_CIRCLE_OUTLINE
        if self.transaction_dialog_overlay.visible: self.page.update()

    async def populate_category_dropdown(self):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        categories = await dm.load_categories(profile_id)
        categories_for_type = categories.get(self.dialog_selected_type, [])
        dropdown, current_value, has_current_value = self.dialog_category_dropdown, self.dialog_category_dropdown.value, False
        dropdown.options.clear()
        for cat_obj in categories_for_type:
            cat_name = cat_obj['name']
            if cat_name == current_value: has_current_value = True
            dropdown.options.append(ft.dropdown.Option(key=cat_name, text=cat_name,
                                                       content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                                      controls=[ft.Text(cat_name), ft.IconButton(
                                                                          icon=ft.Icons.DELETE_OUTLINE, icon_size=16,
                                                                          icon_color=ft.Colors.RED_400,
                                                                          on_click=partial(
                                                                              self.show_confirm_delete_category_dialog,
                                                                              self.dialog_selected_type, cat_name),
                                                                          style=ft.ButtonStyle(padding=0))])))
        if has_current_value:
            dropdown.value = current_value
        elif dropdown.options:
            dropdown.value = dropdown.options[0].key
        else:
            dropdown.value = None

    def open_add_category_dialog(self, e):
        self.category_type_to_add = self.dialog_selected_type
        type_str = self.loc.get('transactions_income') if self.category_type_to_add == 'дохід' else self.loc.get(
            'transactions_expense')
        self.new_category_dialog_textfield.value, self.new_category_dialog_textfield.error_text = "", ""
        self.add_category_dialog.title.value = f"{self.loc.get('transactions_new_category_dialog_title')} ({type_str})"
        self.page.dialog = self.add_category_dialog
        self.add_category_dialog.open = True
        self.page.update()

    def close_sub_dialog(self, dialog: ft.AlertDialog):
        dialog.open = False
        self.page.update()

    async def add_new_category_action(self, e):
        new_name = self.new_category_dialog_textfield.value.strip()
        if not new_name:
            self.new_category_dialog_textfield.error_text = self.loc.get("error_name_empty")
            self.add_category_dialog.update();
            return
        if not self.app_state.current_profile or not self.category_type_to_add: return
        profile_id = self.app_state.current_profile['id']
        categories_data = await dm.load_categories(profile_id)
        current_categories = categories_data.get(self.category_type_to_add, [])
        if any(cat['name'].lower() == new_name.lower() for cat in current_categories):
            self.new_category_dialog_textfield.error_text = self.loc.get("error_name_duplicate")
            self.add_category_dialog.update();
            return
        used_colors = {cat['color'] for cat in current_categories if cat.get('color')}
        available_colors = [color for color in cfg.CHART_COLORS if color not in used_colors]
        new_color = available_colors[0] if available_colors else cfg.CHART_COLORS[
            len(current_categories) % len(cfg.CHART_COLORS)]
        await dm.add_category(profile_id, self.category_type_to_add, new_name, new_color)
        self.dialog_category_dropdown.value = new_name
        await self.populate_category_dropdown()
        self.close_sub_dialog(self.add_category_dialog)
        self.page.update()

    def show_confirm_delete_category_dialog(self, cat_type: str, cat_name: str, e):
        self.category_to_delete = (cat_type, cat_name)
        self.confirm_delete_category_dialog.content.value = self.loc.get("transactions_confirm_delete_category_content",
                                                                         cat_name=cat_name)
        self.page.dialog = self.confirm_delete_category_dialog
        self.confirm_delete_category_dialog.open = True
        self.page.update()

    async def confirm_delete_category_action(self, e):
        if self.category_to_delete and self.app_state.current_profile:
            cat_type, cat_name = self.category_to_delete
            profile_id = self.app_state.current_profile['id']
            await dm.delete_category(profile_id, cat_type, cat_name)
            if self.dialog_category_dropdown.value == cat_name: self.dialog_category_dropdown.value = None
            await self.populate_category_dropdown()
            self.close_sub_dialog(self.confirm_delete_category_dialog)
            await self.update_ui_data(reset_pagination=True)

    @handle_errors("add_or_update_transaction")
    async def add_or_update_transaction_action(self, e):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        
        try:
            amount_str = self.dialog_amount_input.value
            desc = self.dialog_description_input.value.strip()
            is_income = self.dialog_selected_type == cfg.TRANSACTION_TYPE_INCOME
            category = self.dialog_category_dropdown.value if is_income else ""
            
            # Валідація з новою системою
            if not amount_str:
                raise ValueError(self.loc.get("error_amount_zero"))
            
            amount = float(amount_str)
            if not self.validator.validate_amount(amount):
                raise ValueError(self.loc.get("error_amount_zero"))
            
            if is_income and not category:
                raise ValueError(self.loc.get("error_category_empty"))
            
            if not self.validator.validate_category(category) and category:
                raise ValueError("Invalid category")
            
            # Логуємо дію користувача
            logger.log_user_action("add_transaction", user_id=str(profile_id))
            
        except (ValueError, TypeError) as err:
            logger.error(f"Transaction validation failed: {err}")
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"{err}"), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
        if self.editing_transaction_id:
            await dm.update_transaction(self.editing_transaction_id, self.dialog_selected_type, category, desc, amount)
        else:
            await dm.add_transaction(profile_id, self.dialog_selected_type, category, desc, amount)
        await self.close_transaction_dialog_button(e)
        await self.update_ui_data(reset_pagination=True)

    async def open_merge_categories_dialog(self, e):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        categories = await dm.load_categories(profile_id)
        income_categories = categories.get(cfg.TRANSACTION_TYPE_INCOME, [])

        self.merge_source_categories.clear()
        for cat in income_categories:
            self.merge_source_categories.append(
                ft.Checkbox(label=cat['name'], value=False, on_change=self.validate_merge_button)
            )

        self.merge_target_name_field.value = ""
        self.merge_target_name_field.error_text = ""
        self.merge_dialog_button.disabled = True

        self.merge_categories_dialog.content.controls[0].controls = self.merge_source_categories
        self.page.dialog = self.merge_categories_dialog
        self.merge_categories_dialog.open = True
        self.page.update()

    def validate_merge_button(self, e):
        selected_count = sum(1 for chk in self.merge_source_categories if chk.value)
        new_name = self.merge_target_name_field.value.strip()
        self.merge_dialog_button.disabled = not (selected_count >= 2 and new_name)
        self.merge_categories_dialog.update()

    async def merge_categories_action(self, e):
        target_name_field = self.merge_target_name_field
        target_name_field.error_text = None

        selected_categories = [chk.label for chk in self.merge_source_categories if chk.value]

        if len(selected_categories) < 2:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(self.loc.get("transactions_merge_error_min_categories")),
                bgcolor=ft.Colors.RED_700
            )
            self.page.snack_bar.open = True
            self.page.update()
            return

        target_name = target_name_field.value.strip()

        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        all_categories_data = await dm.load_categories(profile_id)

        existing_names_lower = {cat['name'].lower() for cat_list in all_categories_data.values() for cat in cat_list}

        has_error = False
        if not target_name:
            target_name_field.error_text = self.loc.get("transactions_merge_error_name_empty")
            has_error = True
        elif target_name.lower() in existing_names_lower:
            target_name_field.error_text = self.loc.get("transactions_merge_error_name_duplicate")
            has_error = True

        if has_error:
            target_name_field.update()
            return

        self.confirm_merge_dialog.content.value = self.loc.get(
            "transactions_merge_confirm_content",
            count=len(selected_categories),
            target_name=target_name
        )
        self.merge_categories_dialog.open = False
        self.page.dialog = self.confirm_merge_dialog
        self.confirm_merge_dialog.open = True
        self.page.update()

    # --- НОВА, ВИПРАВЛЕНА ВЕРСІЯ МЕТОДУ ---
    async def confirm_merge_action(self, e):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']

        source_names = [chk.label for chk in self.merge_source_categories if chk.value]
        target_name = self.merge_target_name_field.value.strip()

        all_categories = await dm.load_categories(profile_id)
        current_categories = all_categories.get(cfg.TRANSACTION_TYPE_INCOME, [])
        used_colors = {cat['color'] for cat in current_categories if cat.get('color')}
        available_colors = [color for color in cfg.CHART_COLORS if color not in used_colors]
        new_color = available_colors[0] if available_colors else cfg.CHART_COLORS[
            len(current_categories) % len(cfg.CHART_COLORS)]

        await dm.merge_categories(profile_id, source_names, target_name, cfg.TRANSACTION_TYPE_INCOME, new_color)

        # **КЛЮЧОВА ЗМІНА**: Закриваємо спочатку вікно підтвердження
        self.close_sub_dialog(self.confirm_merge_dialog)
        # Потім закриваємо головний діалог транзакції
        await self.close_transaction_dialog()

        # І лише потім оновлюємо дані на головному екрані
        await self.update_ui_data(reset_pagination=True)

    def open_edit_balance_dialog(self, e):
        self.edit_balance_input.value = str(int(self.current_balance))
        self.edit_balance_input.error_text = ""
        self.page.dialog = self.edit_balance_dialog
        self.edit_balance_dialog.open = True
        self.page.update()

    async def save_balance_correction(self, e):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        try:
            new_balance_str = self.edit_balance_input.value
            if not new_balance_str: raise ValueError(self.loc.get("error_name_empty"))
            new_balance = float(new_balance_str)
        except (ValueError, TypeError) as err:
            self.edit_balance_input.error_text = self.loc.get("error_generic", err=err)
            self.edit_balance_dialog.update()
            return
        correction_amount = new_balance - self.current_balance
        if correction_amount != 0:
            trans_type = cfg.TRANSACTION_TYPE_INCOME if correction_amount > 0 else cfg.TRANSACTION_TYPE_EXPENSE
            await dm.add_transaction(profile_id, trans_type, cfg.CORRECTION_CATEGORY,
                                     self.loc.get("special_category_correction"), abs(correction_amount))
        self.close_sub_dialog(self.edit_balance_dialog)
        await self.update_ui_data(reset_pagination=True)

    async def update_ui_data(self, reset_pagination: bool = False):
        if not self.app_state.current_profile or not self.page: return
        profile_id = self.app_state.current_profile['id']

        if reset_pagination:
            self.current_offset = 0
            self.has_more_transactions = True
            self.history_list.controls.clear()

        self.update_filter_buttons_style(update_page=False)

        self.current_balance = await dm.get_total_balance(profile_id)
        self.balance_display_text.controls.clear()
        self.balance_display_text.controls.append(
            create_amount_display(self.current_balance, "green" if self.current_balance >= 0 else "red", size=24))

        now = datetime.now()
        end_date = now
        start_date = None
        if self.time_filter == cfg.TIME_FILTER_DAY:
            start_date = now - timedelta(hours=24)
        elif self.time_filter == cfg.TIME_FILTER_WEEK:
            start_date = now - timedelta(days=7)
        elif self.time_filter == cfg.TIME_FILTER_MONTH:
            start_date = now - timedelta(days=30)

        stats = await dm.get_transactions_stats(profile_id, start_date, end_date)
        income_by_cat, expense_by_desc = await dm.get_category_summary(profile_id, start_date, end_date)
        self.stats_income.controls = [create_amount_display(stats['income'], "green")]
        self.stats_expense.controls = [create_amount_display(stats['expense'], "red")]
        await self.update_pie_chart_data(income_by_cat, expense_by_desc)

        if reset_pagination:
            await self.load_more_transactions(e=None, is_initial_load=True)

        self.is_legend_expanded = False
        self._update_legend_view()
        self._handle_hover_change(None)
        if self.page: self.page.update()

    async def _on_transactions_change(self):
        # Перевантажуємо поточні дані, зберігаючи активний фільтр та пагінацію з початку
        await self.update_ui_data(reset_pagination=True)

    async def load_more_transactions(self, e, is_initial_load=False):
        if self.is_loading_more or not self.has_more_transactions or not self.app_state.current_profile:
            return

        self.is_loading_more = True

        self.loading_more_indicator.visible = True
        self.load_more_button.visible = False
        if self.load_more_container not in self.history_list.controls:
            self.history_list.controls.append(self.load_more_container)
        self.load_more_container.visible = True
        if self.page: self.page.update()

        profile_id = self.app_state.current_profile['id']
        now = datetime.now()
        start_date, end_date = None, now
        if self.time_filter == cfg.TIME_FILTER_DAY:
            start_date = now - timedelta(hours=24)
        elif self.time_filter == cfg.TIME_FILTER_WEEK:
            start_date = now - timedelta(days=7)
        elif self.time_filter == cfg.TIME_FILTER_MONTH:
            start_date = now - timedelta(days=30)

        fetched_transactions = await dm.load_transactions(
            profile_id,
            start_date=start_date,
            end_date=end_date,
            limit=self.TRANSACTIONS_PER_PAGE + 1,
            offset=self.current_offset
        )

        self.has_more_transactions = len(fetched_transactions) > self.TRANSACTIONS_PER_PAGE
        transactions_to_display = fetched_transactions[:self.TRANSACTIONS_PER_PAGE]

        if self.load_more_container in self.history_list.controls:
            self.history_list.controls.remove(self.load_more_container)

        for trans in transactions_to_display:
            self.history_list.controls.append(self.create_transaction_row(trans))

        self.current_offset += len(transactions_to_display)

        if is_initial_load and not self.history_list.controls:
            placeholder = ft.Container(content=ft.Column(
                [ft.Icon(ft.Icons.HISTORY_ROUNDED, size=48, color=ft.Colors.WHITE24),
                 ft.Text(self.loc.get("transactions_history_empty"), text_align=ft.TextAlign.CENTER,
                         color=ft.Colors.WHITE38, size=14)], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10), alignment=ft.alignment.center, expand=True, padding=ft.padding.only(top=30))
            self.history_list.controls.append(placeholder)

        self.is_loading_more = False

        if self.has_more_transactions:
            self.loading_more_indicator.visible = False
            self.load_more_button.visible = True
            self.history_list.controls.append(self.load_more_container)
        else:
            self.load_more_container.visible = False

        if self.page: self.page.update()

    def create_transaction_row(self, trans: dict) -> ft.Container:
        is_special = trans['category'] in [cfg.INITIAL_BALANCE_CATEGORY, cfg.CORRECTION_CATEGORY]
        display_text = trans['description']
        if trans['category'] and not is_special:
            display_text = f"{trans['category']}: {trans['description']}"
        elif is_special:
            special_category_keys = {cfg.INITIAL_BALANCE_CATEGORY: "special_category_initial_balance",
                                     cfg.CORRECTION_CATEGORY: "special_category_correction"}
            localization_key = special_category_keys.get(trans['category'])
            display_text = self.loc.get(localization_key) if localization_key else trans['category']
        is_income = trans['type'] == cfg.TRANSACTION_TYPE_INCOME
        type_str = self.loc.get('transactions_income') if is_income else self.loc.get('transactions_expense')
        date_text_control = ft.Text(datetime.fromisoformat(trans['timestamp']).strftime('%d.%m %H:%M'), size=14)
        type_text_control = ft.Text(type_str.capitalize(), size=14)
        desc_text_control = ft.Text(display_text, italic=is_special, expand=True, size=14)
        amount_display_control = create_amount_display(float(trans['amount']), "green" if is_income else "red", size=14)
        actions_row = ft.Row(spacing=0, alignment=ft.MainAxisAlignment.CENTER, controls=[
            ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color="amber400", icon_size=18,
                          tooltip=self.loc.get("profiles_edit_tooltip"),
                          on_click=partial(self.open_edit_transaction_dialog, trans), height=30,
                          style=ft.ButtonStyle(padding=0)),
            ft.IconButton(icon=ft.Icons.DELETE_FOREVER, icon_color="red400", icon_size=18,
                          tooltip=self.loc.get("profiles_delete_tooltip"),
                          on_click=partial(self.delete_transaction, trans['id']), height=30,
                          style=ft.ButtonStyle(padding=0))])
        row_content = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER,
                             controls=[ft.Container(content=date_text_control, width=110),
                                       ft.Container(content=type_text_control, width=80), desc_text_control,
                                       ft.Container(content=amount_display_control, width=120,
                                                    alignment=ft.alignment.center_right),
                                       ft.Container(content=actions_row, width=80, alignment=ft.alignment.center)])
        return ft.Container(key=str(trans['id']), content=row_content, data=trans, border_radius=6,
                            padding=ft.padding.symmetric(vertical=2, horizontal=4), bgcolor=ft.Colors.TRANSPARENT,
                            animate=ft.Animation(200, "ease"))

    def on_pie_chart_hover(self, e: ft.PieChartEvent):
        if not self.page: return
        new_hover_key = e.control.sections[
            e.section_index].data if e.section_index is not None and e.section_index != -1 else None
        self._handle_hover_change(new_hover_key)

    def on_legend_item_hover(self, e: ft.HoverEvent):
        new_hover_key = e.control.data if e.data == "true" else None
        self._handle_hover_change(new_hover_key)

    def _on_legend_area_hover(self, e: ft.HoverEvent):
        if e.data == "false" and self.is_legend_expanded:
            self.is_legend_expanded = False
            self._handle_hover_change(None)

    def _handle_hover_change(self, new_hover_key: str | None):
        should_expand = (new_hover_key == self._OTHER_CATEGORY_KEY)
        if self.is_legend_expanded != should_expand:
            self.is_legend_expanded = should_expand
            self._update_legend_view()
        if self.hovered_category_name != new_hover_key:
            self.hovered_category_name = new_hover_key
            self._update_highlights()

    def _update_highlights(self):
        for section in self.pie_chart.sections:
            is_hovered = (section.data == self.hovered_category_name)
            section.radius = 70 if is_hovered else 60
            section.border_side = ft.BorderSide(4, ft.Colors.WHITE) if is_hovered else ft.BorderSide(width=0,
                                                                                                     color=ft.Colors.TRANSPARENT)
        if self.chart_legend_switcher.content and hasattr(self.chart_legend_switcher.content, 'controls'):
            for control in self.chart_legend_switcher.content.controls:
                if not isinstance(control, ft.Container) or not hasattr(control, 'data'): continue
                legend_container = control
                legend_text_control = legend_container.content.controls[1]
                is_hovered_currently = (legend_container.data == self.hovered_category_name)
                legend_container.scale = 1.1 if is_hovered_currently else 1.0
                legend_text_control.weight = ft.FontWeight.BOLD if is_hovered_currently else ft.FontWeight.NORMAL
        first_highlighted_key = None
        for item_container in self.history_list.controls:
            if not (isinstance(item_container, ft.Container) and item_container.data): continue
            trans_data = item_container.data
            key = trans_data.get('category') if trans_data.get(
                'type') == cfg.TRANSACTION_TYPE_INCOME else trans_data.get('description')
            is_highlighted = (self.hovered_category_name is not None and key == self.hovered_category_name)
            if self.hovered_category_name == self._OTHER_CATEGORY_KEY:
                small_item_names = {item['name'] for item in self.small_items_cache}
                if key in small_item_names: is_highlighted = True
            item_container.bgcolor = ft.Colors.WHITE10 if is_highlighted else ft.Colors.TRANSPARENT
            if is_highlighted and not first_highlighted_key: first_highlighted_key = item_container.key
        if first_highlighted_key: self.history_list.scroll_to(key=first_highlighted_key, duration=600,
                                                              curve=ft.AnimationCurve.EASE_IN_OUT)
        if self.page: self.page.update()

    def _build_legend_column(self, items: list) -> ft.Column:
        legend_controls = []
        for item in items:
            name, percentage, color, data_key = item['name'], item['percentage'], item['color'], item['data']
            legend_row = ft.Row(controls=[ft.Container(width=16, height=16, bgcolor=color, border_radius=8),
                                          ft.Text(name, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                                                  weight=ft.FontWeight.NORMAL),
                                          ft.Text(f"{percentage:.0f}%", weight=ft.FontWeight.BOLD)], spacing=10,
                                alignment=ft.MainAxisAlignment.START)
            legend_item_container = ft.Container(content=legend_row, on_hover=self.on_legend_item_hover, scale=1.0,
                                                 animate_scale=ft.Animation(200, "ease"), data=data_key,
                                                 border_radius=4,
                                                 padding=ft.padding.symmetric(vertical=2, horizontal=4))
            legend_controls.append(legend_item_container)
        return ft.Column(controls=legend_controls, spacing=4, tight=True)

    def _update_legend_view(self):
        if self.is_legend_expanded and self.small_items_cache:
            self.chart_legend_switcher.content = self._build_legend_column(self.small_items_cache)
        else:
            self.chart_legend_switcher.content = self._build_legend_column(self.large_items_cache)
        if self.page: self.page.update()

    def _build_pie_chart(self):
        self.pie_chart.sections.clear()
        for item in self.large_items_cache:
            self.pie_chart.sections.append(ft.PieChartSection(value=item['percentage'], color=item['color'], radius=60,
                                                              title=f"{item['percentage']:.0f}%",
                                                              title_style=ft.TextStyle(size=12,
                                                                                       weight=ft.FontWeight.BOLD,
                                                                                       color=ft.Colors.WHITE),
                                                              border_side=ft.BorderSide(width=0,
                                                                                        color=ft.Colors.TRANSPARENT),
                                                              data=item['data']))

    async def update_pie_chart_data(self, income_by_category, expense_by_description):
        if not self.app_state.current_profile: return
        profile_id = self.app_state.current_profile['id']
        all_categories = await dm.load_categories(profile_id)
        income_color_map = {cat['name']: cat['color'] for cat in all_categories.get(cfg.TRANSACTION_TYPE_INCOME, [])}

        self.large_items_cache.clear()
        self.small_items_cache.clear()
        data_source, color_map = {}, {}

        if income_by_category:
            data_source, color_map = income_by_category, income_color_map
        elif expense_by_description:
            data_source, color_map = expense_by_description, {}

        self.pie_chart.center_space_color = None
        total_value = sum(data_source.values())

        if total_value == 0:
            self._build_pie_chart()
            self._update_legend_view()
            return

        sorted_items = sorted(data_source.items(), key=lambda item: item[1], reverse=True)
        large_items_data, small_items_data = [], []
        for i, (name, value) in enumerate(sorted_items):
            percentage = (value / total_value) * 100
            color = color_map.get(name, cfg.CHART_COLORS[i % len(cfg.CHART_COLORS)])
            item_data = {'name': name, 'value': value, 'percentage': percentage, 'color': color, 'data': name}
            if percentage < 5:
                small_items_data.append(item_data)
            else:
                large_items_data.append(item_data)

        self.small_items_cache = sorted(small_items_data, key=lambda x: x['value'], reverse=True)
        final_chart_items = large_items_data
        if small_items_data:
            other_category_name = self.loc.get("transactions_chart_other_category")
            other_item = {'name': other_category_name, 'value': sum(item['value'] for item in small_items_data),
                          'percentage': sum(item['percentage'] for item in small_items_data),
                          'color': ft.Colors.BLUE_GREY_500, 'data': self._OTHER_CATEGORY_KEY}
            final_chart_items.append(other_item)

        self.large_items_cache = sorted(final_chart_items, key=lambda x: x['value'], reverse=True)
        self._build_pie_chart()

    async def delete_transaction(self, transaction_id, e):
        await dm.delete_transaction(transaction_id)
        await self.update_ui_data(reset_pagination=True)

    async def filter_transactions_by_time(self, e: ft.ControlEvent):
        self.time_filter = e.control.data
        await self.update_ui_data(reset_pagination=True)

    def update_filter_buttons_style(self, update_page=True):
        if not self._is_built: return
        for button in self.time_filter_buttons:
            is_active = button.data == self.time_filter
            button.style = ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY_CONTAINER) if is_active else ft.ButtonStyle()
        if update_page and self.page: self.update()

    # --- НОВІ МЕТОДИ З VIRTUALIZED LIST ---
    
    def _create_transaction_item_renderer(self, transaction_data: dict, index: int) -> ft.Container:
        """Створює рендерер для елемента транзакції"""
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.ARROW_UPWARD if transaction_data['type'] == 'дохід' else ft.Icons.ARROW_DOWNWARD,
                        color=ft.Colors.GREEN_400 if transaction_data['type'] == 'дохід' else ft.Colors.RED_400,
                        size=20
                    ),
                    width=40,
                    height=40,
                    bgcolor=ft.Colors.WHITE12,
                    border_radius=20,
                    alignment=ft.alignment.center
                ),
                ft.Column([
                    ft.Text(
                        transaction_data['category'],
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        transaction_data['description'] or '',
                        size=12,
                        color=ft.Colors.GREY_400,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS
                    )
                ], expand=True, spacing=2),
                ft.Column([
                    ft.Text(
                        f"{'+' if transaction_data['type'] == 'дохід' else '-'}{format_number(transaction_data['amount'])}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_400 if transaction_data['type'] == 'дохід' else ft.Colors.RED_400,
                        text_align=ft.TextAlign.END
                    ),
                    ft.Text(
                        transaction_data['timestamp'][:10],
                        size=10,
                        color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.END
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
            ], spacing=15),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            bgcolor=ft.Colors.WHITE12,
            border_radius=10,
            margin=ft.margin.only(bottom=8)
        )
    
    def _create_virtualized_transactions_list(self, transactions: list) -> ft.Container:
        """Створює віртуалізований список транзакцій"""
        if not transactions:
            return ft.Container(
                content=ft.Text("Немає транзакцій", color=ft.Colors.GREY_400),
                alignment=ft.alignment.center,
                height=200
            )
        
        # Ініціалізуємо VirtualizedList якщо ще не ініціалізована
        if not self.virtualized_list:
            self.virtualized_list = VirtualizedList(
                config=self.virtualization_config,
                item_renderer=self._create_transaction_item_renderer
            )
        
        # Встановлюємо дані
        self.virtualized_list.set_data(transactions)
        
        # Створюємо контейнер для віртуалізованого списку
        return ft.Container(
            content=self.virtualized_list.get_container(),
            height=self.virtualization_config.container_height,
            border_radius=10,
            bgcolor=ft.Colors.WHITE12
        )
    
    async def _load_transactions_for_virtualization(self, start_index: int, count: int) -> list:
        """Завантажує транзакції для віртуалізації"""
        if not self.app_state.current_profile:
            return []
        
        profile_id = self.app_state.current_profile['id']
        
        # Визначаємо дати на основі фільтру
        end_date = datetime.now()
        if self.time_filter == cfg.TIME_FILTER_DAY:
            start_date = end_date - timedelta(days=1)
        elif self.time_filter == cfg.TIME_FILTER_WEEK:
            start_date = end_date - timedelta(weeks=1)
        elif self.time_filter == cfg.TIME_FILTER_MONTH:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = None
        
        # Завантажуємо транзакції
        transactions = await dm.load_transactions(
            profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            limit=count,
            offset=start_index
        )
        
        return transactions
    
    def enable_virtualization(self, enable: bool = True):
        """Увімкнення/вимкнення віртуалізації"""
        if enable and not self.virtualized_list:
            self.virtualized_list = VirtualizedList(
                config=self.virtualization_config,
                item_renderer=self._create_transaction_item_renderer,
                data_loader=self._load_transactions_for_virtualization
            )
        elif not enable and self.virtualized_list:
            self.virtualized_list = None