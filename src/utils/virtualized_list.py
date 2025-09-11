"""
Віртуалізація списків для оптимізації продуктивності
"""

import asyncio
import logging
from typing import List, Any, Callable, Optional, Dict, Tuple, Generic, TypeVar
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class VirtualizationConfig:
    """Конфігурація віртуалізації"""
    item_height: int = 100
    container_height: int = 600
    buffer_size: int = 5  # Кількість елементів для буферизації
    scroll_threshold: float = 0.1  # Поріг для завантаження нових елементів

@dataclass
class VirtualItem:
    """Віртуальний елемент"""
    index: int
    data: Any
    height: int
    visible: bool = True
    rendered: bool = False

class VirtualizedList(Generic[T]):
    """Віртуалізований список"""
    
    def __init__(
        self,
        config: VirtualizationConfig,
        item_renderer: Callable[[T, int], Any],
        data_loader: Optional[Callable[[int, int], List[T]]] = None
    ):
        self.config = config
        self.item_renderer = item_renderer
        self.data_loader = data_loader
        
        # Дані
        self._items: List[VirtualItem] = []
        self._total_count: int = 0
        self._loaded_count: int = 0
        
        # Стан прокрутки
        self._scroll_offset: float = 0
        self._visible_start: int = 0
        self._visible_end: int = 0
        
        # UI елементи
        self._container: Optional[Any] = None
        self._scrollable_area: Optional[Any] = None
        self._item_containers: Dict[int, Any] = {}
        
        # Callbacks
        self._on_scroll_callbacks: List[Callable] = []
        self._on_data_load_callbacks: List[Callable] = []
        
        # Стан завантаження
        self._is_loading: bool = False
        self._has_more_data: bool = True
    
    def set_total_count(self, count: int):
        """Встановлює загальну кількість елементів"""
        self._total_count = count
        self._update_visible_range()
    
    def set_data(self, data: List[T]):
        """Встановлює дані"""
        self._items = [
            VirtualItem(index=i, data=item, height=self.config.item_height)
            for i, item in enumerate(data)
        ]
        self._total_count = len(data)
        self._loaded_count = len(data)
        self._update_visible_range()
        self._render_visible_items()
    
    def append_data(self, data: List[T]):
        """Додає дані в кінець"""
        start_index = len(self._items)
        new_items = [
            VirtualItem(index=i + start_index, data=item, height=self.config.item_height)
            for i, item in enumerate(data)
        ]
        self._items.extend(new_items)
        self._total_count = len(self._items)
        self._loaded_count = len(self._items)
        self._update_visible_range()
        self._render_visible_items()
    
    def insert_data(self, index: int, data: List[T]):
        """Вставляє дані на позицію"""
        # Оновлюємо індекси існуючих елементів
        for item in self._items[index:]:
            item.index += len(data)
        
        # Вставляємо нові елементи
        new_items = [
            VirtualItem(index=i + index, data=item, height=self.config.item_height)
            for i, item in enumerate(data)
        ]
        self._items[index:index] = new_items
        self._total_count = len(self._items)
        self._loaded_count = len(self._items)
        self._update_visible_range()
        self._render_visible_items()
    
    def remove_item(self, index: int):
        """Видаляє елемент"""
        if 0 <= index < len(self._items):
            del self._items[index]
            # Оновлюємо індекси
            for i, item in enumerate(self._items[index:], index):
                item.index = i
            self._total_count = len(self._items)
            self._loaded_count = len(self._items)
            self._update_visible_range()
            self._render_visible_items()
    
    def update_item(self, index: int, data: T):
        """Оновлює елемент"""
        if 0 <= index < len(self._items):
            self._items[index].data = data
            self._render_item(index)
    
    def scroll_to(self, offset: float):
        """Прокручує до позиції"""
        self._scroll_offset = max(0, min(offset, self._get_max_scroll_offset()))
        self._update_visible_range()
        self._render_visible_items()
        self._notify_scroll_callbacks()
    
    def scroll_to_item(self, index: int):
        """Прокручує до елемента"""
        if 0 <= index < len(self._items):
            offset = index * self.config.item_height
            self.scroll_to(offset)
    
    def _update_visible_range(self):
        """Оновлює діапазон видимих елементів"""
        if not self._items:
            self._visible_start = 0
            self._visible_end = 0
            return
        
        # Розраховуємо видимий діапазон
        start_index = int(self._scroll_offset // self.config.item_height)
        end_index = int((self._scroll_offset + self.config.container_height) // self.config.item_height)
        
        # Додаємо буфер
        buffer_start = max(0, start_index - self.config.buffer_size)
        buffer_end = min(len(self._items), end_index + self.config.buffer_size)
        
        self._visible_start = buffer_start
        self._visible_end = buffer_end
        
        # Перевіряємо чи потрібно завантажити більше даних
        if self.data_loader and self._has_more_data and not self._is_loading:
            if end_index >= self._loaded_count - self.config.buffer_size:
                asyncio.create_task(self._load_more_data())
    
    def _render_visible_items(self):
        """Рендерить видимі елементи"""
        if not self._container:
            return
        
        # Очищаємо контейнер
        if hasattr(self._container, 'controls'):
            self._container.controls.clear()
        
        # Рендеримо видимі елементи
        for i in range(self._visible_start, self._visible_end):
            if i < len(self._items):
                item = self._items[i]
                rendered_item = self._render_item(i)
                if rendered_item and hasattr(self._container, 'controls'):
                    self._container.controls.append(rendered_item)
    
    def _render_item(self, index: int) -> Optional[Any]:
        """Рендерить один елемент"""
        if index >= len(self._items):
            return None
        
        item = self._items[index]
        
        try:
            rendered_item = self.item_renderer(item.data, index)
            item.rendered = True
            self._item_containers[index] = rendered_item
            return rendered_item
        except Exception as e:
            logger.error(f"Error rendering item {index}: {e}")
            return None
    
    async def _load_more_data(self):
        """Завантажує більше даних"""
        if not self.data_loader or self._is_loading or not self._has_more_data:
            return
        
        self._is_loading = True
        
        try:
            # Завантажуємо дані
            new_data = await self.data_loader(self._loaded_count, 50)  # Завантажуємо по 50 елементів
            
            if new_data:
                self.append_data(new_data)
                self._notify_data_load_callbacks()
            else:
                self._has_more_data = False
                
        except Exception as e:
            logger.error(f"Error loading more data: {e}")
        finally:
            self._is_loading = False
    
    def _get_max_scroll_offset(self) -> float:
        """Повертає максимальний offset для прокрутки"""
        if not self._items:
            return 0
        
        total_height = len(self._items) * self.config.item_height
        return max(0, total_height - self.config.container_height)
    
    def _notify_scroll_callbacks(self):
        """Сповіщає про зміну прокрутки"""
        for callback in self._on_scroll_callbacks:
            try:
                callback(self._scroll_offset, self._visible_start, self._visible_end)
            except Exception as e:
                logger.error(f"Error in scroll callback: {e}")
    
    def _notify_data_load_callbacks(self):
        """Сповіщає про завантаження даних"""
        for callback in self._on_data_load_callbacks:
            try:
                callback(self._loaded_count, self._total_count)
            except Exception as e:
                logger.error(f"Error in data load callback: {e}")
    
    def on_scroll(self, callback: Callable):
        """Підписується на зміни прокрутки"""
        self._on_scroll_callbacks.append(callback)
    
    def on_data_load(self, callback: Callable):
        """Підписується на завантаження даних"""
        self._on_data_load_callbacks.append(callback)
    
    def get_visible_items(self) -> List[T]:
        """Повертає видимі елементи"""
        return [
            item.data for item in self._items[self._visible_start:self._visible_end]
            if item.visible
        ]
    
    def get_item_at_position(self, y: float) -> Optional[T]:
        """Повертає елемент за позицією Y"""
        index = int((self._scroll_offset + y) // self.config.item_height)
        if 0 <= index < len(self._items):
            return self._items[index].data
        return None
    
    def get_scroll_info(self) -> Dict[str, Any]:
        """Повертає інформацію про прокрутку"""
        return {
            'scroll_offset': self._scroll_offset,
            'visible_start': self._visible_start,
            'visible_end': self._visible_end,
            'total_items': self._total_count,
            'loaded_items': self._loaded_count,
            'is_loading': self._is_loading,
            'has_more_data': self._has_more_data
        }

class VirtualizedGrid:
    """Віртуалізована сітка"""
    
    def __init__(
        self,
        item_width: int,
        item_height: int,
        container_width: int,
        container_height: int,
        item_renderer: Callable[[Any, int], Any],
        data_loader: Optional[Callable[[int, int], List[Any]]] = None
    ):
        self.item_width = item_width
        self.item_height = item_height
        self.container_width = container_width
        self.container_height = container_height
        self.item_renderer = item_renderer
        self.data_loader = data_loader
        
        # Розраховуємо кількість колонок
        self.columns_count = max(1, container_width // item_width)
        
        # Дані
        self._items: List[Any] = []
        self._total_count: int = 0
        self._loaded_count: int = 0
        
        # Стан прокрутки
        self._scroll_offset: float = 0
        self._visible_start_row: int = 0
        self._visible_end_row: int = 0
        
        # UI елементи
        self._container: Optional[Any] = None
        self._is_loading: bool = False
        self._has_more_data: bool = True
    
    def set_data(self, data: List[Any]):
        """Встановлює дані"""
        self._items = data
        self._total_count = len(data)
        self._loaded_count = len(data)
        self._update_visible_range()
        self._render_visible_items()
    
    def _update_visible_range(self):
        """Оновлює діапазон видимих рядків"""
        if not self._items:
            self._visible_start_row = 0
            self._visible_end_row = 0
            return
        
        # Розраховуємо видимі рядки
        start_row = int(self._scroll_offset // self.item_height)
        end_row = int((self._scroll_offset + self.container_height) // self.item_height)
        
        # Додаємо буфер
        buffer_rows = 2
        start_row = max(0, start_row - buffer_rows)
        end_row = min(self._get_total_rows(), end_row + buffer_rows)
        
        self._visible_start_row = start_row
        self._visible_end_row = end_row
    
    def _get_total_rows(self) -> int:
        """Повертає загальну кількість рядків"""
        return math.ceil(len(self._items) / self.columns_count)
    
    def _render_visible_items(self):
        """Рендерить видимі елементи"""
        if not self._container:
            return
        
        # Очищаємо контейнер
        if hasattr(self._container, 'controls'):
            self._container.controls.clear()
        
        # Рендеримо видимі рядки
        for row in range(self._visible_start_row, self._visible_end_row):
            row_items = []
            for col in range(self.columns_count):
                item_index = row * self.columns_count + col
                if item_index < len(self._items):
                    item = self._items[item_index]
                    rendered_item = self.item_renderer(item, item_index)
                    if rendered_item:
                        row_items.append(rendered_item)
            
            if row_items:
                # Додаємо рядок
                row_container = self._create_row_container(row_items)
                if hasattr(self._container, 'controls'):
                    self._container.controls.append(row_container)
    
    def _create_row_container(self, items: List[Any]) -> Any:
        """Створює контейнер для рядка"""
        # Тут потрібно створити відповідний UI елемент для рядка
        # Наприклад, ft.Row для Flet
        pass

# Утилітарні функції
def create_virtualized_list(
    item_height: int,
    container_height: int,
    item_renderer: Callable[[Any, int], Any],
    data_loader: Optional[Callable[[int, int], List[Any]]] = None
) -> VirtualizedList:
    """Створює віртуалізований список"""
    config = VirtualizationConfig(
        item_height=item_height,
        container_height=container_height
    )
    return VirtualizedList(config, item_renderer, data_loader)

def create_virtualized_grid(
    item_width: int,
    item_height: int,
    container_width: int,
    container_height: int,
    item_renderer: Callable[[Any, int], Any],
    data_loader: Optional[Callable[[int, int], List[Any]]] = None
) -> VirtualizedGrid:
    """Створює віртуалізовану сітку"""
    return VirtualizedGrid(
        item_width, item_height, container_width, container_height,
        item_renderer, data_loader
    )
