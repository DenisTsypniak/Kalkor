"""
Performance Optimizer - Система оптимізації продуктивності
"""
import asyncio
import time
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
from functools import wraps
import logging

@dataclass
class PerformanceMetrics:
    """Метрики продуктивності"""
    operation_name: str
    execution_time: float
    memory_usage: int
    cache_hits: int
    cache_misses: int

class PerformanceOptimizer:
    """Оптимізатор продуктивності"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.cache: Dict[str, Any] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger = logging.getLogger(__name__)
    
    def measure_performance(self, operation_name: str):
        """Декоратор для вимірювання продуктивності"""
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = self._get_memory_usage()
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    end_memory = self._get_memory_usage()
                    
                    metrics = PerformanceMetrics(
                        operation_name=operation_name,
                        execution_time=end_time - start_time,
                        memory_usage=end_memory - start_memory,
                        cache_hits=self.cache_hits,
                        cache_misses=self.cache_misses
                    )
                    self.metrics.append(metrics)
                    self.logger.info(f"Performance: {operation_name} - {metrics.execution_time:.3f}s")
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = self._get_memory_usage()
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    end_memory = self._get_memory_usage()
                    
                    metrics = PerformanceMetrics(
                        operation_name=operation_name,
                        execution_time=end_time - start_time,
                        memory_usage=end_memory - start_memory,
                        cache_hits=self.cache_hits,
                        cache_misses=self.cache_misses
                    )
                    self.metrics.append(metrics)
                    self.logger.info(f"Performance: {operation_name} - {metrics.execution_time:.3f}s")
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    def cache_result(self, key: str, value: Any, ttl: int = 300):
        """Кешування результату з TTL"""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time(),
            'ttl': ttl
        }
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Отримання кешованого результату"""
        if key in self.cache:
            cached = self.cache[key]
            if time.time() - cached['timestamp'] < cached['ttl']:
                self.cache_hits += 1
                return cached['value']
            else:
                del self.cache[key]
        
        self.cache_misses += 1
        return None
    
    def clear_cache(self):
        """Очищення кешу"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Отримання звіту про продуктивність"""
        if not self.metrics:
            return {"message": "No metrics available"}
        
        total_time = sum(m.execution_time for m in self.metrics)
        avg_time = total_time / len(self.metrics)
        
        return {
            "total_operations": len(self.metrics),
            "total_execution_time": total_time,
            "average_execution_time": avg_time,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "slowest_operation": max(self.metrics, key=lambda m: m.execution_time).operation_name,
            "fastest_operation": min(self.metrics, key=lambda m: m.execution_time).operation_name
        }
    
    def _get_memory_usage(self) -> int:
        """Отримання використання пам'яті"""
        try:
            import psutil
            return psutil.Process().memory_info().rss
        except ImportError:
            return 0

class LazyLoader:
    """Lazy loading для великих списків"""
    
    def __init__(self, data_source: Callable, batch_size: int = 50):
        self.data_source = data_source
        self.batch_size = batch_size
        self.loaded_data: List[Any] = []
        self.current_index = 0
        self.is_fully_loaded = False
    
    async def load_next_batch(self) -> List[Any]:
        """Завантаження наступної порції даних"""
        if self.is_fully_loaded:
            return []
        
        start_index = self.current_index
        end_index = start_index + self.batch_size
        
        batch = await self.data_source(start_index, end_index)
        self.loaded_data.extend(batch)
        self.current_index = end_index
        
        if len(batch) < self.batch_size:
            self.is_fully_loaded = True
        
        return batch
    
    def get_loaded_data(self) -> List[Any]:
        """Отримання завантажених даних"""
        return self.loaded_data
    
    def reset(self):
        """Скидання стану"""
        self.loaded_data.clear()
        self.current_index = 0
        self.is_fully_loaded = False

class VirtualizedList:
    """Віртуалізований список для великих даних"""
    
    def __init__(self, total_items: int, item_height: int, visible_height: int):
        self.total_items = total_items
        self.item_height = item_height
        self.visible_height = visible_height
        self.scroll_position = 0
        self.visible_start = 0
        self.visible_end = 0
        self._calculate_visible_range()
    
    def _calculate_visible_range(self):
        """Розрахунок видимих елементів"""
        self.visible_start = self.scroll_position // self.item_height
        self.visible_end = min(
            self.visible_start + (self.visible_height // self.item_height) + 1,
            self.total_items
        )
    
    def scroll_to(self, position: int):
        """Прокрутка до позиції"""
        self.scroll_position = max(0, min(position, self.total_items * self.item_height - self.visible_height))
        self._calculate_visible_range()
    
    def get_visible_range(self) -> tuple[int, int]:
        """Отримання діапазону видимих елементів"""
        return self.visible_start, self.visible_end
    
    def get_scroll_offset(self) -> int:
        """Отримання зміщення прокрутки"""
        return self.scroll_position % self.item_height

# Глобальний екземпляр оптимізатора
performance_optimizer = PerformanceOptimizer()
