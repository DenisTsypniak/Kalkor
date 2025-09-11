# --- START OF FILE src/views/profiles/profiles_view.py ---

import flet as ft
from src.app.app_state import AppState
from src.data import data_manager as dm
from typing import Callable
import random
import base64
from src.utils.localization import LocalizationManager
from src.utils.config import TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_EXPENSE, INITIAL_BALANCE_CATEGORY
from src.views.base_view import BaseContainerView

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




class ProfilesView(BaseContainerView):
    # --- ЗМІНЕНО: Конструктор приймає об'єкт App ---
    def __init__(self, page: ft.Page, app_state: AppState, navigate_func: Callable, loc: LocalizationManager,
                 on_profile_selected: Callable, app):
        super().__init__(
            app_state, loc,
            visible=False, expand=True, 
            alignment=ft.alignment.center,
            padding=ft.padding.all(0))

        self.page = page
        self.app = app  # --- ДОДАНО: Зберігаємо посилання на головний клас App
        self.navigate_func = navigate_func
        self.on_profile_selected = on_profile_selected

        self.new_avatar_b64 = None
        self.profile_to_edit = None
        self.profile_to_delete = None
        
        # Ініціалізуємо нові системи
        self.validator = DataValidator()

        self.file_picker = ft.FilePicker(on_result=self.on_file_picker_result)
        self.app_state.register_on_language_change(self._on_lang_change)
        self.profiles_grid = ft.Row(
            wrap=True, 
            spacing=20, 
            run_spacing=20, 
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True
        )

        self._create_dialogs()
        self._build_ui()
        
        # Додаємо кнопку систем оптимізації
        # Тестовий виклик прибраний

        if self.page:
            self.page.overlay.extend([
                self.file_picker,
                self.create_profile_dialog,
                self.edit_dialog,
                self.confirm_delete_dialog
            ])

    async def _on_lang_change(self, lang_code: str):
        # Викликаємо базовий метод
        await super()._on_lang_change(lang_code)
        
        # Легка локалізація без повного перерендеру, щоб уникнути мерехтіння
        try:
            if self.content and hasattr(self.content, 'controls') and len(self.content.controls) > 0:
                if hasattr(self.content.controls[0], 'content') and hasattr(self.content.controls[0].content, 'controls'):
                    # Знаходимо Text елемент з заголовком
                    for control in self.content.controls[0].content.controls:
                        if isinstance(control, ft.Text):
                            control.value = self.loc.get("profiles_title")
                            break
        except Exception:
            pass
        self._update_dialog_localization()
        # Не викликаємо render_profiles(); лише оновлюємо існуюче
        if self.page:
            self.page.update()
    
    def _close_all_dialogs(self):
        """Закриває всі діалоги при втраті фокусу"""
        try:
            # Закриваємо всі діалоги профілів
            dialog_attributes = [
                'create_profile_dialog', 'edit_dialog', 'confirm_delete_dialog'
            ]
            
            for attr_name in dialog_attributes:
                if hasattr(self, attr_name):
                    dialog = getattr(self, attr_name)
                    if dialog and hasattr(dialog, 'open'):
                        dialog.open = False
            
            # Викликаємо базовий метод для закриття загальних діалогів
            super()._close_all_dialogs()
        except Exception as e:
            print(f"Error closing profile dialogs: {e}")
    
    def _restore_focus(self):
        """Відновлює фокус на текстові поля після повернення до додатку"""
        try:
            # Відновлюємо фокус на активному текстовому полі
            if hasattr(self, 'name_input') and self.name_input:
                self.name_input.focus()
            else:
                # Fallback до базового методу
                if self.page:
                    self.page.update()
        except Exception as e:
            print(f"Error restoring focus in profiles view: {e}")

    def _build_ui(self):
        profiles_title = self.loc.get("profiles_title")
        # Створюємо основний контент з ідеальним центруванням
        main_content = ft.Column(
            controls=[
                ft.Container(expand=True),  # Верхній відступ
                ft.Text(profiles_title or "Профілі", size=32, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.profiles_grid,
                    alignment=ft.alignment.center,
                    expand=True
                ),
                ft.Container(expand=True),  # Нижній відступ
                # Кнопки дій
                # Тестові кнопки прибрані
                ft.Container(expand=True)   # Додатковий нижній відступ
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=30,
            expand=True
        )

        # Обгортаємо все в Stack
        self.content = ft.Stack([
            ft.Container(
                content=main_content,
                alignment=ft.alignment.center,
                expand=True
            )  # Основний контент
        ])

    async def on_view_show(self):
        try:
            # Викликаємо базовий метод
            await super().on_view_show()
            
            # Перевіряємо чи всі необхідні атрибути існують
            if not hasattr(self, 'file_picker') or not hasattr(self, 'create_profile_dialog') or not hasattr(self, 'edit_dialog') or not hasattr(self, 'confirm_delete_dialog'):
                logger.warning("Missing required attributes in ProfilesView")
                return
                
            if self.page:
                if self.file_picker not in self.page.overlay: 
                    self.page.overlay.append(self.file_picker)
                if self.create_profile_dialog not in self.page.overlay: 
                    self.page.overlay.append(self.create_profile_dialog)
                if self.edit_dialog not in self.page.overlay: 
                    self.page.overlay.append(self.edit_dialog)
                if self.confirm_delete_dialog not in self.page.overlay: 
                    self.page.overlay.append(self.confirm_delete_dialog)
            
            await self.render_profiles()
        except Exception as e:
            print(f"Error in on_view_show: {e}")
            import traceback
            traceback.print_exc()

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

    def _create_avatar_stack(self, on_pick_callback: Callable, image_preview_control: ft.Image) -> ft.Stack:
        upload_button = ft.IconButton(
            icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
            tooltip=self.loc.get("profiles_upload_avatar_tooltip", default="Завантажити зображення"),
            on_click=on_pick_callback
        )
        return ft.Stack([upload_button, image_preview_control], width=80, height=80)

    def _create_dialogs(self):
        self.avatar_preview_create = ft.Image(visible=False, fit=ft.ImageFit.COVER, expand=True, border_radius=40)
        self.avatar_stack_create = self._create_avatar_stack(
            lambda _: self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg", "jpeg"]),
            self.avatar_preview_create
        )
        self.new_profile_input = ft.TextField(label=self.loc.get("profiles_create_dialog_name_label"), autofocus=True)
        self.initial_balance_input = ft.TextField(
            label=self.loc.get("profiles_create_dialog_balance_label"),
            value="0",
                            input_filter=ft.NumbersOnlyInputFilter(),
            on_change=self.on_balance_change_validate
        )
        self.create_profile_dialog = ft.AlertDialog(
            modal=True, title=ft.Text(self.loc.get("profiles_create_dialog_title")),
            content=ft.Column([self.avatar_stack_create, self.new_profile_input, self.initial_balance_input],
                              tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            actions=[
                ft.TextButton(self.loc.get("profiles_create_dialog_cancel_button"), on_click=self.close_create_dialog),
                ft.ElevatedButton(self.loc.get("profiles_create_dialog_create_button"),
                                  on_click=self.create_profile_action,
                                  bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)],
            actions_alignment=ft.MainAxisAlignment.END, on_dismiss=self.close_create_dialog)

        self.avatar_preview_edit = ft.Image(visible=False, fit=ft.ImageFit.COVER, expand=True, border_radius=40)
        self.avatar_stack_edit = self._create_avatar_stack(
            lambda _: self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg", "jpeg"]),
            self.avatar_preview_edit
        )
        self.edit_profile_input = ft.TextField(label=self.loc.get("profiles_edit_dialog_new_name_label"),
                                               autofocus=True)
        self.edit_dialog = ft.AlertDialog(
            modal=True, title=ft.Text(self.loc.get("profiles_edit_dialog_title")),
            content=ft.Column([self.avatar_stack_edit, self.edit_profile_input],
                              tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            actions=[
                ft.TextButton(self.loc.get("profiles_create_dialog_cancel_button"), on_click=self.close_edit_dialog),
                ft.ElevatedButton(self.loc.get("profiles_edit_dialog_save_button"), on_click=self.save_edited_profile,
                                  bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)],
            actions_alignment=ft.MainAxisAlignment.END, on_dismiss=self.close_edit_dialog)

        self.confirm_delete_dialog = ft.AlertDialog(
            modal=True, title=ft.Text(self.loc.get("profiles_confirm_delete_title")), content=ft.Text(""),
            actions=[ft.TextButton(self.loc.get("profiles_confirm_delete_no_button"),
                                   on_click=self.close_confirm_delete_dialog),
                     ft.ElevatedButton(self.loc.get("profiles_confirm_delete_yes_button"),
                                       on_click=self.confirm_delete_action,
                                       color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_700)],
            on_dismiss=self.close_confirm_delete_dialog)

    def _update_dialog_localization(self):
        self.create_profile_dialog.title.value = self.loc.get("profiles_create_dialog_title")
        self.new_profile_input.label = self.loc.get("profiles_create_dialog_name_label")
        self.initial_balance_input.label = self.loc.get("profiles_create_dialog_balance_label")
        self.create_profile_dialog.actions[0].text = self.loc.get("profiles_create_dialog_cancel_button")
        self.create_profile_dialog.actions[1].text = self.loc.get("profiles_create_dialog_create_button")

        self.edit_dialog.title.value = self.loc.get("profiles_edit_dialog_title")
        self.edit_profile_input.label = self.loc.get("profiles_edit_dialog_new_name_label")
        self.edit_dialog.actions[0].text = self.loc.get("profiles_create_dialog_cancel_button")
        self.edit_dialog.actions[1].text = self.loc.get("profiles_edit_dialog_save_button")

        self.confirm_delete_dialog.title.value = self.loc.get("profiles_confirm_delete_title")
        self.confirm_delete_dialog.actions[0].text = self.loc.get("profiles_confirm_delete_no_button")
        self.confirm_delete_dialog.actions[1].text = self.loc.get("profiles_confirm_delete_yes_button")

    async def render_profiles(self):
        try:
            self.profiles_grid.controls.clear()
            # --- ЗМІНЕНО: Використання кешу з перевіркою ---
            if hasattr(self, 'app') and hasattr(self.app, 'profile_list_cache'):
                profiles = self.app.profile_list_cache
            else:
                # Fallback до прямої завантаження з БД
                profiles = await dm.get_profile_list()
            
            for profile_data in profiles:
                self.profiles_grid.controls.append(self.create_profile_avatar(profile_data))
            self.profiles_grid.controls.append(self.create_profile_avatar(is_add_button=True))
            if self.page:
                self.page.update()
        except Exception as e:
            print(f"Error in render_profiles: {e}")
            # Fallback - показуємо тільки кнопку додавання
            self.profiles_grid.controls.clear()
            self.profiles_grid.controls.append(self.create_profile_avatar(is_add_button=True))
            if self.page:
                self.page.update()

    def create_profile_avatar(self, profile_data: dict = None, is_add_button: bool = False):
        if is_add_button:
            name = self.loc.get("profiles_add")
            avatar_content = ft.Icon(ft.Icons.ADD, size=80, color=ft.Colors.WHITE)
            bg_color = ft.Colors.WHITE24
        else:
            name = profile_data['name']
            if profile_data.get('avatar_b64'):
                # Використовуємо lazy image loader якщо доступний
                if LAZY_LOADER_ENABLED:
                    try:
                        image_loader = get_image_loader()
                        avatar_content = image_loader.load_image_from_base64(
                            profile_data['avatar_b64'].split(',')[1], 
                            width=140, 
                            height=140
                        )
                    except Exception:
                        # Fallback до звичайного Image
                        avatar_content = ft.Image(src_base64=profile_data['avatar_b64'].split(',')[1], width=140, height=140,
                                                  fit=ft.ImageFit.COVER, border_radius=70)
                else:
                    avatar_content = ft.Image(src_base64=profile_data['avatar_b64'].split(',')[1], width=140, height=140,
                                              fit=ft.ImageFit.COVER, border_radius=70)
                bg_color = ft.Colors.TRANSPARENT
            else:
                avatar_content = ft.Icon(ft.Icons.PERSON_OUTLINE, size=80, color=ft.Colors.WHITE)
                color_seed = sum(ord(c) for c in name)
                rand = random.Random(color_seed)
                bg_color = rand.choice([ft.Colors.BLUE_ACCENT_100, ft.Colors.GREEN_ACCENT_100, ft.Colors.RED_ACCENT_100,
                                        ft.Colors.PURPLE_ACCENT_100, ft.Colors.ORANGE_ACCENT_100,
                                        ft.Colors.TEAL_ACCENT_100])

            edit_icon = ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.AMBER,
                                      tooltip=self.loc.get("profiles_edit_tooltip"),
                                      on_click=lambda e, p=profile_data: self.page.run_task(self.open_edit_dialog, p),
                                      visible=False)
            delete_icon = ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400,
                                        tooltip=self.loc.get("profiles_delete_tooltip"),
                                        on_click=lambda e, p=profile_data: self.page.run_task(
                                            self.open_confirm_delete_dialog, p),
                                        visible=False)
        action_icons = []
        if not is_add_button:
            action_icons = [ft.Container(content=edit_icon, top=5, right=5),
                            ft.Container(content=delete_icon, bottom=5, right=5)]

        avatar_circle = ft.Container(
            width=140, height=140,
            content=ft.Stack(
                [ft.Container(content=avatar_content, alignment=ft.alignment.center, expand=True), *action_icons]),
            alignment=ft.alignment.center, shape=ft.BoxShape.CIRCLE, bgcolor=bg_color,
            animate_scale=ft.Animation(duration=200, curve=ft.AnimationCurve.EASE_OUT),
            on_hover=self.on_avatar_hover, data=profile_data)

        detector = ft.GestureDetector(content=avatar_circle)
        if is_add_button:
            detector.on_tap = self.open_create_profile_dialog
        else:
            # --- ЗМІНЕНО: Передаємо весь об'єкт profile_data ---
            detector.on_tap = lambda e, p_data=profile_data: self.page.run_task(self.on_profile_selected, e, p_data)

        return ft.Column([detector, ft.Text(name, size=16, weight=ft.FontWeight.W_500)],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def on_avatar_hover(self, e: ft.HoverEvent):
        is_hovering = e.data == "true"
        if e.control.data:
            avatar_stack = e.control.content
            for control in avatar_stack.controls:
                if hasattr(control, 'content') and isinstance(control.content, ft.IconButton):
                    control.content.visible = is_hovering
        e.control.scale = 1.1 if is_hovering else 1.0
        e.control.update()

    async def open_create_profile_dialog(self, e):
        self._update_dialog_localization()
        self.new_avatar_b64 = None
        self.avatar_preview_create.visible = False
        self.avatar_preview_create.src_base64 = None
        self.new_profile_input.value, self.initial_balance_input.value = "", "0"
        self.new_profile_input.error_text = ""
        self.page.dialog = self.create_profile_dialog
        self.create_profile_dialog.open = True
        self.page.update()

    async def close_create_dialog(self, e):
        self.create_profile_dialog.open = False
        self.page.update()

    async def create_profile_action(self, e):
        profile_name = self.new_profile_input.value.strip()
        profiles = await dm.get_profile_list()
        if not profile_name or profile_name in [p['name'] for p in profiles]:
            self.new_profile_input.error_text = self.loc.get("error_name_duplicate")
            self.create_profile_dialog.update()
            return

        new_profile_obj = await dm.create_profile(profile_name, self.new_avatar_b64)
        balance = float(self.initial_balance_input.value or "0")
        if balance != 0:
            trans_type = TRANSACTION_TYPE_INCOME if balance > 0 else TRANSACTION_TYPE_EXPENSE
            await dm.add_transaction(new_profile_obj['id'], trans_type, INITIAL_BALANCE_CATEGORY,
                                     self.loc.get("special_category_initial_balance"), abs(balance))

        await self.close_create_dialog(e)
        # --- ЗМІНЕНО: Оновлюємо кеш та встановлюємо новий профіль ---
        await self.app.refresh_profile_cache()
        self.app_state.current_profile = new_profile_obj
        await self.navigate_func(e=None)

    async def on_balance_change_validate(self, e: ft.ControlEvent):
        control = e.control
        original_value = control.value
        if original_value == "" or original_value == "-": return
        try:
            float(original_value)
        except ValueError:
            control.value = original_value[:-1]
            control.update()

    async def on_file_picker_result(self, e: ft.FilePickerResultEvent):
        if e.files:
            with open(e.files[0].path, "rb") as f:
                file_data = f.read()
            b64_string = base64.b64encode(file_data).decode('utf-8')
            self.new_avatar_b64 = f"data:image/png;base64,{b64_string}"

            if self.create_profile_dialog.open:
                self.avatar_preview_create.src_base64 = b64_string
                self.avatar_preview_create.visible = True
                self.create_profile_dialog.update()
            elif self.edit_dialog.open:
                self.avatar_preview_edit.src_base64 = b64_string
                self.avatar_preview_edit.visible = True
                self.edit_dialog.update()

    async def open_edit_dialog(self, profile_data: dict):
        self._update_dialog_localization()
        self.new_avatar_b64 = None
        self.profile_to_edit = profile_data
        self.edit_profile_input.value = profile_data['name']
        if profile_data.get('avatar_b64'):
            self.avatar_preview_edit.src_base64 = profile_data['avatar_b64'].split(',')[1]
            self.avatar_preview_edit.visible = True
        else:
            self.avatar_preview_edit.visible = False
            self.avatar_preview_edit.src_base64 = None
        self.edit_profile_input.error_text = ""
        self.page.dialog = self.edit_dialog
        self.edit_dialog.open = True
        self.page.update()

    async def close_edit_dialog(self, e):
        self.edit_dialog.open = False
        self.page.update()

    async def save_edited_profile(self, e):
        new_name = self.edit_profile_input.value.strip()
        if not new_name:
            self.edit_profile_input.error_text = self.loc.get("error_name_empty")
            self.edit_dialog.update()
            return

        profile_id_to_update = self.profile_to_edit['id']
        old_profile_data = self.app_state.current_profile

        await dm.update_profile(profile_id_to_update, new_name, self.new_avatar_b64)
        await self.app.refresh_profile_cache()

        # --- ЗМІНЕНО: Оновлюємо поточний профіль, якщо його редагували ---
        if old_profile_data and old_profile_data['id'] == profile_id_to_update:
            # Знаходимо оновлені дані в кеші
            updated_profile_data = next((p for p in self.app.profile_list_cache if p['id'] == profile_id_to_update),
                                        None)
            if updated_profile_data:
                self.app_state.current_profile = updated_profile_data

        await self.close_edit_dialog(e)
        await self.render_profiles()

    async def open_confirm_delete_dialog(self, profile_data: dict):
        self._update_dialog_localization()
        self.profile_to_delete = profile_data
        self.confirm_delete_dialog.content.value = self.loc.get("profiles_confirm_delete_content",
                                                                profile_name=profile_data['name'])
        self.page.dialog = self.confirm_delete_dialog
        self.confirm_delete_dialog.open = True
        self.page.update()

    async def close_confirm_delete_dialog(self, e):
        self.confirm_delete_dialog.open = False
        self.page.update()

    async def confirm_delete_action(self, e):
        if self.profile_to_delete:
            profile_id_to_delete = self.profile_to_delete['id']
            current_profile_data = self.app_state.current_profile

            # --- ЗМІНЕНО: Порівняння по ID ---
            if current_profile_data and current_profile_data['id'] == profile_id_to_delete:
                self.app_state.current_profile = None
                await self.navigate_func(e=None, view_name="profiles")

            await dm.delete_profile(profile_id_to_delete)
            await self.app.refresh_profile_cache()

            self.profile_to_delete = None
            await self.close_confirm_delete_dialog(e)
            await self.render_profiles()
    
    # Тестові методи прибрані