# --- START OF FILE src/app/app_state.py ---

import asyncio

class AppState:
    """
    Зберігає загальний стан додатку, до якого мають доступ різні компоненти.
    Використовує механізм зворотних викликів (callbacks) для сповіщення
    компонентів про зміни.
    """

    def __init__(self):
        # --- ЗМІНЕНО: Зберігаємо весь об'єкт профілю (словник), а не тільки ім'я ---
        self._current_profile: dict | None = None
        self.on_profile_change_callbacks = []

        self._current_language: str = "uk"
        self.on_language_change_callbacks = []

        # --- ДОДАНО: Сповіщення про зміну транзакцій (щоб інші в'ю могли оновитись) ---
        self.on_transactions_change_callbacks = []

    @property
    def current_profile(self) -> dict | None:
        """Повертає словник з даними поточного активного профілю (id, name, avatar_b64)."""
        return self._current_profile

    @current_profile.setter
    def current_profile(self, new_profile_data: dict | None):
        """
        Встановлює новий профіль і сповіщає всіх підписників про зміну.
        Сповіщення відбувається тільки якщо нове значення відрізняється від старого.
        """
        # --- ЗМІНЕНО: Порівнюємо по ID, якщо це можливо ---
        old_id = self._current_profile['id'] if self._current_profile else None
        new_id = new_profile_data['id'] if new_profile_data else None

        if old_id != new_id:
            self._current_profile = new_profile_data
            for callback in self.on_profile_change_callbacks:
                try:
                    # --- ЗМІНЕНО: Передаємо весь об'єкт профілю ---
                    asyncio.create_task(callback(new_profile_data))
                except Exception:
                    pass

    def register_on_profile_change(self, callback: callable):
        """
        Реєструє функцію, яка буде викликана при кожній зміні профілю.
        """
        if callback not in self.on_profile_change_callbacks:
            self.on_profile_change_callbacks.append(callback)

    @property
    def current_language(self) -> str:
        """Повертає поточний код мови (напр., 'uk', 'en')."""
        return self._current_language

    @current_language.setter
    def current_language(self, new_lang_code: str):
        """
        Встановлює нову мову і сповіщає всіх підписників.
        """
        if self._current_language != new_lang_code:
            self._current_language = new_lang_code
            for callback in self.on_language_change_callbacks:
                try:
                    asyncio.create_task(callback(new_lang_code))
                except Exception:
                    pass

    def register_on_language_change(self, callback: callable):
        """
        Реєструє функцію, яка буде викликана при кожній зміні мови.
        """
        if callback not in self.on_language_change_callbacks:
            self.on_language_change_callbacks.append(callback)

    # --- ДОДАНО: API для сповіщення про зміну транзакцій ---
    def register_on_transactions_change(self, callback: callable):
        if callback not in self.on_transactions_change_callbacks:
            self.on_transactions_change_callbacks.append(callback)

    def notify_transactions_change(self):
        for callback in self.on_transactions_change_callbacks:
            try:
                asyncio.create_task(callback())
            except Exception:
                pass