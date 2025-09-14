import flet as ft
from datetime import date, datetime, timedelta
import calendar
from typing import Callable, Optional

class ModernDatePicker(ft.Container):
    """Сучасний date picker з календарем"""
    
    def __init__(
        self,
        label: str = "Дата",
        initial_date: Optional[date] = None,
        on_date_changed: Optional[Callable[[date], None]] = None,
        page=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        self.label = label
        self.on_date_changed = on_date_changed
        self.page = page
        
        # Поточна дата
        self.current_date = initial_date or date.today()
        self.display_date = date.today()  # Дата для відображення календаря
        
        # Місяці
        self.months = [
            "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
            "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
        ]
        
        # Дні тижня
        self.weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        
        # Ініціалізація UI
        self._build_ui()
        self._update_calendar()
    
    def _build_ui(self):
        """Створює UI компонента"""
        
        # Заголовок з навігацією
        self.header = ft.Row([
            # Кнопка попереднього місяця
            ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                on_click=self._prev_month,
                tooltip="Попередній місяць"
            ),
            # Назва місяця та року
            ft.Text(
                "",
                size=18,
                weight=ft.FontWeight.BOLD,
                expand=True,
                text_align=ft.TextAlign.CENTER
            ),
            # Кнопка наступного місяця
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                on_click=self._next_month,
                tooltip="Наступний місяць"
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        # Дні тижня
        self.weekdays_row = ft.Row([
            ft.Container(
                content=ft.Text(day, size=12, weight=ft.FontWeight.BOLD),
                width=40,
                height=30,
                alignment=ft.alignment.center,
                bgcolor=ft.Colors.GREY_100,
                border_radius=5
            ) for day in self.weekdays
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        
        # Календар
        self.calendar_grid = ft.Column(spacing=2)
        
        # Кнопка "Сьогодні"
        self.today_button = ft.ElevatedButton(
            text="Сьогодні",
            on_click=self._go_to_today,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_100,
                color=ft.Colors.BLUE_800
            )
        )
        
        # Основний контейнер
        self.content = ft.Column([
            ft.Text(self.label, size=16, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column([
                    self.header,
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    self.weekdays_row,
                    ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                    self.calendar_grid,
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    self.today_button
                ], spacing=0),
                bgcolor=ft.Colors.WHITE,
                border_radius=15,
                border=ft.border.all(1, ft.Colors.GREY_300),
                padding=15,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=15,
                    color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                    offset=ft.Offset(0, 5)
                )
            )
        ], spacing=10)
    
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
                        bg_color = ft.Colors.BLUE_500
                        text_color = ft.Colors.WHITE
                        weight = ft.FontWeight.BOLD
                    elif is_today:
                        bg_color = ft.Colors.BLUE_100
                        text_color = ft.Colors.BLUE_800
                        weight = ft.FontWeight.BOLD
                    else:
                        bg_color = ft.Colors.TRANSPARENT
                        text_color = ft.Colors.BLACK
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
        
        if self.on_date_changed:
            self.on_date_changed(selected_date)
    
    def _prev_month(self, e):
        """Попередній місяць"""
        if self.display_date.month == 1:
            self.display_date = self.display_date.replace(year=self.display_date.year - 1, month=12)
        else:
            self.display_date = self.display_date.replace(month=self.display_date.month - 1)
        self._update_calendar()
    
    def _next_month(self, e):
        """Наступний місяць"""
        if self.display_date.month == 12:
            self.display_date = self.display_date.replace(year=self.display_date.year + 1, month=1)
        else:
            self.display_date = self.display_date.replace(month=self.display_date.month + 1)
        self._update_calendar()
    
    def _go_to_today(self, e):
        """Перейти до сьогоднішньої дати"""
        self.current_date = date.today()
        self.display_date = date.today()
        self._update_calendar()
        
        if self.on_date_changed:
            self.on_date_changed(self.current_date)
    
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

def main(page: ft.Page):
    """Головна функція для тестування"""
    page.title = "Сучасний Date Picker"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 50
    
    def on_date_changed(selected_date: date):
        print(f"Вибрана дата: {selected_date}")
    
    # Створюємо date picker
    date_picker = ModernDatePicker(
        label="Дата покупки",
        on_date_changed=on_date_changed,
        page=page
    )
    
    # Додаємо на сторінку
    page.add(
        ft.Column([
            ft.Text("Сучасний Date Picker", size=24, weight=ft.FontWeight.BOLD),
            date_picker
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

if __name__ == "__main__":
    ft.app(target=main)
