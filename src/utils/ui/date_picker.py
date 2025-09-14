"""
Простий Date Picker з календарем
"""
import flet as ft
from datetime import datetime, date, timedelta
from typing import Optional, Callable
import calendar


class ModernDatePicker(ft.Container):
    """Простий date picker з календарем"""
    
    def __init__(
        self,
        label: str = "Дата",
        initial_date: Optional[date] = None,
        on_date_changed: Optional[Callable[[date], None]] = None,
        page=None,
        mode: str = "add",  # "add" або "edit"
        localization_manager=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        self.label = label
        self.on_date_changed = on_date_changed
        self.page = page
        self.mode = mode
        self.localization_manager = localization_manager
        
        # Поточна дата
        self.current_date = initial_date or date.today()
        self.display_date = date.today()  # Дата для відображення календаря
        
        # Визначаємо кольори залежно від режиму
        if mode == "edit":
            self.primary_color = ft.Colors.AMBER_600
            self.primary_light = ft.Colors.AMBER_100
        else:  # add
            self.primary_color = ft.Colors.BLUE_600
            self.primary_light = ft.Colors.BLUE_100
        
        # Місяці та дні тижня (будуть завантажені з локалізації)
        self.months = []
        self.weekdays = []
        
        # Стан календаря (показаний/прихований)
        self.calendar_visible = False
        
        # Завантажуємо локалізацію
        self._load_localization()
        
        # Ініціалізація UI
        self._build_ui()
        self._update_calendar()
    
    def _load_localization(self):
        """Завантажує локалізовані тексти"""
        print(f"🔍 Calendar: Loading localization...")
        try:
            # Спочатку пробуємо використати передану локалізацію
            if self.localization_manager:
                loc = self.localization_manager
                print(f"🔍 Calendar: Using passed localization manager")
                self.months = loc.get("calendar_months", default=[
                    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
                    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
                ])
                self.weekdays = loc.get("calendar_weekdays", default=["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"])
                print(f"🔍 Calendar: Loaded months: {self.months[:3]}...")
                print(f"🔍 Calendar: Loaded weekdays: {self.weekdays}")
            # Потім пробуємо отримати локалізацію з app_state
            elif hasattr(self.page, 'app_state') and hasattr(self.page.app_state, 'localization_manager'):
                loc = self.page.app_state.localization_manager
                print(f"🔍 Calendar: Found localization manager in app_state")
                self.months = loc.get("calendar_months", default=[
                    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
                    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
                ])
                self.weekdays = loc.get("calendar_weekdays", default=["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"])
                print(f"🔍 Calendar: Loaded months: {self.months[:3]}...")
                print(f"🔍 Calendar: Loaded weekdays: {self.weekdays}")
            else:
                print(f"🔍 Calendar: No localization manager found, using fallback")
                # Fallback на українську
                self.months = [
                    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
                    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
                ]
                self.weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        except Exception as e:
            print(f"🔍 Calendar: Error loading localization: {e}")
            # Fallback на українську
            self.months = [
                "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
                "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
            ]
            self.weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    
    def update_localization(self):
        """Оновлює локалізацію після зміни мови"""
        print(f"🔍 Calendar: Updating localization...")
        self._load_localization()
        self._update_calendar()
    
    def _build_ui(self):
        """Створює UI компонента"""
        
        # Заголовок з навігацією
        self.header = ft.Row([
            # Кнопка попереднього місяця
            ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                on_click=self._prev_month,
                tooltip="Попередній місяць",
                icon_color=ft.Colors.WHITE
            ),
            # Назва місяця та року
            ft.Text(
                "",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
                expand=True,
                text_align=ft.TextAlign.CENTER
            ),
            # Кнопка наступного місяця
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                on_click=self._next_month,
                tooltip="Наступний місяць",
                icon_color=ft.Colors.WHITE
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        # Дні тижня
        self.weekdays_row = ft.Row([
            ft.Container(
                content=ft.Text(day, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                width=40,
                height=30,
                alignment=ft.alignment.center,
                bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
                border_radius=5
            ) for day in self.weekdays
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        
        # Календар
        self.calendar_grid = ft.Column(spacing=2)
        
        
        # Календар контейнер
        self.calendar_container = ft.Container(
            content=ft.Column([
                self.header,
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                self.weekdays_row,
                ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                self.calendar_grid
            ], spacing=0),
            bgcolor=ft.Colors.BLACK,
            border_radius=15,
            border=ft.border.all(1, ft.Colors.WHITE),
            padding=15,
            visible=False,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
                offset=ft.Offset(0, 5)
            )
        )
        
        # Основний контейнер (тільки календар, кнопка прихована)
        self.content = ft.Container(
            content=ft.Column([
                self.calendar_container
            ], spacing=10),
            width=520  # Обмежуємо ширину
        )
    
    def _update_calendar(self):
        """Оновлює календар"""
        # Оновлюємо заголовок
        month_text = f"{self.months[self.display_date.month - 1]} {self.display_date.year}"
        self.header.controls[1].value = month_text
        
        # Очищуємо календар
        self.calendar_grid.controls.clear()
        
        # Отримуємо календар на місяць
        cal = calendar.monthcalendar(self.display_date.year, self.display_date.month)
        
        for week in cal:
            week_row = ft.Row(spacing=2, alignment=ft.MainAxisAlignment.SPACE_EVENLY)
            
            for day in week:
                if day == 0:
                    # Порожня клітинка
                    day_container = ft.Container(
                        width=40,
                        height=40,
                        bgcolor=ft.Colors.TRANSPARENT
                    )
                else:
                    day_date = date(self.display_date.year, self.display_date.month, day)
                    
                    # Визначаємо стиль
                    is_today = day_date == date.today()
                    is_selected = day_date == self.current_date
                    
                    if is_selected:
                        bg_color = self.primary_color
                        text_color = ft.Colors.WHITE
                        weight = ft.FontWeight.BOLD
                    elif is_today:
                        bg_color = self.primary_light
                        text_color = self.primary_color
                        weight = ft.FontWeight.BOLD
                    else:
                        bg_color = ft.Colors.TRANSPARENT
                        text_color = ft.Colors.WHITE
                        weight = ft.FontWeight.NORMAL
                    
                    day_container = ft.Container(
                        content=ft.Text(
                            str(day),
                            size=14,
                            color=text_color,
                            weight=weight
                        ),
                        width=40,
                        height=40,
                        bgcolor=bg_color,
                        border_radius=20,
                        alignment=ft.alignment.center,
                        on_click=lambda e, d=day_date: self._select_date(d)
                    )
                
                week_row.controls.append(day_container)
            
            self.calendar_grid.controls.append(week_row)
        
        # Оновлюємо UI
        if self.page:
            self.page.update()
    
    def _select_date(self, selected_date: date):
        """Вибирає дату"""
        self.current_date = selected_date
        self._update_calendar()
        self._hide_calendar()  # Приховуємо календар після вибору
        
        if self.on_date_changed:
            self.on_date_changed(selected_date)
    
    def _toggle_calendar(self, e):
        """Перемикає видимість календаря"""
        if self.calendar_visible:
            self._hide_calendar()
        else:
            self._show_calendar()
    
    def _show_calendar(self):
        """Показує календар"""
        self.calendar_visible = True
        self.calendar_container.visible = True
        if self.page:
            self.page.update()
    
    def _hide_calendar(self):
        """Приховує календар"""
        self.calendar_visible = False
        self.calendar_container.visible = False
        if self.page:
            self.page.update()
    
    def _prev_month(self, e):
        """Попередній місяць"""
        if not self.calendar_visible:
            return
        if self.display_date.month == 1:
            self.display_date = self.display_date.replace(year=self.display_date.year - 1, month=12)
        else:
            self.display_date = self.display_date.replace(month=self.display_date.month - 1)
        self._update_calendar()
    
    def _next_month(self, e):
        """Наступний місяць"""
        if not self.calendar_visible:
            return
        if self.display_date.month == 12:
            self.display_date = self.display_date.replace(year=self.display_date.year + 1, month=1)
        else:
            self.display_date = self.display_date.replace(month=self.display_date.month + 1)
        self._update_calendar()
    
    
    def get_date_string(self) -> str:
        """Повертає дату у форматі рядка"""
        return self.current_date.strftime("%Y-%m-%d")
    
    def set_date_from_string(self, date_string: str):
        """Встановлює дату з рядка"""
        try:
            self.current_date = datetime.strptime(date_string, "%Y-%m-%d").date()
            self.display_date = self.current_date
            self._update_calendar()
        except ValueError:
            pass
    
    def set_date(self, new_date: date):
        """Встановлює дату"""
        self.current_date = new_date
        self.display_date = new_date
        self._update_calendar()

# Для зворотної сумісності
IOSDatePicker = ModernDatePicker
