"""
Конфігурація систем оптимізації
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class OptimizationConfig:
    """Конфігурація оптимізацій"""
    
    # Database Pool
    db_pool_min_connections: int = 2
    db_pool_max_connections: int = 10
    db_pool_timeout: int = 30
    
    # Image Loading
    image_cache_size: int = 100
    image_max_size: int = 800
    image_quality: int = 85
    
    # UI Responsiveness
    debounce_delay: float = 0.3
    throttle_rate: float = 1.0
    
    # Animation
    default_animation_duration: float = 0.3
    animation_fps: int = 60
    
    # Metrics
    metrics_save_interval: int = 300  # 5 хвилин
    metrics_max_history: int = 10000
    
    # Backup
    backup_max_count: int = 10
    backup_auto_interval: int = 3600  # 1 година
    backup_encryption: bool = True
    backup_compression: bool = True
    
    # Offline
    offline_sync_interval: int = 1800  # 30 хвилин
    offline_max_retries: int = 3
    
    # Error Handling
    error_log_level: str = "ERROR"
    error_notification_enabled: bool = True
    
    # Theme
    default_theme: str = "dark"
    theme_auto_save: bool = True
    
    @classmethod
    def from_env(cls) -> 'OptimizationConfig':
        """Створює конфігурацію з змінних середовища"""
        return cls(
            db_pool_min_connections=int(os.getenv('DB_POOL_MIN', 2)),
            db_pool_max_connections=int(os.getenv('DB_POOL_MAX', 10)),
            db_pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', 30)),
            
            image_cache_size=int(os.getenv('IMAGE_CACHE_SIZE', 100)),
            image_max_size=int(os.getenv('IMAGE_MAX_SIZE', 800)),
            image_quality=int(os.getenv('IMAGE_QUALITY', 85)),
            
            debounce_delay=float(os.getenv('DEBOUNCE_DELAY', 0.3)),
            throttle_rate=float(os.getenv('THROTTLE_RATE', 1.0)),
            
            default_animation_duration=float(os.getenv('ANIMATION_DURATION', 0.3)),
            animation_fps=int(os.getenv('ANIMATION_FPS', 60)),
            
            metrics_save_interval=int(os.getenv('METRICS_SAVE_INTERVAL', 300)),
            metrics_max_history=int(os.getenv('METRICS_MAX_HISTORY', 10000)),
            
            backup_max_count=int(os.getenv('BACKUP_MAX_COUNT', 10)),
            backup_auto_interval=int(os.getenv('BACKUP_AUTO_INTERVAL', 3600)),
            backup_encryption=os.getenv('BACKUP_ENCRYPTION', 'true').lower() == 'true',
            backup_compression=os.getenv('BACKUP_COMPRESSION', 'true').lower() == 'true',
            
            offline_sync_interval=int(os.getenv('OFFLINE_SYNC_INTERVAL', 1800)),
            offline_max_retries=int(os.getenv('OFFLINE_MAX_RETRIES', 3)),
            
            error_log_level=os.getenv('ERROR_LOG_LEVEL', 'ERROR'),
            error_notification_enabled=os.getenv('ERROR_NOTIFICATION', 'true').lower() == 'true',
            
            default_theme=os.getenv('DEFAULT_THEME', 'dark'),
            theme_auto_save=os.getenv('THEME_AUTO_SAVE', 'true').lower() == 'true'
        )

# Глобальна конфігурація
_config: Optional[OptimizationConfig] = None

def get_optimization_config() -> OptimizationConfig:
    """Отримує глобальну конфігурацію оптимізацій"""
    global _config
    if _config is None:
        _config = OptimizationConfig.from_env()
    return _config

def set_optimization_config(config: OptimizationConfig):
    """Встановлює глобальну конфігурацію оптимізацій"""
    global _config
    _config = config
