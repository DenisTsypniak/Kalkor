"""
Збір метрик продуктивності
"""

import asyncio
import logging
import time
import psutil
import json
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Метрика продуктивності"""
    name: str
    value: float
    timestamp: datetime
    category: str
    tags: Dict[str, str] = None

@dataclass
class SystemMetrics:
    """Системні метрики"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_sent_mb: float
    network_recv_mb: float
    timestamp: datetime

@dataclass
class OperationMetrics:
    """Метрики операцій"""
    operation_name: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = None
    metadata: Dict[str, Any] = None

@dataclass
class UIMetrics:
    """Метрики UI"""
    view_name: str
    load_time_ms: float
    render_time_ms: float
    user_interactions: int
    timestamp: datetime

class MetricsCollector:
    """Збирач метрик"""
    
    def __init__(self, storage_path: str = "metrics"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)  # Створюємо папку якщо не існує
        
        # Метрики
        self._performance_metrics: deque = deque(maxlen=10000)
        self._operation_metrics: deque = deque(maxlen=10000)
        self._ui_metrics: deque = deque(maxlen=10000)
        self._system_metrics: deque = deque(maxlen=1000)
        
        # Статистика
        self._operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'success_count': 0,
            'error_count': 0,
            'min_duration': float('inf'),
            'max_duration': 0.0,
            'avg_duration': 0.0
        })
        
        # Callbacks
        self._metrics_callbacks: List[Callable] = []
        
        # Фонові задачі
        self._system_metrics_task: Optional[asyncio.Task] = None
        self._save_metrics_task: Optional[asyncio.Task] = None
        
        # Конфігурація
        self._system_metrics_interval: int = 30  # секунд
        self._save_metrics_interval: int = 300  # 5 хвилин
        self._enabled: bool = True
        
        # Запускаємо фонові задачі
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Запускає фонові задачі"""
        self._system_metrics_task = asyncio.create_task(self._collect_system_metrics_loop())
        self._save_metrics_task = asyncio.create_task(self._save_metrics_loop())
    
    async def _collect_system_metrics_loop(self):
        """Цикл збору системних метрик"""
        while True:
            try:
                await asyncio.sleep(self._system_metrics_interval)
                if self._enabled:
                    await self._collect_system_metrics()
            except Exception as e:
                logger.error(f"Error in system metrics loop: {e}")
    
    async def _save_metrics_loop(self):
        """Цикл збереження метрик"""
        while True:
            try:
                await asyncio.sleep(self._save_metrics_interval)
                if self._enabled:
                    await self._save_metrics_to_disk()
            except Exception as e:
                logger.error(f"Error in save metrics loop: {e}")
    
    async def _collect_system_metrics(self):
        """Збирає системні метрики"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # Network
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / (1024 * 1024)
            network_recv_mb = network.bytes_recv / (1024 * 1024)
            
            system_metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                timestamp=datetime.now()
            )
            
            self._system_metrics.append(system_metrics)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def record_operation(
        self,
        operation_name: str,
        duration_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Записує метрику операції"""
        if not self._enabled:
            return
        
        operation_metric = OperationMetrics(
            operation_name=operation_name,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self._operation_metrics.append(operation_metric)
        
        # Оновлюємо статистику
        stats = self._operation_stats[operation_name]
        stats['count'] += 1
        stats['total_duration'] += duration_ms
        stats['min_duration'] = min(stats['min_duration'], duration_ms)
        stats['max_duration'] = max(stats['max_duration'], duration_ms)
        stats['avg_duration'] = stats['total_duration'] / stats['count']
        
        if success:
            stats['success_count'] += 1
        else:
            stats['error_count'] += 1
    
    def record_performance_metric(
        self,
        name: str,
        value: float,
        category: str = "general",
        tags: Optional[Dict[str, str]] = None
    ):
        """Записує метрику продуктивності"""
        if not self._enabled:
            return
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            category=category,
            tags=tags or {}
        )
        
        self._performance_metrics.append(metric)
    
    def record_ui_metrics(
        self,
        view_name: str,
        load_time_ms: float,
        render_time_ms: float,
        user_interactions: int = 0
    ):
        """Записує метрики UI"""
        if not self._enabled:
            return
        
        ui_metric = UIMetrics(
            view_name=view_name,
            load_time_ms=load_time_ms,
            render_time_ms=render_time_ms,
            user_interactions=user_interactions,
            timestamp=datetime.now()
        )
        
        self._ui_metrics.append(ui_metric)
    
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """Повертає статистику операцій"""
        if operation_name:
            return self._operation_stats.get(operation_name, {})
        return dict(self._operation_stats)
    
    def get_performance_metrics(
        self,
        category: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """Повертає метрики продуктивності"""
        metrics = list(self._performance_metrics)
        
        if category:
            metrics = [m for m in metrics if m.category == category]
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return metrics
    
    def get_system_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[SystemMetrics]:
        """Повертає системні метрики"""
        metrics = list(self._system_metrics)
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return metrics
    
    def get_ui_metrics(
        self,
        view_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[UIMetrics]:
        """Повертає метрики UI"""
        metrics = list(self._ui_metrics)
        
        if view_name:
            metrics = [m for m in metrics if m.view_name == view_name]
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return metrics
    
    async def _save_metrics_to_disk(self):
        """Зберігає метрики на диск"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Зберігаємо метрики продуктивності
            if self._performance_metrics:
                perf_file = self.storage_path / f"performance_{timestamp}.json"
                perf_data = [asdict(m) for m in self._performance_metrics]
                async with aiofiles.open(perf_file, 'w') as f:
                    await f.write(json.dumps(perf_data, indent=2, default=str))
            
            # Зберігаємо метрики операцій
            if self._operation_metrics:
                ops_file = self.storage_path / f"operations_{timestamp}.json"
                ops_data = [asdict(m) for m in self._operation_metrics]
                async with aiofiles.open(ops_file, 'w') as f:
                    await f.write(json.dumps(ops_data, indent=2, default=str))
            
            # Зберігаємо системні метрики
            if self._system_metrics:
                sys_file = self.storage_path / f"system_{timestamp}.json"
                sys_data = [asdict(m) for m in self._system_metrics]
                async with aiofiles.open(sys_file, 'w') as f:
                    await f.write(json.dumps(sys_data, indent=2, default=str))
            
            # Зберігаємо метрики UI
            if self._ui_metrics:
                ui_file = self.storage_path / f"ui_{timestamp}.json"
                ui_data = [asdict(m) for m in self._ui_metrics]
                async with aiofiles.open(ui_file, 'w') as f:
                    await f.write(json.dumps(ui_data, indent=2, default=str))
            
            # Зберігаємо статистику
            stats_file = self.storage_path / f"stats_{timestamp}.json"
            async with aiofiles.open(stats_file, 'w') as f:
                await f.write(json.dumps(dict(self._operation_stats), indent=2, default=str))
            
        except Exception as e:
            logger.error(f"Error saving metrics to disk: {e}")
    
    def generate_report(self) -> Dict[str, Any]:
        """Генерує звіт по метриках"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'operation_stats': dict(self._operation_stats),
            'system_summary': self._get_system_summary(),
            'performance_summary': self._get_performance_summary(),
            'ui_summary': self._get_ui_summary()
        }
        
        return report
    
    def _get_system_summary(self) -> Dict[str, Any]:
        """Повертає підсумок системних метрик"""
        if not self._system_metrics:
            return {}
        
        recent_metrics = list(self._system_metrics)[-10:]  # Останні 10 записів
        
        return {
            'avg_cpu_percent': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            'avg_memory_percent': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            'avg_disk_usage_percent': sum(m.disk_usage_percent for m in recent_metrics) / len(recent_metrics),
            'total_network_sent_mb': recent_metrics[-1].network_sent_mb if recent_metrics else 0,
            'total_network_recv_mb': recent_metrics[-1].network_recv_mb if recent_metrics else 0
        }
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Повертає підсумок метрик продуктивності"""
        if not self._performance_metrics:
            return {}
        
        # Групуємо по категоріях
        categories = defaultdict(list)
        for metric in self._performance_metrics:
            categories[metric.category].append(metric.value)
        
        summary = {}
        for category, values in categories.items():
            summary[category] = {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values)
            }
        
        return summary
    
    def _get_ui_summary(self) -> Dict[str, Any]:
        """Повертає підсумок метрик UI"""
        if not self._ui_metrics:
            return {}
        
        # Групуємо по view
        views = defaultdict(list)
        for metric in self._ui_metrics:
            views[metric.view_name].append(metric)
        
        summary = {}
        for view_name, metrics in views.items():
            summary[view_name] = {
                'count': len(metrics),
                'avg_load_time': sum(m.load_time_ms for m in metrics) / len(metrics),
                'avg_render_time': sum(m.render_time_ms for m in metrics) / len(metrics),
                'total_interactions': sum(m.user_interactions for m in metrics)
            }
        
        return summary
    
    def enable(self):
        """Увімкнює збір метрик"""
        self._enabled = True
    
    def disable(self):
        """Вимкнює збір метрик"""
        self._enabled = False
    
    def clear_metrics(self):
        """Очищає всі метрики"""
        self._performance_metrics.clear()
        self._operation_metrics.clear()
        self._ui_metrics.clear()
        self._system_metrics.clear()
        self._operation_stats.clear()
    
    def on_metrics_updated(self, callback: Callable[[str], None]):
        """Підписується на оновлення метрик"""
        self._metrics_callbacks.append(callback)
    
    async def dispose(self):
        """Звільняє ресурси"""
        if self._system_metrics_task:
            self._system_metrics_task.cancel()
        if self._save_metrics_task:
            self._save_metrics_task.cancel()
        
        # Чекаємо завершення задач
        if self._system_metrics_task:
            try:
                await self._system_metrics_task
            except asyncio.CancelledError:
                pass
        
        if self._save_metrics_task:
            try:
                await self._save_metrics_task
            except asyncio.CancelledError:
                pass

# Декоратори для метрик
def track_operation(operation_name: str):
    """Декоратор для відстеження операцій"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                collector = get_metrics_collector()
                collector.record_operation(operation_name, duration_ms, success, error_message)
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                collector = get_metrics_collector()
                collector.record_operation(operation_name, duration_ms, success, error_message)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def track_performance(metric_name: str, category: str = "general"):
    """Декоратор для відстеження продуктивності"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            collector = get_metrics_collector()
            collector.record_performance_metric(metric_name, duration_ms, category)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            collector = get_metrics_collector()
            collector.record_performance_metric(metric_name, duration_ms, category)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Утилітарні функції
def record_operation_metric(operation_name: str, duration_ms: float, success: bool = True):
    """Записує метрику операції"""
    collector = get_metrics_collector()
    collector.record_operation(operation_name, duration_ms, success)

def record_performance_metric(name: str, value: float, category: str = "general"):
    """Записує метрику продуктивності"""
    collector = get_metrics_collector()
    collector.record_performance_metric(name, value, category)

def record_ui_metric(view_name: str, load_time_ms: float, render_time_ms: float):
    """Записує метрику UI"""
    collector = get_metrics_collector()
    collector.record_ui_metrics(view_name, load_time_ms, render_time_ms)

# Глобальний екземпляр
_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Отримує глобальний збирач метрик"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

async def dispose_metrics_collector():
    """Звільняє глобальний збирач метрик"""
    global _metrics_collector
    if _metrics_collector:
        await _metrics_collector.dispose()
        _metrics_collector = None
