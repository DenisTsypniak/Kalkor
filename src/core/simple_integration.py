"""
Спрощена інтеграція систем оптимізації
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SimpleSystemIntegrator:
    """Спрощений інтегратор систем"""
    
    def __init__(self):
        self._initialized = False
        self._services = {}
    
    async def initialize_all_systems(self):
        """Ініціалізує всі системи"""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing optimization systems...")
            
            # 1. Database Pool
            try:
                from src.core.database_pool import get_db_pool
                db_pool = await get_db_pool()
                self._services['db_pool'] = db_pool
                logger.info("✅ Database pool initialized")
            except Exception as e:
                logger.warning(f"⚠️ Database pool failed: {e}")
            
            # 2. Animation Manager
            try:
                from src.utils.animation_manager import get_animation_manager
                animation_manager = get_animation_manager()
                self._services['animation_manager'] = animation_manager
                logger.info("✅ Animation manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ Animation manager failed: {e}")
            
            # 3. Theme Manager
            try:
                from src.themes.theme_manager import get_theme_manager
                theme_manager = get_theme_manager()
                self._services['theme_manager'] = theme_manager
                logger.info("✅ Theme manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ Theme manager failed: {e}")
            
            # 4. Performance Optimizer
            try:
                from src.utils.performance.optimizer import PerformanceOptimizer
                performance_optimizer = PerformanceOptimizer()
                self._services['performance_optimizer'] = performance_optimizer
                logger.info("✅ Performance optimizer initialized")
            except Exception as e:
                logger.warning(f"⚠️ Performance optimizer failed: {e}")
            
            # 5. Analytics Engine
            try:
                from src.utils.analytics_engine import AnalyticsEngine
                analytics_engine = AnalyticsEngine()
                self._services['analytics_engine'] = analytics_engine
                logger.info("✅ Analytics engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Analytics engine failed: {e}")
            
            # 6. Fallback Database Manager видалено, оскільки не використовується
            
            # 4. Image Loader
            try:
                from src.utils.lazy_image_loader import get_image_loader
                image_loader = get_image_loader()
                self._services['image_loader'] = image_loader
                logger.info("✅ Image loader initialized")
            except Exception as e:
                logger.warning(f"⚠️ Image loader failed: {e}")
            
            # 5. Metrics Collector
            try:
                from src.utils.metrics_collector import get_metrics_collector
                metrics_collector = get_metrics_collector()
                self._services['metrics_collector'] = metrics_collector
                logger.info("✅ Metrics collector initialized")
            except Exception as e:
                logger.warning(f"⚠️ Metrics collector failed: {e}")
            
            # 6. Error Handler
            try:
                from src.utils.error_handler import get_error_handler
                error_handler = get_error_handler()
                self._services['error_handler'] = error_handler
                logger.info("✅ Error handler initialized")
            except Exception as e:
                logger.warning(f"⚠️ Error handler failed: {e}")
            
            # 7. UI Responsiveness
            try:
                from src.utils.ui_responsiveness import get_ui_responsiveness_manager
                ui_manager = get_ui_responsiveness_manager()
                self._services['ui_manager'] = ui_manager
                logger.info("✅ UI responsiveness manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ UI responsiveness manager failed: {e}")
            
            # 8. Simple Validator
            try:
                from src.utils.validators import DataValidator
                validator = DataValidator()
                self._services['validator'] = validator
                logger.info("✅ Simple validator initialized")
            except Exception as e:
                logger.warning(f"⚠️ Simple validator failed: {e}")
            
            self._initialized = True
            logger.info("🎉 All available systems initialized!")
            
        except Exception as e:
            logger.error(f"❌ Error initializing systems: {e}")
            # Не викидаємо помилку, щоб додаток міг працювати без оптимізацій
    
    async def dispose_all_systems(self):
        """Звільняє всі системи"""
        if not self._initialized:
            return
        
        try:
            logger.info("Disposing optimization systems...")
            
            # Звільняємо в зворотному порядку
            if 'metrics_collector' in self._services:
                try:
                    from src.utils.metrics_collector import dispose_metrics_collector
                    await dispose_metrics_collector()
                except Exception as e:
                    logger.warning(f"Error disposing metrics collector: {e}")
            
            if 'db_pool' in self._services:
                try:
                    from src.core.database_pool import close_db_pool
                    await close_db_pool()
                except Exception as e:
                    logger.warning(f"Error disposing database pool: {e}")
            
            self._services.clear()
            self._initialized = False
            logger.info("✅ All systems disposed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error disposing systems: {e}")
    
    def get_service(self, service_name: str):
        """Отримує сервіс за назвою"""
        return self._services.get(service_name)
    
    def is_initialized(self) -> bool:
        """Перевіряє чи ініціалізовані системи"""
        return self._initialized
    
    def get_available_services(self) -> list:
        """Повертає список доступних сервісів"""
        return list(self._services.keys())

# Глобальний інтегратор
_integrator: Optional[SimpleSystemIntegrator] = None

def get_integrator() -> SimpleSystemIntegrator:
    """Отримує глобальний інтегратор"""
    global _integrator
    if _integrator is None:
        _integrator = SimpleSystemIntegrator()
    return _integrator

async def initialize_optimization_systems():
    """Ініціалізує всі системи оптимізації"""
    integrator = get_integrator()
    await integrator.initialize_all_systems()

async def dispose_optimization_systems():
    """Звільняє всі системи оптимізації"""
    integrator = get_integrator()
    await integrator.dispose_all_systems()
