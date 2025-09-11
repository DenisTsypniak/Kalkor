import flet as ft
from src.app.app_state import AppState
from src.data import data_manager as dm
from src.utils import config as cfg
from datetime import datetime, timedelta
from collections import defaultdict
import math
import asyncio
from src.utils.localization import LocalizationManager
from src.views.base_view import BaseView
from src.utils.ui.helpers import format_number_k, format_number_full

# Імпортуємо нові системи
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors

import calendar

logger = get_logger(__name__)




class AnalyticsView(BaseView):
    def __init__(self, page: ft.Page, app_state: AppState, loc: LocalizationManager):
        super().__init__(app_state, loc, visible=False, expand=True)
        self.page = page
        self.app_state.register_on_profile_change(self.handle_profile_change)
        self.app_state.register_on_language_change(self._on_lang_change)
        self.selected_period = cfg.ANALYTICS_PERIOD_DAY
        self.chart: ft.BarChart | None = None
        self.last_hovered_group_index = -1
        self.week_day_names = []
        self._update_weekday_names()
        self.start_date: datetime | None = None
        self.end_date: datetime | None = None
        self.last_update_hour: int = -1
        self.updater_task: asyncio.Task | None = None
        
        # Змінні для summary елементів (для оновлення локалізації)
        self.summary_total_income_text = None
        self.summary_avg_income_text = None
        self.summary_most_profitable_text = None
        
        self._create_pickers()
        self._create_controls()
        self._build_ui()

    def _update_weekday_names(self):
        self.week_day_names = [self.loc.get("analytics_weekday_mon"), self.loc.get("analytics_weekday_tue"),
                               self.loc.get("analytics_weekday_wed"), self.loc.get("analytics_weekday_thu"),
                               self.loc.get("analytics_weekday_fri"), self.loc.get("analytics_weekday_sat"),
                               self.loc.get("analytics_weekday_sun")]

    async def _on_lang_change(self, lang_code: str):
        # Викликаємо базовий метод
        await super()._on_lang_change(lang_code)
        
        # Оновлюємо заголовок сторінки
        if hasattr(self, 'page_title_text'):
            self.page_title_text.value = self.loc.get("analytics_title", default="Аналітика")
        
        # Оновлюємо тексти без важкого перебілду/перерахунку чарту, щоб уникнути сірої паузи
        self._update_weekday_names()
        self.no_profile_placeholder.content.value = self.loc.get("analytics_placeholder_no_profile")
        self.no_data_placeholder.controls[1].value = self.loc.get("analytics_placeholder_no_data")
        self.no_data_placeholder.controls[2].value = self.loc.get("analytics_placeholder_no_data_subtitle")
        self.period_buttons[0].content.value = self.loc.get("analytics_period_day")
        self.period_buttons[1].content.value = self.loc.get("analytics_period_week")
        self.period_buttons[2].content.value = self.loc.get("analytics_period_month")
        self.period_buttons[3].content.value = self.loc.get("analytics_period_custom")
        self.start_date_button.text = self.loc.get("analytics_datepicker_start_button")
        self.end_date_button.text = self.loc.get("analytics_datepicker_end_button")
        
        # Оновлення summary елементів
        if self.summary_total_income_text:
            self.summary_total_income_text.value = self.loc.get("analytics_summary_total_income")
        if self.summary_avg_income_text:
            # Оновлюємо відповідно до поточного періоду
            if self.selected_period == cfg.ANALYTICS_PERIOD_DAY:
                self.summary_avg_income_text.value = self.loc.get("analytics_summary_avg_income_hour")
            elif self.selected_period == cfg.ANALYTICS_PERIOD_WEEK:
                self.summary_avg_income_text.value = self.loc.get("analytics_summary_avg_income_day")
            elif self.selected_period == cfg.ANALYTICS_PERIOD_MONTH:
                self.summary_avg_income_text.value = self.loc.get("analytics_summary_avg_income_week")
            else:  # CUSTOM
                self.summary_avg_income_text.value = self.loc.get("analytics_summary_avg_income_day")
        if self.summary_most_profitable_text:
            # Оновлюємо відповідно до поточного періоду
            if self.selected_period == cfg.ANALYTICS_PERIOD_DAY:
                self.summary_most_profitable_text.value = self.loc.get("analytics_summary_most_profitable_hour")
            else:
                self.summary_most_profitable_text.value = self.loc.get("analytics_summary_most_profitable_day")
        
        # Не перевизначаємо datepickers і не перераховуємо чарт тут
        self.update()
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        try:
            # Закриваємо всі діалоги аналітики
            dialog_attributes = [
                'datepicker_start', 'datepicker_end'
            ]
            
            for attr_name in dialog_attributes:
                if hasattr(self, attr_name):
                    dialog = getattr(self, attr_name)
                    if dialog and hasattr(dialog, 'open'):
                        dialog.open = False
            
            # Викликаємо базовий метод для закриття загальних діалогів
            super()._close_all_dialogs()
        except Exception as e:
            print(f"Error closing analytics dialogs: {e}")
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # В аналітиці немає текстових полів для введення, тому використовуємо базовий метод
            super()._restore_focus()
        except Exception as e:
            print(f"Error restoring focus in analytics view: {e}")

    def _create_pickers(self):
        self.datepicker_start = ft.DatePicker(on_change=self.on_start_date_change,
                                              help_text=self.loc.get("analytics_datepicker_start_help"))
        self.datepicker_end = ft.DatePicker(on_change=self.on_end_date_change,
                                            help_text=self.loc.get("analytics_datepicker_end_help"))

    async def _time_updater_task(self):
        while self.visible:
            now = datetime.now()
            if now.hour != self.last_update_hour:
                self.last_update_hour = now.hour
                if self.selected_period == cfg.ANALYTICS_PERIOD_DAY and self.page:
                    await self._update_chart(animate=True)
            await asyncio.sleep(20)

    async def on_chart_event(self, e: ft.BarChartEvent):
        if not self.chart: return
        current_index = e.group_index if e.group_index is not None else -1
        if self.last_hovered_group_index != -1 and self.last_hovered_group_index != current_index:
            if self.last_hovered_group_index < len(self.chart.bar_groups):
                group = self.chart.bar_groups[self.last_hovered_group_index]
                if group.bar_rods and group.bar_rods[0].to_y > 0:
                    rod = group.bar_rods[0]
                    rod.to_y = rod.data
                    rod.color = ft.Colors.with_opacity(0.8, ft.Colors.WHITE)
                    rod.border_side = ft.BorderSide(width=0, color=ft.Colors.TRANSPARENT)
        if current_index != -1 and current_index < len(self.chart.bar_groups):
            group = self.chart.bar_groups[current_index]
            if group.bar_rods and group.bar_rods[0].to_y > 0:
                rod = group.bar_rods[0]
                if rod.data > 0:
                    rod.to_y = rod.data * 1.05
                    rod.color = ft.Colors.GREEN_800
                    rod.border_side = ft.BorderSide(width=2, color=ft.Colors.BLACK)
        self.last_hovered_group_index = current_index
        self.chart.update()

    async def handle_period_change(self, e):
        new_period = e.control.data
        if self.selected_period == new_period: return
        self.selected_period = new_period

        # ВИПРАВЛЕННЯ БАГУ: Примусово оновлюємо візуальний стан кнопок
        for button in self.period_buttons:
            button.bgcolor = ft.Colors.BLUE_GREY_700 if button.data == new_period else ft.Colors.WHITE12
            if button.page:
                button.update()

        self.custom_date_container.visible = False
        await self._update_chart(animate=True)

    async def handle_custom_period_click(self, e):
        new_period = e.control.data
        if self.selected_period != new_period:
            self.selected_period = new_period
            self.custom_date_container.visible = True

            # ВИПРАВЛЕННЯ БАГУ: Примусово оновлюємо візуальний стан кнопок
            for button in self.period_buttons:
                button.bgcolor = ft.Colors.BLUE_GREY_700 if button.data == new_period else ft.Colors.WHITE12
                if button.page:
                    button.update()

            self.update()
            if self.start_date and self.end_date: await self._update_chart(animate=True)
        else:
            self.custom_date_container.visible = not self.custom_date_container.visible
            self.update()

    async def _update_chart(self, animate: bool = False):
        if animate:
            self.animated_switcher.content = self.loading_indicator
            self.update()

        # --- ЗМІНЕНО: Використовуємо ID з app_state ---
        if not self.app_state.current_profile:
            self.animated_switcher.content = self.no_data_placeholder
            self.update()
            return

        profile_id = self.app_state.current_profile['id']
        if self.selected_period == cfg.ANALYTICS_PERIOD_CUSTOM and (not self.start_date or not self.end_date):
            self.chart_container.content = self.no_data_placeholder
            self.summary_container.content = self.create_summary_view([], defaultdict(float))
            self.animated_switcher.content = self.content_column
            self.update()
            return

        # --- ЗМІНЕНО: Передаємо ID в dm.load_transactions ---
        all_transactions = await dm.load_transactions(profile_id)
        now = datetime.now()
        income_transactions = [t for t in all_transactions if t['type'] == cfg.TRANSACTION_TYPE_INCOME and t[
            'category'] != cfg.INITIAL_BALANCE_CATEGORY]
        summary_data_source = []
        chart_data = {"bar_groups": [], "x_labels": [], "chart_top_y": 100}
        period_map = {
            cfg.ANALYTICS_PERIOD_DAY: (self._build_day_data, cfg.TIME_FILTER_DAY),
            cfg.ANALYTICS_PERIOD_WEEK: (self._build_week_data, cfg.TIME_FILTER_WEEK),
            cfg.ANALYTICS_PERIOD_MONTH: (self._build_month_data, cfg.TIME_FILTER_MONTH),
            cfg.ANALYTICS_PERIOD_CUSTOM: (self._build_custom_data, cfg.ANALYTICS_PERIOD_CUSTOM)
        }
        if self.selected_period in period_map:
            build_func, filter_type = period_map[self.selected_period]
            chart_data = build_func(now, income_transactions)
            summary_data_source = self._filter_transactions_by_time(income_transactions, filter_type, now)
        bar_groups, x_labels, chart_top_y = chart_data.get("bar_groups", []), chart_data.get("x_labels",
                                                                                             []), chart_data.get(
            "chart_top_y", 100)
        aggregated_income_data = defaultdict(float)
        agg_key_func = (lambda t: datetime.fromisoformat(t['timestamp']).replace(minute=0, second=0,
                                                                                 microsecond=0)) if self.selected_period == cfg.ANALYTICS_PERIOD_DAY else (
            lambda t: datetime.fromisoformat(t['timestamp']).date())
        for t in summary_data_source:
            aggregated_income_data[agg_key_func(t)] += float(t['amount'])
        self.summary_container.content = self.create_summary_view(summary_data_source, aggregated_income_data)
        if not bar_groups:
            self.chart_container.content = self.no_data_placeholder
        else:
            y_step = max(1, math.ceil(chart_top_y / 5))
            y_labels = [ft.ChartAxisLabel(value=y, label=ft.Text(format_number_k(y), color=ft.Colors.WHITE70, size=11))
                        for y in range(0, int(chart_top_y) + y_step, y_step)]
            for group in bar_groups:
                if group.bar_rods: group.bar_rods[0].bg_to_y = chart_top_y
            self.chart = ft.BarChart(bar_groups=bar_groups, bottom_axis=ft.ChartAxis(labels=x_labels, labels_size=60),
                                     left_axis=ft.ChartAxis(labels=y_labels, labels_size=40, show_labels=True),
                                     horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.WHITE10, width=1),
                                     on_chart_event=self.on_chart_event, interactive=True, expand=True)
            self.chart_container.content = self.chart
        self.last_hovered_group_index = -1
        self.animated_switcher.content = self.content_column
        self.update()

    def _filter_transactions_by_time(self, transactions: list, time_filter_type: str, now: datetime) -> list:
        if time_filter_type == cfg.ANALYTICS_PERIOD_CUSTOM:
            if self.start_date and self.end_date:
                start_dt = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                return [t for t in transactions if start_dt <= datetime.fromisoformat(t['timestamp']) <= end_dt]
            return []
        cutoff_time = now
        if time_filter_type == cfg.TIME_FILTER_DAY:
            cutoff_time = now - timedelta(hours=24)
        elif time_filter_type == cfg.TIME_FILTER_WEEK:
            cutoff_time = now - timedelta(days=7)
        elif time_filter_type == cfg.TIME_FILTER_MONTH:
            last_month = now.month - 1
            last_year = now.year
            if last_month == 0: last_month, last_year = 12, last_year - 1
            day = min(now.day, calendar.monthrange(last_year, last_month)[1])
            cutoff_time = datetime(last_year, last_month, day)
        return [t for t in transactions if datetime.fromisoformat(t['timestamp']) >= cutoff_time]

    def _get_chart_top_y(self, data_values):
        max_y = max(data_values) if data_values else 0
        if max_y == 0: return 100000
        power = 10 ** (len(str(int(max_y))) - 1)
        return math.ceil(max_y / power) * power

    def _build_day_data(self, now, income_transactions):
        aggregated_data = defaultdict(float)
        cutoff_time = now - timedelta(hours=24)
        filtered = [t for t in income_transactions if datetime.fromisoformat(t['timestamp']) >= cutoff_time]
        for t in filtered:
            aggregated_data[datetime.fromisoformat(t['timestamp']).replace(minute=0, second=0, microsecond=0)] += t[
                'amount']
        dt_sequence = [(now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0) for i in range(23, -1, -1)]
        chart_top_y = self._get_chart_top_y(aggregated_data.values())
        bar_groups, x_labels = [], []
        for i, dt_key in enumerate(dt_sequence):
            value = aggregated_data.get(dt_key, 0)
            bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[
                ft.BarChartRod(to_y=value, width=18, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                               tooltip=f"{format_number_full(value)}$", border_radius=6, data=value)]))
            show_date_label = (dt_key.hour == 0 or i == 0)
            is_current_hour = (dt_key.hour == now.hour and dt_key.date() == now.date())
            label_content = [ft.Text(f"{dt_key.hour:02d}:00", size=10,
                                     weight=ft.FontWeight.BOLD if is_current_hour else ft.FontWeight.NORMAL,
                                     color=ft.Colors.AMBER_300 if is_current_hour else ft.Colors.WHITE70)]
            if show_date_label: label_content.append(ft.Text(dt_key.strftime('%d.%m'), size=8, color=ft.Colors.WHITE38))
            x_labels.append(ft.ChartAxisLabel(value=i, label=ft.Column(label_content, spacing=2,
                                                                       horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
        return {"bar_groups": bar_groups, "x_labels": x_labels, "chart_top_y": chart_top_y}

    def _build_week_data(self, now, income_transactions):
        aggregated_data, bar_groups, x_labels = defaultdict(float), [], []
        cutoff_time = now.date() - timedelta(days=6)
        filtered = [t for t in income_transactions if datetime.fromisoformat(t['timestamp']).date() >= cutoff_time]
        for t in filtered: aggregated_data[datetime.fromisoformat(t['timestamp']).date()] += t['amount']
        date_sequence = [cutoff_time + timedelta(days=i) for i in range(7)]
        chart_top_y = self._get_chart_top_y(aggregated_data.values())
        for i, date_key in enumerate(date_sequence):
            value = aggregated_data.get(date_key, 0)
            bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[
                ft.BarChartRod(to_y=value, width=30, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                               tooltip=f"{format_number_full(value)}$", border_radius=8, data=value)]))
            is_today = (date_key == now.date())
            label_content = ft.Column([ft.Text(self.week_day_names[date_key.weekday()], size=11,
                                               weight=ft.FontWeight.BOLD if is_today else ft.FontWeight.NORMAL,
                                               color=ft.Colors.AMBER_300 if is_today else ft.Colors.WHITE70),
                                       ft.Text(date_key.strftime('%d.%m'), size=9, color=ft.Colors.WHITE54)], spacing=2,
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            x_labels.append(ft.ChartAxisLabel(value=i, label=label_content))
        return {"bar_groups": bar_groups, "x_labels": x_labels, "chart_top_y": chart_top_y}

    def _build_month_data(self, now, income_transactions):
        aggregated_data = defaultdict(float)
        last_month_date = now - timedelta(days=30)

        filtered = [t for t in income_transactions if
                    datetime.fromisoformat(t['timestamp']).date() >= last_month_date.date()]

        for t in filtered:
            t_date = datetime.fromisoformat(t['timestamp']).date()
            week_key = (t_date.isocalendar().year, t_date.isocalendar().week)
            aggregated_data[week_key] += t['amount']

        if not aggregated_data:
            return {"bar_groups": [], "x_labels": [], "chart_top_y": 100}

        sorted_week_keys = sorted(aggregated_data.keys())
        chart_top_y = self._get_chart_top_y(aggregated_data.values())
        bar_groups, x_labels = [], []

        for i, week_key in enumerate(sorted_week_keys):
            year, week_num = week_key
            value = aggregated_data.get(week_key, 0)
            week_start = datetime.fromisocalendar(year, week_num, 1)
            week_end = week_start + timedelta(days=6)
            tooltip_text = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}\n{format_number_full(value)}$"
            bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[
                ft.BarChartRod(to_y=value, width=35, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                               tooltip=tooltip_text, border_radius=8, data=value)]))
            label_text = f"{week_start.strftime('%d.%m')}-\n{week_end.strftime('%d.%m')}"
            is_current_week = (now.isocalendar().year == year and now.isocalendar().week == week_num)
            label_content = ft.Text(label_text, size=9, text_align=ft.TextAlign.CENTER,
                                    weight=ft.FontWeight.BOLD if is_current_week else ft.FontWeight.NORMAL,
                                    color=ft.Colors.AMBER_300 if is_current_week else ft.Colors.WHITE70)
            x_labels.append(ft.ChartAxisLabel(value=i, label=label_content))

        return {"bar_groups": bar_groups, "x_labels": x_labels, "chart_top_y": chart_top_y}

    # --- ЗАМІНИТИ ВЕСЬ МЕТОД ---
    def _build_custom_data(self, now, income_transactions):
        if not self.start_date or not self.end_date: return {"bar_groups": [], "x_labels": [], "chart_top_y": 100}

        num_days = (self.end_date.date() - self.start_date.date()).days + 1

        # Якщо період занадто великий, групуємо по тижнях
        if num_days > 60:
            aggregated_data = defaultdict(float)
            filtered = [t for t in income_transactions if
                        self.start_date.date() <= datetime.fromisoformat(t['timestamp']).date() <= self.end_date.date()]

            for t in filtered:
                t_date = datetime.fromisoformat(t['timestamp']).date()
                week_key = (t_date.isocalendar().year, t_date.isocalendar().week)
                aggregated_data[week_key] += t['amount']

            if not aggregated_data: return {"bar_groups": [], "x_labels": [], "chart_top_y": 100}

            sorted_week_keys = sorted(aggregated_data.keys())
            chart_top_y = self._get_chart_top_y(aggregated_data.values())
            bar_groups, x_labels = [], []

            for i, week_key in enumerate(sorted_week_keys):
                year, week_num = week_key
                value = aggregated_data.get(week_key, 0)
                week_start = datetime.fromisocalendar(year, week_num, 1)
                week_end = week_start + timedelta(days=6)
                tooltip_text = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}\n{format_number_full(value)}$"

                bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[
                    ft.BarChartRod(to_y=value, width=max(10, 300 / len(sorted_week_keys)),
                                   color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                                   tooltip=tooltip_text, border_radius=8, data=value)]))

                label_text = f"{week_start.strftime('%d.%m')}-\n{week_end.strftime('%d.%m')}"
                is_current_week = (now.isocalendar().year == year and now.isocalendar().week == week_num)
                label_content = ft.Text(label_text, size=9, text_align=ft.TextAlign.CENTER,
                                        weight=ft.FontWeight.BOLD if is_current_week else ft.FontWeight.NORMAL,
                                        color=ft.Colors.AMBER_300 if is_current_week else ft.Colors.WHITE70)
                x_labels.append(ft.ChartAxisLabel(value=i, label=label_content))

            return {"bar_groups": bar_groups, "x_labels": x_labels, "chart_top_y": chart_top_y}

        # Якщо період нормальний, залишаємо групування по днях
        else:
            aggregated_data, bar_groups, x_labels = defaultdict(float), [], []
            date_sequence = [self.start_date.date() + timedelta(days=i) for i in range(num_days)]
            filtered = [t for t in income_transactions if
                        self.start_date.date() <= datetime.fromisoformat(t['timestamp']).date() <= self.end_date.date()]
            for t in filtered: aggregated_data[datetime.fromisoformat(t['timestamp']).date()] += t['amount']
            chart_top_y = self._get_chart_top_y(aggregated_data.values())

            # Розумний розрахунок кроку для підписів
            max_labels = 12
            step = 1
            if len(date_sequence) > max_labels:
                step = math.ceil(len(date_sequence) / max_labels)

            for i, date_key in enumerate(date_sequence):
                value = aggregated_data.get(date_key, 0)
                bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[
                    ft.BarChartRod(to_y=value, width=max(5, 400 / len(date_sequence)),
                                   color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                                   tooltip=f"{date_key.strftime('%d.%m')}\n{format_number_full(value)}$",
                                   border_radius=6, data=value)]))

                # Показуємо перший, останній і проміжні підписи
                if i == 0 or i == len(date_sequence) - 1 or i % step == 0:
                    x_labels.append(
                        ft.ChartAxisLabel(value=i, label=ft.Text(date_key.strftime("%d.%m"), size=9, rotate=-0.4)))

            return {"bar_groups": bar_groups, "x_labels": x_labels, "chart_top_y": chart_top_y}

    def create_summary_view(self, filtered_income_transactions: list, aggregated_income_data: defaultdict):
        if not filtered_income_transactions:
            return ft.Container(padding=15, border=ft.border.all(1, ft.Colors.WHITE12), border_radius=8,
                                content=ft.Column([ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.WHITE54),
                                                           ft.Text(self.loc.get("analytics_summary_no_data"),
                                                                   color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)],
                                                          alignment=ft.MainAxisAlignment.CENTER),
                                                   ft.Text(self.loc.get("analytics_summary_no_data_subtitle"), size=12,
                                                           color=ft.Colors.WHITE54, text_align=ft.TextAlign.CENTER)],
                                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5))
        total_income = sum(aggregated_income_data.values())
        avg_label_key, avg_val = "N/A", 0
        max_label_key, max_val_str = "N/A", "N/A"
        if aggregated_income_data:
            max_time_key, max_value = max(aggregated_income_data.items(), key=lambda item: item[1])
            if self.selected_period == cfg.ANALYTICS_PERIOD_DAY:
                avg_label_key = "analytics_summary_avg_income_hour"
                avg_val = total_income / 24
                max_label_key = "analytics_summary_most_profitable_hour"
                max_val_str = f"{format_number_full(max_value)}$ ({max_time_key.hour:02d}:00)"
            elif self.selected_period == cfg.ANALYTICS_PERIOD_WEEK:
                avg_label_key = "analytics_summary_avg_income_day"
                avg_val = total_income / 7
                max_label_key = "analytics_summary_most_profitable_day"
                max_val_str = f"{format_number_full(max_value)}$ ({max_time_key.strftime('%d.%m')})"
            elif self.selected_period == cfg.ANALYTICS_PERIOD_MONTH:
                avg_label_key = "analytics_summary_avg_income_week"
                avg_val = (total_income / 30) * 7
                max_label_key = "analytics_summary_most_profitable_day"
                max_val_str = f"{format_number_full(max_value)}$ ({max_time_key.strftime('%d.%m')})"
            elif self.selected_period == cfg.ANALYTICS_PERIOD_CUSTOM and self.start_date and self.end_date:
                num_days = (self.end_date.date() - self.start_date.date()).days + 1
                avg_label_key = "analytics_summary_avg_income_day"
                avg_val = total_income / num_days if num_days > 0 else 0
                max_label_key = "analytics_summary_most_profitable_day"
                max_val_str = f"{format_number_full(max_value)}$ ({max_time_key.strftime('%d.%m.%Y')})"
        self.summary_total_income_text = ft.Text(self.loc.get("analytics_summary_total_income"), weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70)
        self.summary_avg_income_text = ft.Text(self.loc.get(avg_label_key), color=ft.Colors.WHITE70)
        self.summary_most_profitable_text = ft.Text(self.loc.get(max_label_key), color=ft.Colors.WHITE70)
        
        return ft.Container(padding=15, border=ft.border.all(1, ft.Colors.WHITE12), border_radius=8, content=ft.Column(
            [ft.Row([self.summary_total_income_text,
                     ft.Text(f"{format_number_full(total_income)}$", color=ft.Colors.GREEN_300, size=16,
                             weight=ft.FontWeight.BOLD)]), ft.Row(
                [self.summary_avg_income_text,
                 ft.Text(f"{format_number_full(avg_val)}$")]),
             ft.Row([self.summary_most_profitable_text, ft.Text(max_val_str)])],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5))

    def _create_controls(self):
        self.no_profile_placeholder = ft.Container(
            content=ft.Text(self.loc.get("analytics_placeholder_no_profile"), style="headlineSmall",
                            text_align=ft.TextAlign.CENTER, color=ft.Colors.ON_SURFACE_VARIANT),
            alignment=ft.alignment.center, expand=True, visible=True)
        self.no_data_placeholder = ft.Column([ft.Icon(ft.Icons.QUERY_STATS_ROUNDED, size=60, color=ft.Colors.WHITE24),
                                              ft.Text(self.loc.get("analytics_placeholder_no_data"), size=16,
                                                      color=ft.Colors.WHITE54),
                                              ft.Text(self.loc.get("analytics_placeholder_no_data_subtitle"), size=12,
                                                      color=ft.Colors.WHITE38)], alignment=ft.MainAxisAlignment.CENTER,
                                             horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True,
                                             opacity=0.8)
        self.main_analytics_view = ft.Column(expand=True, spacing=15, visible=False, scroll=ft.ScrollMode.HIDDEN)
        self.header_title = ft.Text(self.loc.get("analytics_title"), style="headlineSmall", weight=ft.FontWeight.BOLD)
        self.subtitle_text = ft.Text(self.loc.get("analytics_subtitle"), color=ft.Colors.WHITE70)
        self.divider = ft.Divider(height=1, color=ft.Colors.WHITE24)
        self.period_buttons = [
            ft.Container(content=ft.Text(self.loc.get("analytics_period_day"), weight=ft.FontWeight.BOLD),
                         data=cfg.ANALYTICS_PERIOD_DAY, on_click=self.handle_period_change,
                         padding=ft.padding.symmetric(vertical=8, horizontal=16), border_radius=20,
                         bgcolor=ft.Colors.BLUE_GREY_700, animate=ft.Animation(200, "ease")),
            ft.Container(content=ft.Text(self.loc.get("analytics_period_week"), weight=ft.FontWeight.BOLD),
                         data=cfg.ANALYTICS_PERIOD_WEEK, on_click=self.handle_period_change,
                         padding=ft.padding.symmetric(vertical=8, horizontal=16), border_radius=20,
                         bgcolor=ft.Colors.WHITE12, animate=ft.Animation(200, "ease")),
            ft.Container(content=ft.Text(self.loc.get("analytics_period_month"), weight=ft.FontWeight.BOLD),
                         data=cfg.ANALYTICS_PERIOD_MONTH, on_click=self.handle_period_change,
                         padding=ft.padding.symmetric(vertical=8, horizontal=16), border_radius=20,
                         bgcolor=ft.Colors.WHITE12, animate=ft.Animation(200, "ease")),
            ft.Container(content=ft.Text(self.loc.get("analytics_period_custom"), weight=ft.FontWeight.BOLD),
                         data=cfg.ANALYTICS_PERIOD_CUSTOM, on_click=self.handle_custom_period_click,
                         padding=ft.padding.symmetric(vertical=8, horizontal=16), border_radius=20,
                         bgcolor=ft.Colors.WHITE12, animate=ft.Animation(200, "ease"))]
        self.period_buttons_row = ft.Row(controls=self.period_buttons, alignment=ft.MainAxisAlignment.CENTER,
                                         spacing=10)
        self.start_date_button = ft.ElevatedButton(self.loc.get("analytics_datepicker_start_button"),
                                                   icon=ft.Icons.CALENDAR_MONTH, on_click=self.open_datepicker_start)
        self.end_date_button = ft.ElevatedButton(self.loc.get("analytics_datepicker_end_button"),
                                                 icon=ft.Icons.CALENDAR_MONTH, on_click=self.open_datepicker_end)
        self.custom_date_container = ft.Container(
            content=ft.Row(controls=[self.start_date_button, self.end_date_button],
                           alignment=ft.MainAxisAlignment.CENTER, spacing=20), visible=False,
            margin=ft.margin.only(top=10))
        self.chart_container = ft.Container(content=None, expand=True, alignment=ft.alignment.center,
                                            padding=ft.padding.only(right=20, left=10, bottom=20))
        self.summary_container = ft.Container(padding=ft.padding.only(top=15, bottom=10))
        self.content_column = ft.Column([self.chart_container, self.summary_container], expand=True,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self.loading_indicator = ft.Column([ft.ProgressRing()], alignment=ft.MainAxisAlignment.CENTER,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        self.animated_switcher = ft.AnimatedSwitcher(content=self.content_column,
                                                     transition=ft.AnimatedSwitcherTransition.FADE, duration=300,
                                                     reverse_duration=100)

    def _build_ui(self):
        self.main_analytics_view.padding = ft.padding.only(left=20, top=20, right=20, bottom=10)
        
        # Створюємо красивий заголовок сторінки
        self.page_title_text = ft.Text(
            self.loc.get("analytics_title", default="Аналітика"),
            size=28,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        self.page_title = ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.ANALYTICS_OUTLINED,
                    size=32,
                    color=ft.Colors.PURPLE_400
                ),
                self.page_title_text
            ], spacing=12, alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.only(bottom=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.PURPLE_400))
        )
        
        # Створюємо основний контент без фону (фон буде глобальним)
        main_content = ft.Column([
            self.page_title,
            ft.Container(height=10), 
            self.period_buttons_row,
            self.custom_date_container, 
            self.animated_switcher
        ], expand=True)
        
        self.main_analytics_view.controls.clear()
        self.main_analytics_view.controls.append(main_content)
        self.controls.clear()
        self.controls.append(ft.Stack([self.no_profile_placeholder, self.main_analytics_view], expand=True))

    async def on_view_show(self):
        try:
            # Викликаємо базовий метод
            await super().on_view_show()
            
            # Перевіряємо чи маємо необхідні атрибути
            if not hasattr(self, '_set_attr_internal'):
                return
                
            if self.page:
                if self.datepicker_start not in self.page.overlay: self.page.overlay.append(self.datepicker_start)
                if self.datepicker_end not in self.page.overlay: self.page.overlay.append(self.datepicker_end)
            await self.handle_profile_change(self.app_state.current_profile)
            if self.updater_task is None or self.updater_task.done():
                self.last_update_hour = datetime.now().hour
                self.updater_task = asyncio.create_task(self._time_updater_task())
        except Exception:
            pass

    async def on_view_hide(self):
        try:
            # Викликаємо базовий метод
            await super().on_view_hide()
            
            # Зупиняємо оновлювач часу
            if self.updater_task and not self.updater_task.done():
                self.updater_task.cancel()
                self.updater_task = None
                
            # Очищаємо overlay елементи (тільки ті, що належать цьому view)
            if self.page and hasattr(self.page, 'overlay'):
                try:
                    for overlay_item in self.page.overlay[:]:
                        if (isinstance(overlay_item, ft.DatePicker) and 
                            hasattr(overlay_item, 'open') and 
                            overlay_item.open):
                            overlay_item.open = False
                except Exception:
                    pass
        except Exception:
            pass

    def open_datepicker_start(self, e):
        self.datepicker_start.open = True;
        self.page.update()

    def open_datepicker_end(self, e):
        self.datepicker_end.open = True;
        self.page.update()

    async def on_start_date_change(self, e):
        self.start_date = self.datepicker_start.value
        self.start_date_button.text = self.start_date.strftime("%d.%m.%Y")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            self.end_date, self.end_date_button.text = None, self.loc.get("analytics_datepicker_end_button")
        self.datepicker_start.open = False;
        self.page.update()
        if self.start_date and self.end_date: await self._update_chart(animate=True)

    async def on_end_date_change(self, e):
        self.end_date = self.datepicker_end.value
        self.end_date_button.text = self.end_date.strftime("%d.%m.%Y")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            self.start_date, self.start_date_button.text = None, self.loc.get("analytics_datepicker_start_button")
        self.datepicker_end.open = False;
        self.page.update()
        if self.start_date and self.end_date: await self._update_chart(animate=True)

    # --- ЗМІНЕНО: Приймає об'єкт профілю ---
    async def handle_profile_change(self, profile_data: dict | None):
        is_profile_selected = bool(profile_data)
        self.main_analytics_view.visible, self.no_profile_placeholder.visible = is_profile_selected, not is_profile_selected
        if is_profile_selected:
            self.start_date, self.end_date = None, None
            self.start_date_button.text, self.end_date_button.text = self.loc.get(
                "analytics_datepicker_start_button"), self.loc.get("analytics_datepicker_end_button")
            self.selected_period = cfg.ANALYTICS_PERIOD_DAY

            # ВИПРАВЛЕННЯ БАГУ: Примусово оновлюємо візуальний стан кнопок при зміні профілю
            for button in self.period_buttons:
                button.bgcolor = ft.Colors.BLUE_GREY_700 if button.data == self.selected_period else ft.Colors.WHITE12
                if button.page:
                    button.update()

            self.custom_date_container.visible = False
            await self._update_chart()
        else:
            self.animated_switcher.content = ft.Container()
        self.update()