# --- START OF FILE src/utils/config.py ---

import flet as ft
import os
import sys
import base64

APP_VERSION = "1.1.0"

GITHUB_REPO = "DenisTsypniak/Kalkor"
MAIN_EXE_NAME = "Kalkor.exe"
UPDATER_EXE_NAME = "updater.exe"

# --- КОНСТАНТИ ДОДАТКУ ---

# Типи транзакцій
TRANSACTION_TYPE_INCOME = "дохід"
TRANSACTION_TYPE_EXPENSE = "витрата"

# Спеціальні категорії
INITIAL_BALANCE_CATEGORY = "Початковий баланс"
CORRECTION_CATEGORY = "Корекція"
PROPERTY_SALE_CATEGORY = "Продаж майна"
PROPERTY_PURCHASE_CATEGORY = "Покупка майна"

# Фільтри часу для головної сторінки
TIME_FILTER_DAY = "day"
TIME_FILTER_WEEK = "week"
TIME_FILTER_MONTH = "month"
TIME_FILTER_ALL = "all"

# Періоди для сторінки аналітики
ANALYTICS_PERIOD_DAY = "ЗА ДЕНЬ"
ANALYTICS_PERIOD_WEEK = "ЗА ТИЖДЕНЬ"
ANALYTICS_PERIOD_MONTH = "ЗА МІСЯЦЬ"
ANALYTICS_PERIOD_CUSTOM = "СВІЙ ПЕРІОД"
ANALYTICS_PERIOD_ALL = "ЗА ВЕСЬ ЧАС"


# --------------------------

def resource_path(relative_path: str) -> str:
    """
    Отримує абсолютний шлях до ресурсу, працює як для розробки, так і для PyInstaller.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(project_root, relative_path)


def get_icon_b64(path_to_icon: str) -> str | None:
    """
    Знаходить іконку за відносним шляхом, читає її та повертає у форматі Base64.
    """
    try:
        abs_path = resource_path(path_to_icon)
        with open(abs_path, "rb") as f:
            b64_string = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64_string}"
    except Exception:
        pass
    return None


CHART_COLORS = [
    ft.Colors.BLUE_400,
    ft.Colors.ORANGE_400,
    ft.Colors.GREEN_400,
    ft.Colors.PURPLE_400,
    ft.Colors.RED_400,
    ft.Colors.TEAL_400,
    ft.Colors.PINK_400,
    ft.Colors.LIGHT_GREEN_400,
    ft.Colors.CYAN_400,
    ft.Colors.AMBER_400,
    ft.Colors.INDIGO_400,
    ft.Colors.LIME_400
]