"""
Універсальний менеджер для drag & drop функціональності карток
"""

import flet as ft
import asyncio
import logging
from typing import List, Callable, Optional, Any, Dict, Set
from src.utils.ui.helpers import SafeAsyncExecutor

logger = logging.getLogger(__name__)


class DragDropManager:
    """
    Універсальний менеджер для створення та управління drag & drop функціональністю
    """
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._current_dragged_id: Optional[int] = None
        self._created_cards: Set[str] = set()  # Трекимо створені картки
        self._card_references: Dict[str, ft.DragTarget] = {}  # Зберігаємо посилання
    
    def create_draggable_card(
        self, 
        card_content: ft.Control, 
        item_id: int, 
        group_name: str, 
        swap_callback: Callable, 
        card_width: int = 220, 
        card_height: int = 280
    ) -> ft.DragTarget:
        """
        Універсальна функція для створення draggable картки з drag & drop функціональністю
        
        Args:
            card_content: Вміст картки (Container з картинкою, текстом тощо)
            item_id: ID об'єкта (property, transaction тощо)
            group_name: Назва групи для drag & drop (наприклад, "properties", "transactions")
            swap_callback: Функція для обміну місцями (async функція, яка приймає target_id)
            card_width: Ширина картки
            card_height: Висота картки
        """
        card_key = f"{group_name}_{item_id}"
        
        # Placeholder для перетягування
        placeholder = ft.Container(
            width=card_width,
            height=card_height,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_200),
            border_radius=16,
            border=ft.border.all(1, ft.Colors.BLUE_200),
        )
        
        # Draggable компонент (спрощена версія без потенційно проблемних параметрів)
        drag = ft.Draggable(
            group=group_name,
            data=str(item_id),
            content=card_content,
            content_when_dragging=placeholder,
            on_drag_start=lambda e: self._on_drag_start(item_id),
        )

        # Фрейм з рамкою
        frame = ft.Container(
            content=drag,
            border_radius=16,
            border=ft.border.all(1, ft.Colors.GREY_700),
        )

        # Функції для візуальної зворотної зв'язки
        def _will_accept(e):
            frame.border = ft.border.all(2, ft.Colors.BLUE_400)
            if frame.page:
                frame.update()

        def _leave(e):
            frame.border = ft.border.all(1, ft.Colors.GREY_700)
            if frame.page:
                frame.update()

        # DragTarget з обробкою drop подій
        def _on_accept(e):
            if self.page:
                # Використовуємо run_task для асинхронних callback
                if asyncio.iscoroutinefunction(swap_callback):
                    self.page.run_task(swap_callback, item_id)
                else:
                    # Перевіряємо кількість аргументів функції
                    import inspect
                    sig = inspect.signature(swap_callback)
                    if len(sig.parameters) == 2:  # Функція очікує 2 аргументи (e, target_id)
                        swap_callback(e, item_id)
                    else:  # Функція очікує 1 аргумент (target_id)
                        swap_callback(item_id)
        
        drag_target = ft.DragTarget(
            group=group_name,
            content=frame,
            on_will_accept=_will_accept,
            on_leave=_leave,
            on_accept=_on_accept,
        )
        
        # Зберігаємо посилання для подальшого очищення
        self._created_cards.add(card_key)
        self._card_references[card_key] = drag_target
        
        logger.debug(f"Created draggable card: {card_key}")
        return drag_target
    
    def cleanup_card(self, item_id: int, group_name: str) -> bool:
        """
        Очищає ресурси конкретної картки
        
        Args:
            item_id: ID об'єкта
            group_name: Назва групи
            
        Returns:
            bool: True якщо картка була знайдена та очищена
        """
        card_key = f"{group_name}_{item_id}"
        
        if card_key in self._card_references:
            # Очищаємо посилання
            drag_target = self._card_references.pop(card_key)
            self._created_cards.discard(card_key)
            
            # Очищаємо вміст
            if hasattr(drag_target, 'content') and drag_target.content:
                if hasattr(drag_target.content, 'content'):
                    drag_target.content.content = None
                drag_target.content = None
            
            logger.debug(f"Cleaned up card: {card_key}")
            return True
        
        return False
    
    def cleanup_group(self, group_name: str) -> int:
        """
        Очищає всі картки групи
        
        Args:
            group_name: Назва групи для очищення
            
        Returns:
            int: Кількість очищених карток
        """
        cards_to_remove = []
        cleaned_count = 0
        
        for card_key in self._created_cards:
            if card_key.startswith(f"{group_name}_"):
                cards_to_remove.append(card_key)
        
        for card_key in cards_to_remove:
            if self.cleanup_card(int(card_key.split('_')[1]), group_name):
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} cards from group: {group_name}")
        return cleaned_count
    
    def cleanup_all(self) -> int:
        """
        Очищає всі картки
        
        Returns:
            int: Кількість очищених карток
        """
        total_cards = len(self._created_cards)
        
        # Очищаємо всі посилання
        for card_key in list(self._created_cards):
            try:
                # Розбиваємо ключ на частини
                parts = card_key.split('_')
                if len(parts) >= 3:
                    # Формат: props_swap_17 -> group_name = "props_swap", item_id = "17"
                    group_name = '_'.join(parts[:-1])  # Всі частини крім останньої
                    item_id = parts[-1]  # Остання частина
                    self.cleanup_card(int(item_id), group_name)
                else:
                    # Старий формат: props_17 -> group_name = "props", item_id = "17"
                    group_name, item_id = card_key.split('_', 1)
                    self.cleanup_card(int(item_id), group_name)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse card key '{card_key}': {e}")
                # Видаляємо неправильний ключ з множини
                self._created_cards.discard(card_key)
        
        self._created_cards.clear()
        self._card_references.clear()
        
        logger.info(f"Cleaned up all {total_cards} cards")
        return total_cards
    
    def get_card_count(self, group_name: Optional[str] = None) -> int:
        """
        Повертає кількість активних карток
        
        Args:
            group_name: Якщо вказано, повертає кількість карток тільки для цієї групи
            
        Returns:
            int: Кількість карток
        """
        if group_name:
            return len([key for key in self._created_cards if key.startswith(f"{group_name}_")])
        return len(self._created_cards)
    
    def create_draggable_row(self, cards: List[ft.DragTarget], spacing: int = 12) -> ft.Row:
        """
        Створює рядок з draggable картками
        
        Args:
            cards: Список DragTarget карток
            spacing: Відступ між картками
            
        Returns:
            ft.Row: Рядок з картками
        """
        if not cards:
            return ft.Row([], spacing=spacing)
        
        return ft.Row(
            cards,
            spacing=spacing,
            vertical_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        )
    
    def _on_drag_start(self, item_id: int):
        """Обробляє початок перетягування"""
        self._current_dragged_id = item_id
        logger.info(f"🎯 Drag started for item: {item_id}")
    
    def get_current_dragged_id(self) -> Optional[int]:
        """Повертає ID поточного перетягуваного елемента"""
        return self._current_dragged_id
    
    def clear_dragged_id(self):
        """Очищає ID перетягуваного елемента"""
        self._current_dragged_id = None
    
    async def handle_swap_async(self, target_id: int, current_ids: List[int], 
                               update_order_callback: Callable, 
                               refresh_ui_callback: Callable) -> bool:
        """
        Асинхронно обробляє swap операцію з timeout та обробкою помилок
        """
        try:
            logger.info(f"🔄 Starting swap operation: target_id={target_id}, current_ids={current_ids}")
            
            # Додаємо timeout для операції
            timeout_seconds = 10.0
            
            # Розраховуємо новий порядок
            new_order = self._calculate_new_order(target_id, current_ids)
            
            if new_order == current_ids:
                logger.info("📍 No order change needed, skipping update")
                return True
            
            # Виконуємо оновлення порядку з timeout
            logger.info(f"💾 Updating order in database: {new_order}")
            await asyncio.wait_for(
                update_order_callback(new_order),
                timeout=timeout_seconds
            )
            
            # Оновлюємо UI
            logger.info(f"🎨 Refreshing UI with new order: {new_order}")
            await refresh_ui_callback(new_order)
            
            logger.info(f"✅ Swap operation completed successfully for target: {target_id}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Swap operation timed out after {timeout_seconds} seconds")
            return False
        except Exception as e:
            logger.error(f"❌ Error in swap operation: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
        finally:
            self._current_dragged_id = None
    
    def _calculate_new_order(self, target_id: int, current_ids: List[int]) -> List[int]:
        """
        Розраховує новий порядок після swap операції
        """
        logger.info(f"🔄 Calculating new order: target_id={target_id}, current_ids={current_ids}")
        
        if not current_ids or target_id not in current_ids:
            logger.warning(f"❌ Invalid target_id or empty current_ids: target_id={target_id}, current_ids={current_ids}")
            return current_ids
        
        # Знаходимо індекси
        dragged_id = self._current_dragged_id
        if not dragged_id or dragged_id not in current_ids:
            logger.warning(f"❌ Invalid dragged_id: dragged_id={dragged_id}, current_ids={current_ids}")
            return current_ids
        
        dragged_index = current_ids.index(dragged_id)
        target_index = current_ids.index(target_id)
        
        logger.info(f"📍 Indexes: dragged_index={dragged_index}, target_index={target_index}")
        
        # Створюємо новий порядок
        new_order = current_ids.copy()
        
        # Якщо перетягуємо в ту ж позицію, нічого не змінюємо
        if dragged_index == target_index:
            logger.info("📍 Same position, no change needed")
            return new_order
        
        # Видаляємо елемент з поточної позиції
        item = new_order.pop(dragged_index)
        
        # Вставляємо в нову позицію
        if dragged_index < target_index:
            # Перетягуємо вправо
            new_order.insert(target_index, item)
        else:
            # Перетягуємо вліво
            new_order.insert(target_index, item)
        
        logger.info(f"✅ New order calculated: {new_order}")
        return new_order
