"""
Система тем для додатку
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)

class ThemeType(Enum):
    """Тип теми"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    CUSTOM = "custom"

@dataclass
class ColorPalette:
    """Палітра кольорів"""
    primary: str
    secondary: str
    background: str
    surface: str
    error: str
    warning: str
    success: str
    info: str
    text_primary: str
    text_secondary: str
    text_disabled: str
    border: str
    divider: str
    shadow: str

@dataclass
class Typography:
    """Типографіка"""
    font_family: str
    font_size_small: int
    font_size_medium: int
    font_size_large: int
    font_size_xlarge: int
    font_weight_light: str
    font_weight_normal: str
    font_weight_bold: str
    line_height_small: float
    line_height_medium: float
    line_height_large: float

@dataclass
class Spacing:
    """Відступи"""
    xs: int
    sm: int
    md: int
    lg: int
    xl: int
    xxl: int

@dataclass
class BorderRadius:
    """Радіуси закруглення"""
    small: int
    medium: int
    large: int
    xlarge: int

@dataclass
class Theme:
    """Тема"""
    name: str
    type: ThemeType
    colors: ColorPalette
    typography: Typography
    spacing: Spacing
    border_radius: BorderRadius
    custom_properties: Dict[str, Any] = None

class ThemeManager:
    """Менеджер тем"""
    
    def __init__(self, themes_path: str = "themes"):
        self.themes_path = Path(themes_path)
        
        # Темы
        self._themes: Dict[str, Theme] = {}
        self._current_theme: Optional[Theme] = None
        self._default_theme: Optional[Theme] = None
        
        # Callbacks
        self._theme_change_callbacks: List[Callable[[Theme], None]] = []
        
        # Ініціалізуємо стандартні теми
        self._initialize_default_themes()
    
    def _initialize_default_themes(self):
        """Ініціалізує стандартні теми"""
        # Темна тема
        dark_theme = Theme(
            name="Dark",
            type=ThemeType.DARK,
            colors=ColorPalette(
                primary="#2196F3",
                secondary="#FFC107",
                background="#121212",
                surface="#1E1E1E",
                error="#F44336",
                warning="#FF9800",
                success="#4CAF50",
                info="#2196F3",
                text_primary="#FFFFFF",
                text_secondary="#B3B3B3",
                text_disabled="#666666",
                border="#333333",
                divider="#2A2A2A",
                shadow="#000000"
            ),
            typography=Typography(
                font_family="Segoe UI, system-ui, sans-serif",
                font_size_small=12,
                font_size_medium=14,
                font_size_large=16,
                font_size_xlarge=20,
                font_weight_light="300",
                font_weight_normal="400",
                font_weight_bold="600",
                line_height_small=1.2,
                line_height_medium=1.4,
                line_height_large=1.6
            ),
            spacing=Spacing(
                xs=4,
                sm=8,
                md=16,
                lg=24,
                xl=32,
                xxl=48
            ),
            border_radius=BorderRadius(
                small=4,
                medium=8,
                large=12,
                xlarge=16
            )
        )
        
        # Світла тема
        light_theme = Theme(
            name="Light",
            type=ThemeType.LIGHT,
            colors=ColorPalette(
                primary="#1976D2",
                secondary="#FFC107",
                background="#FFFFFF",
                surface="#F5F5F5",
                error="#D32F2F",
                warning="#F57C00",
                success="#388E3C",
                info="#1976D2",
                text_primary="#212121",
                text_secondary="#757575",
                text_disabled="#BDBDBD",
                border="#E0E0E0",
                divider="#F0F0F0",
                shadow="#000000"
            ),
            typography=Typography(
                font_family="Segoe UI, system-ui, sans-serif",
                font_size_small=12,
                font_size_medium=14,
                font_size_large=16,
                font_size_xlarge=20,
                font_weight_light="300",
                font_weight_normal="400",
                font_weight_bold="600",
                line_height_small=1.2,
                line_height_medium=1.4,
                line_height_large=1.6
            ),
            spacing=Spacing(
                xs=4,
                sm=8,
                md=16,
                lg=24,
                xl=32,
                xxl=48
            ),
            border_radius=BorderRadius(
                small=4,
                medium=8,
                large=12,
                xlarge=16
            )
        )
        
        # Синя тема
        blue_theme = Theme(
            name="Blue",
            type=ThemeType.CUSTOM,
            colors=ColorPalette(
                primary="#1976D2",
                secondary="#FFC107",
                background="#0D47A1",
                surface="#1565C0",
                error="#D32F2F",
                warning="#F57C00",
                success="#388E3C",
                info="#1976D2",
                text_primary="#FFFFFF",
                text_secondary="#B3E5FC",
                text_disabled="#81D4FA",
                border="#1976D2",
                divider="#1565C0",
                shadow="#000000"
            ),
            typography=Typography(
                font_family="Segoe UI, system-ui, sans-serif",
                font_size_small=12,
                font_size_medium=14,
                font_size_large=16,
                font_size_xlarge=20,
                font_weight_light="300",
                font_weight_normal="400",
                font_weight_bold="600",
                line_height_small=1.2,
                line_height_medium=1.4,
                line_height_large=1.6
            ),
            spacing=Spacing(
                xs=4,
                sm=8,
                md=16,
                lg=24,
                xl=32,
                xxl=48
            ),
            border_radius=BorderRadius(
                small=4,
                medium=8,
                large=12,
                xlarge=16
            )
        )
        
        # Зелена тема
        green_theme = Theme(
            name="Green",
            type=ThemeType.CUSTOM,
            colors=ColorPalette(
                primary="#388E3C",
                secondary="#FFC107",
                background="#1B5E20",
                surface="#2E7D32",
                error="#D32F2F",
                warning="#F57C00",
                success="#4CAF50",
                info="#2196F3",
                text_primary="#FFFFFF",
                text_secondary="#C8E6C9",
                text_disabled="#A5D6A7",
                border="#388E3C",
                divider="#2E7D32",
                shadow="#000000"
            ),
            typography=Typography(
                font_family="Segoe UI, system-ui, sans-serif",
                font_size_small=12,
                font_size_medium=14,
                font_size_large=16,
                font_size_xlarge=20,
                font_weight_light="300",
                font_weight_normal="400",
                font_weight_bold="600",
                line_height_small=1.2,
                line_height_medium=1.4,
                line_height_large=1.6
            ),
            spacing=Spacing(
                xs=4,
                sm=8,
                md=16,
                lg=24,
                xl=32,
                xxl=48
            ),
            border_radius=BorderRadius(
                small=4,
                medium=8,
                large=12,
                xlarge=16
            )
        )
        
        # Додаємо теми
        self._themes["dark"] = dark_theme
        self._themes["light"] = light_theme
        self._themes["blue"] = blue_theme
        self._themes["green"] = green_theme
        
        # Встановлюємо темну тему за замовчуванням
        self._default_theme = dark_theme
        self._current_theme = dark_theme
    
    def get_theme(self, name: str) -> Optional[Theme]:
        """Отримує тему за назвою"""
        return self._themes.get(name)
    
    def get_current_theme(self) -> Optional[Theme]:
        """Отримує поточну тему"""
        return self._current_theme
    
    def set_theme(self, name: str) -> bool:
        """Встановлює тему"""
        theme = self._themes.get(name)
        if theme:
            self._current_theme = theme
            self._notify_theme_change()
            return True
        return False
    
    def get_available_themes(self) -> List[str]:
        """Повертає список доступних тем"""
        return list(self._themes.keys())
    
    def create_custom_theme(
        self,
        name: str,
        base_theme: str = "dark",
        color_overrides: Optional[Dict[str, str]] = None,
        typography_overrides: Optional[Dict[str, Any]] = None,
        spacing_overrides: Optional[Dict[str, int]] = None,
        border_radius_overrides: Optional[Dict[str, int]] = None
    ) -> bool:
        """Створює кастомну тему"""
        base = self._themes.get(base_theme)
        if not base:
            return False
        
        # Копіюємо базову тему
        new_theme = Theme(
            name=name,
            type=ThemeType.CUSTOM,
            colors=ColorPalette(**asdict(base.colors)),
            typography=Typography(**asdict(base.typography)),
            spacing=Spacing(**asdict(base.spacing)),
            border_radius=BorderRadius(**asdict(base.border_radius))
        )
        
        # Застосовуємо перевизначення
        if color_overrides:
            for key, value in color_overrides.items():
                if hasattr(new_theme.colors, key):
                    setattr(new_theme.colors, key, value)
        
        if typography_overrides:
            for key, value in typography_overrides.items():
                if hasattr(new_theme.typography, key):
                    setattr(new_theme.typography, key, value)
        
        if spacing_overrides:
            for key, value in spacing_overrides.items():
                if hasattr(new_theme.spacing, key):
                    setattr(new_theme.spacing, key, value)
        
        if border_radius_overrides:
            for key, value in border_radius_overrides.items():
                if hasattr(new_theme.border_radius, key):
                    setattr(new_theme.border_radius, key, value)
        
        # Додаємо тему
        self._themes[name] = new_theme
        return True
    
    async def save_theme(self, name: str) -> bool:
        """Зберігає тему на диск"""
        theme = self._themes.get(name)
        if not theme:
            return False
        
        try:
            theme_file = self.themes_path / f"{name}.json"
            async with aiofiles.open(theme_file, 'w') as f:
                await f.write(json.dumps(asdict(theme), indent=2))
            return True
        except Exception as e:
            logger.error(f"Error saving theme {name}: {e}")
            return False
    
    async def load_theme(self, name: str) -> bool:
        """Завантажує тему з диска"""
        try:
            theme_file = self.themes_path / f"{name}.json"
            if not theme_file.exists():
                return False
            
            async with aiofiles.open(theme_file, 'r') as f:
                theme_data = json.loads(await f.read())
            
            # Відновлюємо об'єкти
            theme = Theme(
                name=theme_data['name'],
                type=ThemeType(theme_data['type']),
                colors=ColorPalette(**theme_data['colors']),
                typography=Typography(**theme_data['typography']),
                spacing=Spacing(**theme_data['spacing']),
                border_radius=BorderRadius(**theme_data['border_radius']),
                custom_properties=theme_data.get('custom_properties', {})
            )
            
            self._themes[name] = theme
            return True
        except Exception as e:
            logger.error(f"Error loading theme {name}: {e}")
            return False
    
    async def load_all_themes(self):
        """Завантажує всі теми з диска"""
        for theme_file in self.themes_path.glob("*.json"):
            theme_name = theme_file.stem
            if theme_name not in self._themes:
                await self.load_theme(theme_name)
    
    def delete_theme(self, name: str) -> bool:
        """Видаляє тему"""
        if name in ["dark", "light"]:  # Не можна видаляти системні теми
            return False
        
        if name in self._themes:
            del self._themes[name]
            
            # Видаляємо файл
            theme_file = self.themes_path / f"{name}.json"
            if theme_file.exists():
                theme_file.unlink()
            
            return True
        return False
    
    def on_theme_change(self, callback: Callable[[Theme], None]):
        """Підписується на зміну теми"""
        self._theme_change_callbacks.append(callback)
    
    def _notify_theme_change(self):
        """Сповіщає про зміну теми"""
        for callback in self._theme_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(self._current_theme))
                else:
                    callback(self._current_theme)
            except Exception as e:
                logger.error(f"Error in theme change callback: {e}")
    
    def get_color(self, color_name: str) -> Optional[str]:
        """Отримує колір з поточної теми"""
        if not self._current_theme:
            return None
        
        if hasattr(self._current_theme.colors, color_name):
            return getattr(self._current_theme.colors, color_name)
        
        return None
    
    def get_spacing(self, size: str) -> Optional[int]:
        """Отримує відступ з поточної теми"""
        if not self._current_theme:
            return None
        
        if hasattr(self._current_theme.spacing, size):
            return getattr(self._current_theme.spacing, size)
        
        return None
    
    def get_border_radius(self, size: str) -> Optional[int]:
        """Отримує радіус закруглення з поточної теми"""
        if not self._current_theme:
            return None
        
        if hasattr(self._current_theme.border_radius, size):
            return getattr(self._current_theme.border_radius, size)
        
        return None
    
    def get_typography(self, property_name: str) -> Optional[Any]:
        """Отримує властивість типографіки з поточної теми"""
        if not self._current_theme:
            return None
        
        if hasattr(self._current_theme.typography, property_name):
            return getattr(self._current_theme.typography, property_name)
        
        return None

# Утилітарні функції
def apply_theme_to_control(control: Any, theme: Theme):
    """Застосовує тему до контрола"""
    if not theme:
        return
    
    # Застосовуємо кольори
    if hasattr(control, 'bgcolor') and not control.bgcolor:
        control.bgcolor = theme.colors.background
    
    if hasattr(control, 'color') and not control.color:
        control.color = theme.colors.text_primary
    
    if hasattr(control, 'border') and not control.border:
        control.border = f"1px solid {theme.colors.border}"
    
    # Застосовуємо відступи
    if hasattr(control, 'padding') and not control.padding:
        control.padding = theme.spacing.md
    
    if hasattr(control, 'margin') and not control.margin:
        control.margin = theme.spacing.sm
    
    # Застосовуємо радіуси закруглення
    if hasattr(control, 'border_radius') and not control.border_radius:
        control.border_radius = theme.border_radius.medium

def create_themed_container(theme: Theme, **kwargs) -> Any:
    """Створює контейнер з застосованою темою"""
    # Тут має бути створення ft.Container з застосованою темою
    # Це залежить від конкретного UI фреймворку
    pass

# Глобальний екземпляр
_theme_manager: Optional[ThemeManager] = None

def get_theme_manager() -> ThemeManager:
    """Отримує глобальний менеджер тем"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager

def get_current_theme() -> Optional[Theme]:
    """Отримує поточну тему"""
    return get_theme_manager().get_current_theme()

def set_theme(name: str) -> bool:
    """Встановлює тему"""
    return get_theme_manager().set_theme(name)

def get_color(color_name: str) -> Optional[str]:
    """Отримує колір з поточної теми"""
    return get_theme_manager().get_color(color_name)

def get_spacing(size: str) -> Optional[int]:
    """Отримує відступ з поточної теми"""
    return get_theme_manager().get_spacing(size)

def get_border_radius(size: str) -> Optional[int]:
    """Отримує радіус закруглення з поточної теми"""
    return get_theme_manager().get_border_radius(size)
