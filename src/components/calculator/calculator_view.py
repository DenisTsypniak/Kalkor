# --- START OF FILE src/components/calculator/calculator_view.py ---

import flet as ft
import re
from typing import Callable
import asyncio
from src.utils.localization import LocalizationManager
from src.app.app_state import AppState


class Calculator(ft.Column):
    """
    Новий самодостатній компонент-калькулятор у стилі iOS для AlertDialog.
    ВЕРСІЯ 3 - фінальна.
    """
    # --- РЕФАКТОРИНГ: Винесення розмірів у константи ---
    CALCULATOR_WIDTH = 280
    CALCULATOR_HEIGHT = 500
    BUTTON_SIZE = 60

    def __init__(self, page: ft.Page, loc: LocalizationManager, app_state: AppState):
        super().__init__(
            width=self.CALCULATOR_WIDTH,
            height=self.CALCULATOR_HEIGHT,
            spacing=10,
            alignment=ft.MainAxisAlignment.END,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.app_page = page
        self.loc = loc
        app_state.register_on_language_change(self._on_lang_change)

        self.display_history = ft.Text("", color=ft.Colors.WHITE70, size=18, text_align=ft.TextAlign.RIGHT,
                                       no_wrap=True)
        self.display_main = ft.Text("0", color=ft.Colors.WHITE, size=65, text_align=ft.TextAlign.RIGHT, max_lines=1,
                                    no_wrap=True)

        self.ac_button_text = ft.Text("AC", size=24, weight=ft.FontWeight.W_400)

        self.copy_switcher = ft.AnimatedSwitcher(
            content=ft.Icon(ft.Icons.COPY_ALL_OUTLINED),
            transition=ft.AnimatedSwitcherTransition.SCALE,
            duration=300,
            reverse_duration=100
        )

        self.expression = ""
        self.just_calculated = False

        self.buttons = {}

        self._build_ui()

    async def _on_lang_change(self, lang_code: str):
        self.copy_button.tooltip = self.loc.get("calculator_copy_tooltip")
        if self.display_main.value == "Помилка" or self.display_main.value == "Error" or self.display_main.value == "Ошибка":
            self.display_main.value = self.loc.get("calculator_error")
        if self.page:
            self.page.update()

    async def _on_keyboard(self, e: ft.KeyboardEvent):
        key_map = {
            "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
            "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
            ".": ".", ",": ".",
            "+": "+", "-": "-", "*": "*", "/": "/",
            "Enter": "=", "=": "=",
            "Backspace": "AC", "Delete": "AC",
            "%": "%",
            "Numpad 0": "0", "Numpad 1": "1", "Numpad 2": "2",
            "Numpad 3": "3", "Numpad 4": "4", "Numpad 5": "5",
            "Numpad 6": "6", "Numpad 7": "7", "Numpad 8": "8",
            "Numpad 9": "9",
            "Numpad Decimal": ".", "Numpad Add": "+",
            "Numpad Subtract": "-", "Numpad Multiply": "*",
            "Numpad Divide": "/", "Numpad Enter": "="
        }
        if e.key in key_map:
            button_data = key_map[e.key]
            if button_data in self.buttons:
                await self._simulate_button_click(self.buttons[button_data])

    async def _simulate_button_click(self, button_control: ft.Container):
        mock_event = ft.ControlEvent(
            target=button_control.uid,
            name="click",
            data="",
            control=button_control,
            page=self.app_page
        )
        await self._on_button_click(mock_event)

    async def _handle_copy_click(self, e):
        result_to_copy = self.get_result()
        if result_to_copy:
            self.app_page.set_clipboard(result_to_copy)
            self.copy_switcher.content = ft.Icon(ft.Icons.CHECK_ROUNDED, color=ft.Colors.LIGHT_GREEN_ACCENT_700)
            self.app_page.update()
            await asyncio.sleep(1)
            self.copy_switcher.content = ft.Icon(ft.Icons.COPY_ALL_OUTLINED)
            self.app_page.update()

    def _build_ui(self):
        FUNC_BG, OP_BG, NUM_BG = "#A5A5A5", "#FF9F0A", "#333333"
        # --- РЕФАКТОРИНГ: Використання константи ---
        BUTTON_SIZE = self.BUTTON_SIZE

        self.copy_button = ft.Container(
            content=self.copy_switcher,
            alignment=ft.alignment.center,
            bgcolor=OP_BG,
            border_radius=BUTTON_SIZE / 2,
            data="copy",
            on_click=self._handle_copy_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            tooltip=self.loc.get("calculator_copy_tooltip")
        )

        def create_op_button(text_content, data):
            btn = ft.Container(
                content=ft.Text(text_content, size=32, weight=ft.FontWeight.W_300),
                padding=ft.padding.only(bottom=4),
                alignment=ft.alignment.center,
                bgcolor=OP_BG,
                border_radius=BUTTON_SIZE / 2,
                data=data,
                on_click=lambda e: self.app_page.run_task(self._on_button_click, e),
                width=BUTTON_SIZE,
                height=BUTTON_SIZE
            )
            self.buttons[data] = btn
            return btn

        def create_button(text_content, bgcolor, data):
            btn = ft.Container(
                content=ft.Text(text_content, size=28, weight=ft.FontWeight.W_400),
                alignment=ft.alignment.center,
                bgcolor=bgcolor,
                border_radius=BUTTON_SIZE / 2,
                data=data,
                on_click=lambda e: self.app_page.run_task(self._on_button_click, e),
                width=BUTTON_SIZE,
                height=BUTTON_SIZE
            )
            self.buttons[data] = btn
            return btn

        button_ac = ft.Container(
            content=self.ac_button_text,
            alignment=ft.alignment.center,
            bgcolor=FUNC_BG,
            border_radius=BUTTON_SIZE / 2,
            data="AC",
            on_click=lambda e: self.app_page.run_task(self._on_button_click, e),
            width=BUTTON_SIZE,
            height=BUTTON_SIZE
        )
        self.buttons["AC"] = button_ac

        self.controls = [
            ft.Container(
                content=ft.Column(
                    [self.display_history, self.display_main],
                    horizontal_alignment=ft.CrossAxisAlignment.END, spacing=5,
                ),
                padding=ft.padding.symmetric(horizontal=20), height=150,
                alignment=ft.alignment.bottom_right
            ),
            ft.Row(controls=[
                button_ac, create_button("±", FUNC_BG, "+/-"), create_button("%", FUNC_BG, "%"),
                create_op_button("÷", "/")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=[
                create_button("7", NUM_BG, "7"), create_button("8", NUM_BG, "8"), create_button("9", NUM_BG, "9"),
                create_op_button("×", "*")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=[
                create_button("4", NUM_BG, "4"), create_button("5", NUM_BG, "5"), create_button("6", NUM_BG, "6"),
                create_op_button("−", "-")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=[
                create_button("1", NUM_BG, "1"), create_button("2", NUM_BG, "2"), create_button("3", NUM_BG, "3"),
                create_op_button("+", "+")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=[
                self.copy_button, create_button("0", NUM_BG, "0"), create_button(",", NUM_BG, "."),
                create_op_button("=", "=")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]

    def _update_ac_button(self):
        if self.display_main.value == "0" and not self.expression:
            self.ac_button_text.value = "AC"
        else:
            self.ac_button_text.value = "C"

    def _adjust_font_size(self):
        length = len(self.display_main.value.replace(",", "").replace("-", ""))
        if length >= 7:
            self.display_main.size = max(28, 65 - (length - 6) * 7)
        else:
            self.display_main.size = 65

    async def _on_button_click(self, e: ft.ControlEvent):
        data = e.control.data
        display = self.display_main

        if data.isdigit():
            if self.just_calculated or display.value == "0":
                display.value = data
            else:
                display.value += data
            self.just_calculated = False
        elif data == "." and "." not in display.value:
            display.value += "."
        elif data in "+-*/":
            current_val = display.value.replace(',', '.')
            if self.expression and self.expression[-1] in "+-*/" and display.value == "0":
                self.expression = self.expression[:-1] + data
            else:
                self.expression += current_val + data

            self.display_history.value = self.expression.replace("/", "÷").replace("*", "×")
            display.value = "0"
            self.just_calculated = False

        elif data == "=":
            if not self.expression: return
            self.expression += display.value.replace(',', '.')
            try:
                if self.expression and self.expression[-1] in "+-*/":
                    self.expression = self.expression[:-1]

                result = round(eval(self.expression), 6)
                display.value = str(result).replace('.', ',').removesuffix(',0')
            except Exception:
                display.value = self.loc.get("calculator_error")
            self.expression = ""
            self.just_calculated = True
            self.display_history.value = ""
        elif data == "AC":
            if self.ac_button_text.value == "C":
                if display.value != "0":
                    display.value = "0"
                else:
                    self.expression = ""
                    self.display_history.value = ""
            else:
                display.value = "0"
                self.expression = ""
                self.display_history.value = ""
        elif data == "+/-" and display.value != "0":
            if display.value != self.loc.get("calculator_error"):
                display.value = display.value[1:] if display.value.startswith('-') else '-' + display.value
        elif data == "%":
            if display.value != self.loc.get("calculator_error"):
                try:
                    display.value = str(float(display.value.replace(',', '.')) / 100).replace('.', ',')
                except ValueError:
                    pass

        self._adjust_font_size()
        self._update_ac_button()

        if self.app_page:
            self.app_page.update()

    def show(self, initial_value: str = "0"):
        self.display_main.value = initial_value.replace('.', ',') if initial_value else "0"
        self.expression = ""
        self.display_history.value = ""
        self.just_calculated = False
        self._update_ac_button()
        self._adjust_font_size()

    def get_result(self) -> str:
        result = self.display_main.value
        return "0" if result == self.loc.get("calculator_error") else result.replace(',', '.')