"""
Lazy loading для зображень з кешуванням та оптимізацією
"""

import asyncio
import base64
import logging
from typing import Dict, Set, Optional, Callable
from PIL import Image
import io
import hashlib
import flet as ft

logger = logging.getLogger(__name__)

class LazyImageLoader:
    """Менеджер для lazy loading зображень"""
    
    def __init__(self, max_cache_size: int = 100):
        self._cache: Dict[str, str] = {}  # hash -> base64
        self._loading: Set[str] = set()  # hash -> loading state
        self._callbacks: Dict[str, list[Callable]] = {}  # hash -> callbacks
        self._max_cache_size = max_cache_size
        self._lock = asyncio.Lock()
    
    def _get_image_hash(self, image_b64: str) -> str:
        """Генерує хеш для зображення"""
        return hashlib.md5(image_b64.encode()).hexdigest()[:16]
    
    async def load_image_async(
        self, 
        image_b64: str, 
        container: 'ft.Container',
        placeholder: Optional[str] = None,
        on_loaded: Optional[Callable] = None
    ):
        """Асинхронно завантажує зображення"""
        if not image_b64:
            return
        
        image_hash = self._get_image_hash(image_b64)
        
        # Перевіряємо кеш
        if image_hash in self._cache:
            await self._apply_image_to_container(container, self._cache[image_hash])
            if on_loaded:
                on_loaded()
            return
        
        # Якщо вже завантажується, додаємо callback
        if image_hash in self._loading:
            if on_loaded:
                if image_hash not in self._callbacks:
                    self._callbacks[image_hash] = []
                self._callbacks[image_hash].append(on_loaded)
            return
        
        # Показуємо placeholder
        if placeholder:
            await self._apply_placeholder(container, placeholder)
        
        # Починаємо завантаження
        self._loading.add(image_hash)
        asyncio.create_task(self._load_and_cache_image(image_b64, image_hash, container, on_loaded))
    
    async def _load_and_cache_image(
        self, 
        image_b64: str, 
        image_hash: str, 
        container: 'ft.Container',
        on_loaded: Optional[Callable]
    ):
        """Завантажує та кешує зображення"""
        try:
            # Обробляємо зображення в фоні
            processed_b64 = await self._process_image_async(image_b64)
            
            async with self._lock:
                # Зберігаємо в кеш
                if len(self._cache) >= self._max_cache_size:
                    # Видаляємо найстаріший елемент
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                
                self._cache[image_hash] = processed_b64
                self._loading.discard(image_hash)
            
            # Застосовуємо зображення
            await self._apply_image_to_container(container, processed_b64)
            
            # Викликаємо callbacks
            if image_hash in self._callbacks:
                for callback in self._callbacks[image_hash]:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in image load callback: {e}")
                del self._callbacks[image_hash]
            
            if on_loaded:
                on_loaded()
                
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            self._loading.discard(image_hash)
            if image_hash in self._callbacks:
                del self._callbacks[image_hash]
    
    async def _process_image_async(self, image_b64: str) -> str:
        """Обробляє зображення в асинхронному режимі"""
        def process_image():
            try:
                # Видаляємо data:image/...;base64, префікс
                if ',' in image_b64:
                    image_b64 = image_b64.split(',')[1]
                
                # Декодуємо base64
                image_data = base64.b64decode(image_b64)
                
                # Відкриваємо зображення
                img = Image.open(io.BytesIO(image_data))
                
                # Конвертуємо в RGB якщо потрібно
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Оптимізуємо розмір
                max_size = 800
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Зберігаємо з оптимізацією
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                
                # Повертаємо base64
                processed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return f"data:image/jpeg;base64,{processed_b64}"
                
            except Exception as e:
                logger.error(f"Error processing image: {e}")
                return image_b64  # Повертаємо оригінал при помилці
        
        # Виконуємо в thread pool для неблокуючої обробки
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, process_image)
    
    async def _apply_image_to_container(self, container: 'ft.Container', image_b64: str):
        """Застосовує зображення до контейнера"""
        try:
            if hasattr(container, 'content') and hasattr(container.content, 'src_base64'):
                container.content.src_base64 = image_b64.split(',')[1] if ',' in image_b64 else image_b64
                if hasattr(container, 'page') and container.page:
                    container.update()
        except Exception as e:
            logger.error(f"Error applying image to container: {e}")
    
    async def _apply_placeholder(self, container: 'ft.Container', placeholder: str):
        """Застосовує placeholder до контейнера"""
        try:
            if hasattr(container, 'content'):
                if isinstance(container.content, ft.Image):
                    container.content.src = placeholder
                elif hasattr(container.content, 'src'):
                    container.content.src = placeholder
                if hasattr(container, 'page') and container.page:
                    container.update()
        except Exception as e:
            logger.error(f"Error applying placeholder: {e}")
    
    def preload_images(self, image_b64_list: list[str]):
        """Попередньо завантажує список зображень"""
        for image_b64 in image_b64_list:
            if image_b64:
                image_hash = self._get_image_hash(image_b64)
                if image_hash not in self._cache and image_hash not in self._loading:
                    asyncio.create_task(self._preload_single_image(image_b64, image_hash))
    
    async def _preload_single_image(self, image_b64: str, image_hash: str):
        """Попередньо завантажує одне зображення"""
        try:
            processed_b64 = await self._process_image_async(image_b64)
            async with self._lock:
                if len(self._cache) < self._max_cache_size:
                    self._cache[image_hash] = processed_b64
        except Exception as e:
            logger.error(f"Error preloading image: {e}")
    
    def clear_cache(self):
        """Очищає кеш зображень"""
        self._cache.clear()
        self._loading.clear()
        self._callbacks.clear()
        logger.info("Image cache cleared")
    
    def get_cache_stats(self) -> dict:
        """Повертає статистику кешу"""
        return {
            'cached_images': len(self._cache),
            'loading_images': len(self._loading),
            'pending_callbacks': sum(len(callbacks) for callbacks in self._callbacks.values()),
            'cache_size_mb': sum(len(b64) for b64 in self._cache.values()) / (1024 * 1024)
        }

# Глобальний екземпляр
_image_loader = LazyImageLoader()

def get_image_loader() -> LazyImageLoader:
    """Отримує глобальний екземпляр lazy image loader"""
    return _image_loader
