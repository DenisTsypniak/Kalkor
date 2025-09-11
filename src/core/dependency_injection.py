"""
Система Dependency Injection для додатку
"""

import asyncio
import logging
from typing import Any, Type, TypeVar, Dict, Callable, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceLifetime(Enum):
    """Тривалість життя сервісу"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

@dataclass
class ServiceDescriptor:
    """Опис сервісу"""
    interface: Type
    implementation: Type
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: list[Type] = None

class IServiceProvider(ABC):
    """Інтерфейс провайдера сервісів"""
    
    @abstractmethod
    def get_service(self, service_type: Type[T]) -> T:
        """Отримує сервіс за типом"""
        pass
    
    @abstractmethod
    def get_required_service(self, service_type: Type[T]) -> T:
        """Отримує обов'язковий сервіс"""
        pass
    
    @abstractmethod
    def get_services(self, service_type: Type[T]) -> list[T]:
        """Отримує всі сервіси за типом"""
        pass

class ServiceCollection:
    """Колекція сервісів для реєстрації"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
    
    def add_singleton(self, interface: Type[T], implementation: Type[T]) -> 'ServiceCollection':
        """Додає singleton сервіс"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON
        )
        return self
    
    def add_transient(self, interface: Type[T], implementation: Type[T]) -> 'ServiceCollection':
        """Додає transient сервіс"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.TRANSIENT
        )
        return self
    
    def add_scoped(self, interface: Type[T], implementation: Type[T]) -> 'ServiceCollection':
        """Додає scoped сервіс"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.SCOPED
        )
        return self
    
    def add_singleton_factory(self, interface: Type[T], factory: Callable[[], T]) -> 'ServiceCollection':
        """Додає singleton сервіс з фабрикою"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=None,
            factory=factory,
            lifetime=ServiceLifetime.SINGLETON
        )
        return self
    
    def add_transient_factory(self, interface: Type[T], factory: Callable[[], T]) -> 'ServiceCollection':
        """Додає transient сервіс з фабрикою"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=None,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT
        )
        return self
    
    def add_instance(self, interface: Type[T], instance: T) -> 'ServiceCollection':
        """Додає готовий екземпляр"""
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=None,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON
        )
        return self
    
    def build_service_provider(self) -> 'ServiceProvider':
        """Створює провайдер сервісів"""
        return ServiceProvider(self._services.copy())

class ServiceProvider(IServiceProvider):
    """Провайдер сервісів"""
    
    def __init__(self, services: Dict[Type, ServiceDescriptor]):
        self._services = services
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self._lock = asyncio.Lock()
    
    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """Отримує сервіс за типом"""
        try:
            return self._create_instance(service_type)
        except Exception as e:
            logger.error(f"Error getting service {service_type.__name__}: {e}")
            return None
    
    def get_required_service(self, service_type: Type[T]) -> T:
        """Отримує обов'язковий сервіс"""
        service = self.get_service(service_type)
        if service is None:
            raise ValueError(f"Required service {service_type.__name__} not found")
        return service
    
    def get_services(self, service_type: Type[T]) -> list[T]:
        """Отримує всі сервіси за типом"""
        services = []
        for descriptor in self._services.values():
            if issubclass(descriptor.interface, service_type):
                service = self.get_service(descriptor.interface)
                if service:
                    services.append(service)
        return services
    
    def _create_instance(self, service_type: Type[T]) -> T:
        """Створює екземпляр сервісу"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} not registered")
        
        descriptor = self._services[service_type]
        
        # Перевіряємо singleton
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
        
        # Перевіряємо scoped
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]
        
        # Створюємо новий екземпляр
        instance = self._instantiate_service(descriptor)
        
        # Зберігаємо залежно від lifetime
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            self._singletons[service_type] = instance
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            self._scoped_instances[service_type] = instance
        
        return instance
    
    def _instantiate_service(self, descriptor: ServiceDescriptor) -> Any:
        """Створює екземпляр сервісу"""
        # Якщо є готовий екземпляр
        if descriptor.instance is not None:
            return descriptor.instance
        
        # Якщо є фабрика
        if descriptor.factory is not None:
            return descriptor.factory()
        
        # Якщо є реалізація
        if descriptor.implementation is not None:
            return self._create_from_implementation(descriptor.implementation)
        
        raise ValueError(f"Cannot create instance for {descriptor.interface.__name__}")
    
    def _create_from_implementation(self, implementation: Type) -> Any:
        """Створює екземпляр з реалізації"""
        try:
            # Спробуємо створити без параметрів
            return implementation()
        except TypeError:
            # Якщо потрібні параметри, спробуємо dependency injection
            return self._create_with_dependencies(implementation)
    
    def _create_with_dependencies(self, implementation: Type) -> Any:
        """Створює екземпляр з залежностями"""
        import inspect
        
        # Отримуємо сигнатуру конструктора
        sig = inspect.signature(implementation.__init__)
        dependencies = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            if param.annotation != inspect.Parameter.empty:
                dependency = self.get_service(param.annotation)
                if dependency is None:
                    raise ValueError(f"Cannot resolve dependency {param.annotation.__name__} for {implementation.__name__}")
                dependencies.append(dependency)
            else:
                # Якщо немає анотації типу, спробуємо знайти за ім'ям
                raise ValueError(f"Parameter {param_name} in {implementation.__name__} has no type annotation")
        
        return implementation(*dependencies)
    
    async def dispose(self):
        """Звільняє ресурси"""
        async with self._lock:
            # Викликаємо dispose для всіх singleton
            for instance in self._singletons.values():
                if hasattr(instance, 'dispose'):
                    if asyncio.iscoroutinefunction(instance.dispose):
                        await instance.dispose()
                    else:
                        instance.dispose()
            
            # Очищаємо кеші
            self._singletons.clear()
            self._scoped_instances.clear()

# Декоратори для dependency injection
def injectable(cls: Type[T]) -> Type[T]:
    """Декоратор для позначення класу як injectable"""
    cls._is_injectable = True
    return cls

def singleton(cls: Type[T]) -> Type[T]:
    """Декоратор для singleton сервісу"""
    cls._is_singleton = True
    return cls

def scoped(cls: Type[T]) -> Type[T]:
    """Декоратор для scoped сервісу"""
    cls._is_scoped = True
    return cls

# Глобальний контейнер
_service_provider: Optional[ServiceProvider] = None

def configure_services() -> ServiceCollection:
    """Налаштовує сервіси додатку"""
    services = ServiceCollection()
    
    # Реєструємо основні сервіси
    from src.core.database_pool import DatabasePool, get_db_pool
    from src.utils.lazy_image_loader import LazyImageLoader, get_image_loader
    from src.utils.ui_responsiveness import UIResponsivenessManager, get_ui_responsiveness_manager
    from src.utils.localization import LocalizationManager
    
    # Database
    services.add_singleton_factory(DatabasePool, get_db_pool)
    
    # Image loader
    services.add_singleton_factory(LazyImageLoader, get_image_loader)
    
    # UI responsiveness
    services.add_singleton_factory(UIResponsivenessManager, get_ui_responsiveness_manager)
    
    # Cache manager
    services.add_singleton(CacheManager, CacheManager)
    
    # Localization
    services.add_singleton(LocalizationManager, LocalizationManager)
    
    return services

def get_service_provider() -> ServiceProvider:
    """Отримує глобальний провайдер сервісів"""
    global _service_provider
    if _service_provider is None:
        services = configure_services()
        _service_provider = services.build_service_provider()
    return _service_provider

def get_service(service_type: Type[T]) -> T:
    """Отримує сервіс за типом"""
    return get_service_provider().get_required_service(service_type)

async def dispose_services():
    """Звільняє всі сервіси"""
    global _service_provider
    if _service_provider:
        await _service_provider.dispose()
        _service_provider = None
