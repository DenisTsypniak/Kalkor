"""
Інтеграція всіх нових систем оптимізації
"""

import asyncio
import logging
from typing import Optional

from src.core.database_pool import get_db_pool, close_db_pool
from src.core.dependency_injection import get_service_provider, dispose_services
from src.core.state_management import get_store
from src.utils.lazy_image_loader import get_image_loader
from src.utils.ui_responsiveness import get_ui_responsiveness_manager
from src.utils.error_handler import get_error_handler
from src.utils.virtualized_list import VirtualizedList
from src.utils.offline_manager import get_offline_manager, dispose_offline_manager
from src.utils.animation_manager import get_animation_manager
from src.themes.theme_manager import get_theme_manager
from src.utils.validators import DataValidator
from src.utils.backup_manager import get_backup_manager, dispose_backup_sync
from src.utils.metrics_collector import get_metrics_collector, dispose_metrics_collector

logger = logging.getLogger(__name__)

class SystemIntegrator:
    """Інтегратор всіх систем"""
    
    def __init__(self):
        self._initialized = False
        self._services = {}
    
    async def initialize_all_systems(self):
        """Ініціалізує всі системи"""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing all optimization systems...")
            
            # 1. Database Pool
            logger.info("Initializing database pool...")
            db_pool = await get_db_pool()
            self._services['db_pool'] = db_pool
            
            # 2. Dependency Injection
            logger.info("Initializing dependency injection...")
            service_provider = get_service_provider()
            self._services['service_provider'] = service_provider
            
            # 3. State Management
            logger.info("Initializing state management...")
            store = get_store()
            self._services['store'] = store
            
            # 4. Image Loader
            logger.info("Initializing lazy image loader...")
            image_loader = get_image_loader()
            self._services['image_loader'] = image_loader
            
            # 5. UI Responsiveness
            logger.info("Initializing UI responsiveness...")
            ui_manager = get_ui_responsiveness_manager()
            self._services['ui_manager'] = ui_manager
            
            # 6. Error Handler
            logger.info("Initializing error handler...")
            error_handler = get_error_handler()
            self._services['error_handler'] = error_handler
            
            # 7. Offline Manager
            logger.info("Initializing offline manager...")
            offline_manager = get_offline_manager()
            self._services['offline_manager'] = offline_manager
            
            # 8. Animation Manager
            logger.info("Initializing animation manager...")
            animation_manager = get_animation_manager()
            self._services['animation_manager'] = animation_manager
            
            # 9. Theme Manager
            logger.info("Initializing theme manager...")
            theme_manager = get_theme_manager()
            self._services['theme_manager'] = theme_manager
            
            # 10. Data Validator
            logger.info("Initializing data validator...")
            validator = get_validator()
            self._services['validator'] = validator
            
            # 11. Backup Manager
            logger.info("Initializing backup manager...")
            backup_manager = get_backup_manager()
            self._services['backup_manager'] = backup_manager
            
            # 12. Metrics Collector
            logger.info("Initializing metrics collector...")
            metrics_collector = get_metrics_collector()
            self._services['metrics_collector'] = metrics_collector
            
            self._initialized = True
            logger.info("All systems initialized successfully!")
            
        except Exception as e:
            logger.error(f"Error initializing systems: {e}")
            raise
    
    async def dispose_all_systems(self):
        """Звільняє всі системи"""
        if not self._initialized:
            return
        
        try:
            logger.info("Disposing all systems...")
            
            # Звільняємо в зворотному порядку
            await dispose_metrics_collector()
            await dispose_backup_sync()
            await dispose_offline_manager()
            await dispose_services()
            await close_db_pool()
            
            self._services.clear()
            self._initialized = False
            logger.info("All systems disposed successfully!")
            
        except Exception as e:
            logger.error(f"Error disposing systems: {e}")
    
    def get_service(self, service_name: str):
        """Отримує сервіс за назвою"""
        return self._services.get(service_name)
    
    def is_initialized(self) -> bool:
        """Перевіряє чи ініціалізовані системи"""
        return self._initialized

# Глобальний інтегратор
_integrator: Optional[SystemIntegrator] = None

