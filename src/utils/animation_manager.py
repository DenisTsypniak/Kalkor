"""
Менеджер анімацій для додатку
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Dict, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)

class AnimationType(Enum):
    """Тип анімації"""
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SLIDE_IN = "slide_in"
    SLIDE_OUT = "slide_out"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    ROTATE = "rotate"
    BOUNCE = "bounce"
    ELASTIC = "elastic"
    CUSTOM = "custom"

class EasingType(Enum):
    """Тип згладжування"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    BOUNCE = "bounce"
    ELASTIC = "elastic"

@dataclass
class AnimationConfig:
    """Конфігурація анімації"""
    duration: float = 0.3  # в секундах
    easing: EasingType = EasingType.EASE_OUT
    delay: float = 0.0
    repeat: int = 1
    reverse: bool = False
    auto_reverse: bool = False

@dataclass
class AnimationKeyframe:
    """Ключовий кадр анімації"""
    time: float  # 0.0 - 1.0
    properties: Dict[str, Any]

class AnimationManager:
    """Менеджер анімацій"""
    
    def __init__(self):
        self._active_animations: Dict[str, asyncio.Task] = {}
        self._animation_queue: List[Tuple[str, Callable, AnimationConfig]] = []
        self._is_processing_queue: bool = False
    
    def fade_in(
        self,
        control: Any,
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_OUT,
        delay: float = 0.0
    ) -> str:
        """Анімація появи"""
        animation_id = f"fade_in_{id(control)}_{asyncio.get_event_loop().time()}"
        
        config = AnimationConfig(duration=duration, easing=easing, delay=delay)
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Встановлюємо початкові значення
            control.opacity = 0.0
            control.visible = True
            if hasattr(control, 'page') and control.page:
                control.update()
            
            # Анімуємо
            await self._animate_property(
                control, 'opacity', 0.0, 1.0, duration, easing
            )
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def fade_out(
        self,
        control: Any,
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_IN,
        delay: float = 0.0
    ) -> str:
        """Анімація зникнення"""
        animation_id = f"fade_out_{id(control)}_{asyncio.get_event_loop().time()}"
        
        config = AnimationConfig(duration=duration, easing=easing, delay=delay)
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Анімуємо
            await self._animate_property(
                control, 'opacity', 1.0, 0.0, duration, easing
            )
            
            # Приховуємо
            control.visible = False
            if hasattr(control, 'page') and control.page:
                control.update()
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def slide_in(
        self,
        control: Any,
        direction: str = "right",
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_OUT,
        delay: float = 0.0
    ) -> str:
        """Анімація висування"""
        animation_id = f"slide_in_{id(control)}_{asyncio.get_event_loop().time()}"
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Встановлюємо початкові значення
            if direction == "right":
                control.left = -control.width if hasattr(control, 'width') else -200
            elif direction == "left":
                control.left = control.width if hasattr(control, 'width') else 200
            elif direction == "up":
                control.top = -control.height if hasattr(control, 'height') else -200
            elif direction == "down":
                control.top = control.height if hasattr(control, 'height') else 200
            
            control.visible = True
            if hasattr(control, 'page') and control.page:
                control.update()
            
            # Анімуємо до початкової позиції
            if direction in ["right", "left"]:
                await self._animate_property(
                    control, 'left', control.left, 0, duration, easing
                )
            else:
                await self._animate_property(
                    control, 'top', control.top, 0, duration, easing
                )
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def slide_out(
        self,
        control: Any,
        direction: str = "right",
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_IN,
        delay: float = 0.0
    ) -> str:
        """Анімація засування"""
        animation_id = f"slide_out_{id(control)}_{asyncio.get_event_loop().time()}"
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Зберігаємо поточну позицію
            start_pos = control.left if direction in ["right", "left"] else control.top
            
            # Анімуємо до кінцевої позиції
            if direction == "right":
                end_pos = control.width if hasattr(control, 'width') else 200
                await self._animate_property(
                    control, 'left', start_pos, end_pos, duration, easing
                )
            elif direction == "left":
                end_pos = -control.width if hasattr(control, 'width') else -200
                await self._animate_property(
                    control, 'left', start_pos, end_pos, duration, easing
                )
            elif direction == "up":
                end_pos = -control.height if hasattr(control, 'height') else -200
                await self._animate_property(
                    control, 'top', start_pos, end_pos, duration, easing
                )
            elif direction == "down":
                end_pos = control.height if hasattr(control, 'height') else 200
                await self._animate_property(
                    control, 'top', start_pos, end_pos, duration, easing
                )
            
            # Приховуємо
            control.visible = False
            if hasattr(control, 'page') and control.page:
                control.update()
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def scale_in(
        self,
        control: Any,
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_OUT,
        delay: float = 0.0
    ) -> str:
        """Анімація масштабування (збільшення)"""
        animation_id = f"scale_in_{id(control)}_{asyncio.get_event_loop().time()}"
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Встановлюємо початкові значення
            control.scale = 0.0
            control.visible = True
            if hasattr(control, 'page') and control.page:
                control.update()
            
            # Анімуємо
            await self._animate_property(
                control, 'scale', 0.0, 1.0, duration, easing
            )
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def scale_out(
        self,
        control: Any,
        duration: float = 0.3,
        easing: EasingType = EasingType.EASE_IN,
        delay: float = 0.0
    ) -> str:
        """Анімація масштабування (зменшення)"""
        animation_id = f"scale_out_{id(control)}_{asyncio.get_event_loop().time()}"
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Анімуємо
            await self._animate_property(
                control, 'scale', 1.0, 0.0, duration, easing
            )
            
            # Приховуємо
            control.visible = False
            if hasattr(control, 'page') and control.page:
                control.update()
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def bounce(
        self,
        control: Any,
        duration: float = 0.6,
        delay: float = 0.0
    ) -> str:
        """Анімація відскоку"""
        animation_id = f"bounce_{id(control)}_{asyncio.get_event_loop().time()}"
        
        async def animate():
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Встановлюємо початкові значення
            control.scale = 0.0
            control.visible = True
            if hasattr(control, 'page') and control.page:
                control.update()
            
            # Анімуємо з bounce ефектом
            await self._animate_property(
                control, 'scale', 0.0, 1.0, duration, EasingType.BOUNCE
            )
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def sequence(
        self,
        animations: List[Tuple[Callable, Dict[str, Any]]],
        delay_between: float = 0.1
    ) -> str:
        """Виконує послідовність анімацій"""
        animation_id = f"sequence_{asyncio.get_event_loop().time()}"
        
        async def animate():
            for i, (animation_func, params) in enumerate(animations):
                if i > 0 and delay_between > 0:
                    await asyncio.sleep(delay_between)
                
                await animation_func(**params)
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    def parallel(
        self,
        animations: List[Tuple[Callable, Dict[str, Any]]]
    ) -> str:
        """Виконує анімації паралельно"""
        animation_id = f"parallel_{asyncio.get_event_loop().time()}"
        
        async def animate():
            tasks = []
            for animation_func, params in animations:
                task = asyncio.create_task(animation_func(**params))
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        self._active_animations[animation_id] = asyncio.create_task(animate())
        return animation_id
    
    async def _animate_property(
        self,
        control: Any,
        property_name: str,
        start_value: float,
        end_value: float,
        duration: float,
        easing: EasingType
    ):
        """Анімує властивість"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            if elapsed >= duration:
                setattr(control, property_name, end_value)
                if hasattr(control, 'page') and control.page:
                    control.update()
                break
            
            # Розраховуємо прогрес (0.0 - 1.0)
            progress = elapsed / duration
            
            # Застосовуємо easing
            eased_progress = self._apply_easing(progress, easing)
            
            # Розраховуємо поточне значення
            current_value = start_value + (end_value - start_value) * eased_progress
            
            # Встановлюємо значення
            setattr(control, property_name, current_value)
            
            if hasattr(control, 'page') and control.page:
                control.update()
            
            await asyncio.sleep(1/60)  # 60 FPS
    
    def _apply_easing(self, progress: float, easing: EasingType) -> float:
        """Застосовує easing функцію"""
        if easing == EasingType.LINEAR:
            return progress
        elif easing == EasingType.EASE_IN:
            return progress * progress
        elif easing == EasingType.EASE_OUT:
            return 1 - (1 - progress) * (1 - progress)
        elif easing == EasingType.EASE_IN_OUT:
            if progress < 0.5:
                return 2 * progress * progress
            else:
                return 1 - 2 * (1 - progress) * (1 - progress)
        elif easing == EasingType.EASE_IN_CUBIC:
            return progress * progress * progress
        elif easing == EasingType.EASE_OUT_CUBIC:
            return 1 - (1 - progress) ** 3
        elif easing == EasingType.EASE_IN_OUT_CUBIC:
            if progress < 0.5:
                return 4 * progress * progress * progress
            else:
                return 1 - 4 * (1 - progress) ** 3
        elif easing == EasingType.BOUNCE:
            return self._bounce_easing(progress)
        elif easing == EasingType.ELASTIC:
            return self._elastic_easing(progress)
        else:
            return progress
    
    def _bounce_easing(self, progress: float) -> float:
        """Bounce easing функція"""
        if progress < 1/2.75:
            return 7.5625 * progress * progress
        elif progress < 2/2.75:
            progress -= 1.5/2.75
            return 7.5625 * progress * progress + 0.75
        elif progress < 2.5/2.75:
            progress -= 2.25/2.75
            return 7.5625 * progress * progress + 0.9375
        else:
            progress -= 2.625/2.75
            return 7.5625 * progress * progress + 0.984375
    
    def _elastic_easing(self, progress: float) -> float:
        """Elastic easing функція"""
        if progress == 0 or progress == 1:
            return progress
        
        c4 = (2 * math.pi) / 3
        
        if progress < 0.5:
            return -(2 ** (20 * progress - 10)) * math.sin((20 * progress - 11.125) * c4) / 2
        else:
            return (2 ** (-20 * progress + 10)) * math.sin((20 * progress - 11.125) * c4) / 2 + 1
    
    def stop_animation(self, animation_id: str):
        """Зупиняє анімацію"""
        if animation_id in self._active_animations:
            self._active_animations[animation_id].cancel()
            del self._active_animations[animation_id]
    
    def stop_all_animations(self):
        """Зупиняє всі анімації"""
        for animation_id in list(self._active_animations.keys()):
            self.stop_animation(animation_id)
    
    def is_animating(self, animation_id: str) -> bool:
        """Перевіряє чи анімується"""
        return animation_id in self._active_animations
    
    def get_active_animations(self) -> List[str]:
        """Повертає список активних анімацій"""
        return list(self._active_animations.keys())

# Утилітарні функції
def create_fade_animation(control: Any, fade_in: bool = True, duration: float = 0.3) -> str:
    """Створює fade анімацію"""
    manager = get_animation_manager()
    if fade_in:
        return manager.fade_in(control, duration)
    else:
        return manager.fade_out(control, duration)

def create_slide_animation(
    control: Any,
    direction: str = "right",
    slide_in: bool = True,
    duration: float = 0.3
) -> str:
    """Створює slide анімацію"""
    manager = get_animation_manager()
    if slide_in:
        return manager.slide_in(control, direction, duration)
    else:
        return manager.slide_out(control, direction, duration)

def create_scale_animation(control: Any, scale_in: bool = True, duration: float = 0.3) -> str:
    """Створює scale анімацію"""
    manager = get_animation_manager()
    if scale_in:
        return manager.scale_in(control, duration)
    else:
        return manager.scale_out(control, duration)

# Глобальний екземпляр
_animation_manager: Optional[AnimationManager] = None

def get_animation_manager() -> AnimationManager:
    """Отримує глобальний менеджер анімацій"""
    global _animation_manager
    if _animation_manager is None:
        _animation_manager = AnimationManager()
    return _animation_manager
