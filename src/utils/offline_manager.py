"""
Менеджер офлайн режиму з синхронізацією
"""

import asyncio
import logging
import json
import time
from typing import Any, Dict, List, Callable, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)

class OperationType(Enum):
    """Тип операції"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SYNC = "sync"

class SyncStatus(Enum):
    """Статус синхронізації"""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"

@dataclass
class OfflineOperation:
    """Операція для офлайн режиму"""
    id: str
    type: OperationType
    entity_type: str
    entity_id: str
    data: Dict[str, Any]
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3
    status: SyncStatus = SyncStatus.PENDING
    error_message: Optional[str] = None

@dataclass
class SyncResult:
    """Результат синхронізації"""
    success: bool
    synced_count: int
    failed_count: int
    errors: List[str]

class OfflineManager:
    """Менеджер офлайн режиму"""
    
    def __init__(self, storage_path: str = "offline_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Операції
        self._pending_operations: List[OfflineOperation] = []
        self._operation_queue: asyncio.Queue = asyncio.Queue()
        
        # Стан
        self._is_online: bool = True
        self._is_syncing: bool = False
        self._last_sync_time: Optional[float] = None
        
        # Callbacks
        self._sync_callbacks: List[Callable] = []
        self._online_callbacks: List[Callable] = []
        self._offline_callbacks: List[Callable] = []
        
        # Конфігурація
        self._auto_sync_interval: int = 300  # 5 хвилин
        self._max_operations_in_memory: int = 1000
        
        # Запускаємо фонові задачі
        self._sync_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Запускає фонові задачі"""
        self._sync_task = asyncio.create_task(self._auto_sync_loop())
        self._monitor_task = asyncio.create_task(self._monitor_connectivity())
    
    async def _auto_sync_loop(self):
        """Автоматична синхронізація"""
        while True:
            try:
                await asyncio.sleep(self._auto_sync_interval)
                if self._is_online and not self._is_syncing and self._pending_operations:
                    await self.sync_pending_operations()
            except Exception as e:
                logger.error(f"Error in auto sync loop: {e}")
    
    async def _monitor_connectivity(self):
        """Моніторинг підключення"""
        while True:
            try:
                # Простий перевірка підключення
                is_online = await self._check_connectivity()
                
                if is_online != self._is_online:
                    self._is_online = is_online
                    if is_online:
                        await self._notify_online()
                        # Синхронізуємо при відновленні підключення
                        if self._pending_operations:
                            await self.sync_pending_operations()
                    else:
                        await self._notify_offline()
                
                await asyncio.sleep(30)  # Перевіряємо кожні 30 секунд
            except Exception as e:
                logger.error(f"Error in connectivity monitor: {e}")
    
    async def _check_connectivity(self) -> bool:
        """Перевіряє підключення до інтернету"""
        try:
            # Простий ping до надійного сервера
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://httpbin.org/status/200', timeout=5) as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def _notify_online(self):
        """Сповіщає про відновлення підключення"""
        for callback in self._online_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in online callback: {e}")
    
    async def _notify_offline(self):
        """Сповіщає про втрату підключення"""
        for callback in self._offline_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in offline callback: {e}")
    
    async def queue_operation(
        self,
        operation_type: OperationType,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        sync_immediately: bool = False
    ) -> str:
        """Додає операцію в чергу"""
        operation_id = f"{entity_type}_{entity_id}_{int(time.time() * 1000)}"
        
        operation = OfflineOperation(
            id=operation_id,
            type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data,
            timestamp=time.time()
        )
        
        # Додаємо в чергу
        await self._operation_queue.put(operation)
        self._pending_operations.append(operation)
        
        # Зберігаємо на диск
        await self._save_operation_to_disk(operation)
        
        # Синхронізуємо одразу якщо онлайн
        if self._is_online and sync_immediately:
            await self.sync_pending_operations()
        
        return operation_id
    
    async def _save_operation_to_disk(self, operation: OfflineOperation):
        """Зберігає операцію на диск"""
        try:
            operation_file = self.storage_path / f"{operation.id}.json"
            async with aiofiles.open(operation_file, 'w') as f:
                await f.write(json.dumps(asdict(operation), indent=2))
        except Exception as e:
            logger.error(f"Error saving operation to disk: {e}")
    
    async def _load_operations_from_disk(self):
        """Завантажує операції з диска"""
        try:
            for operation_file in self.storage_path.glob("*.json"):
                async with aiofiles.open(operation_file, 'r') as f:
                    operation_data = json.loads(await f.read())
                    operation = OfflineOperation(**operation_data)
                    self._pending_operations.append(operation)
        except Exception as e:
            logger.error(f"Error loading operations from disk: {e}")
    
    async def sync_pending_operations(self) -> SyncResult:
        """Синхронізує всі очікуючі операції"""
        if self._is_syncing or not self._is_online:
            return SyncResult(False, 0, 0, ["Already syncing or offline"])
        
        self._is_syncing = True
        synced_count = 0
        failed_count = 0
        errors = []
        
        try:
            # Завантажуємо операції з диска
            await self._load_operations_from_disk()
            
            # Синхронізуємо по черзі
            for operation in self._pending_operations[:]:
                try:
                    success = await self._sync_single_operation(operation)
                    if success:
                        synced_count += 1
                        operation.status = SyncStatus.SYNCED
                        self._pending_operations.remove(operation)
                        await self._remove_operation_from_disk(operation.id)
                    else:
                        failed_count += 1
                        operation.status = SyncStatus.FAILED
                        operation.retry_count += 1
                        
                        if operation.retry_count >= operation.max_retries:
                            errors.append(f"Max retries exceeded for operation {operation.id}")
                            self._pending_operations.remove(operation)
                            await self._remove_operation_from_disk(operation.id)
                
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Error syncing operation {operation.id}: {e}")
                    operation.status = SyncStatus.FAILED
                    operation.error_message = str(e)
            
            self._last_sync_time = time.time()
            
            # Сповіщаємо про завершення синхронізації
            await self._notify_sync_complete(synced_count, failed_count)
            
            return SyncResult(
                success=failed_count == 0,
                synced_count=synced_count,
                failed_count=failed_count,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Error in sync_pending_operations: {e}")
            return SyncResult(False, synced_count, failed_count, [str(e)])
        finally:
            self._is_syncing = False
    
    async def _sync_single_operation(self, operation: OfflineOperation) -> bool:
        """Синхронізує одну операцію"""
        try:
            # Тут має бути логіка синхронізації з сервером
            # Наприклад, HTTP запити до API
            
            if operation.type == OperationType.CREATE:
                # Створюємо на сервері
                success = await self._create_on_server(operation.entity_type, operation.data)
            elif operation.type == OperationType.UPDATE:
                # Оновлюємо на сервері
                success = await self._update_on_server(operation.entity_type, operation.entity_id, operation.data)
            elif operation.type == OperationType.DELETE:
                # Видаляємо на сервері
                success = await self._delete_on_server(operation.entity_type, operation.entity_id)
            else:
                success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error syncing operation {operation.id}: {e}")
            return False
    
    async def _create_on_server(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Створює сутність на сервері"""
        # Тут має бути реальна логіка HTTP запиту
        # Наприклад:
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(f"/api/{entity_type}", json=data) as response:
        #         return response.status == 201
        
        # Заглушка для демонстрації
        await asyncio.sleep(0.1)  # Імітація мережевого запиту
        return True
    
    async def _update_on_server(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> bool:
        """Оновлює сутність на сервері"""
        # Тут має бути реальна логіка HTTP запиту
        await asyncio.sleep(0.1)  # Імітація мережевого запиту
        return True
    
    async def _delete_on_server(self, entity_type: str, entity_id: str) -> bool:
        """Видаляє сутність на сервері"""
        # Тут має бути реальна логіка HTTP запиту
        await asyncio.sleep(0.1)  # Імітація мережевого запиту
        return True
    
    async def _remove_operation_from_disk(self, operation_id: str):
        """Видаляє операцію з диска"""
        try:
            operation_file = self.storage_path / f"{operation_id}.json"
            if operation_file.exists():
                operation_file.unlink()
        except Exception as e:
            logger.error(f"Error removing operation from disk: {e}")
    
    async def _notify_sync_complete(self, synced_count: int, failed_count: int):
        """Сповіщає про завершення синхронізації"""
        for callback in self._sync_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(synced_count, failed_count)
                else:
                    callback(synced_count, failed_count)
            except Exception as e:
                logger.error(f"Error in sync callback: {e}")
    
    def is_online(self) -> bool:
        """Перевіряє чи онлайн"""
        return self._is_online
    
    def is_syncing(self) -> bool:
        """Перевіряє чи синхронізується"""
        return self._is_syncing
    
    def get_pending_operations_count(self) -> int:
        """Повертає кількість очікуючих операцій"""
        return len(self._pending_operations)
    
    def get_last_sync_time(self) -> Optional[float]:
        """Повертає час останньої синхронізації"""
        return self._last_sync_time
    
    def on_sync_complete(self, callback: Callable[[int, int], None]):
        """Підписується на завершення синхронізації"""
        self._sync_callbacks.append(callback)
    
    def on_online(self, callback: Callable[[], None]):
        """Підписується на відновлення підключення"""
        self._online_callbacks.append(callback)
    
    def on_offline(self, callback: Callable[[], None]):
        """Підписується на втрату підключення"""
        self._offline_callbacks.append(callback)
    
    async def clear_pending_operations(self):
        """Очищає всі очікуючі операції"""
        self._pending_operations.clear()
        
        # Видаляємо файли з диска
        for operation_file in self.storage_path.glob("*.json"):
            try:
                operation_file.unlink()
            except Exception as e:
                logger.error(f"Error removing operation file {operation_file}: {e}")
    
    async def dispose(self):
        """Звільняє ресурси"""
        if self._sync_task:
            self._sync_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        
        # Чекаємо завершення задач
        if self._sync_task:
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        if self._monitor_task:
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

# Декоратори для офлайн режиму
def offline_operation(entity_type: str, operation_type: OperationType):
    """Декоратор для операцій в офлайн режимі"""
    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            offline_manager = get_offline_manager()
            
            if offline_manager.is_online():
                # Якщо онлайн, виконуємо операцію
                return await func(*args, **kwargs)
            else:
                # Якщо офлайн, додаємо в чергу
                entity_id = kwargs.get('entity_id', str(int(time.time() * 1000)))
                data = kwargs.get('data', {})
                
                operation_id = await offline_manager.queue_operation(
                    operation_type=operation_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    data=data
                )
                
                return {'operation_id': operation_id, 'offline': True}
        
        def sync_wrapper(*args, **kwargs):
            offline_manager = get_offline_manager()
            
            if offline_manager.is_online():
                return func(*args, **kwargs)
            else:
                entity_id = kwargs.get('entity_id', str(int(time.time() * 1000)))
                data = kwargs.get('data', {})
                
                # Для синхронних функцій створюємо задачу
                asyncio.create_task(offline_manager.queue_operation(
                    operation_type=operation_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    data=data
                ))
                
                return {'offline': True}
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Глобальний екземпляр
_offline_manager: Optional[OfflineManager] = None

def get_offline_manager() -> OfflineManager:
    """Отримує глобальний менеджер офлайн режиму"""
    global _offline_manager
    if _offline_manager is None:
        _offline_manager = OfflineManager()
    return _offline_manager

async def dispose_offline_manager():
    """Звільняє глобальний менеджер офлайн режиму"""
    global _offline_manager
    if _offline_manager:
        await _offline_manager.dispose()
        _offline_manager = None
