import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import io
import base64

from src.data import data_manager as dm
from src.utils.config import TRANSACTION_TYPE_EXPENSE, TRANSACTION_TYPE_INCOME, PROPERTY_PURCHASE_CATEGORY, PROPERTY_SALE_CATEGORY

logger = logging.getLogger(__name__)

@dataclass
class PropertyData:
    """Модель даних для майна"""
    name: str
    price: float
    image_b64: Optional[str] = None
    property_id: Optional[int] = None
    purchase_date: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Валідує дані майна"""
        errors = []
        if not self.name or not self.name.strip():
            errors.append("Назва не може бути порожньою")
        if self.price <= 0:
            errors.append("Ціна має бути більше 0")
        if len(self.name.strip()) > 100:
            errors.append("Назва занадто довга (максимум 100 символів)")
        return errors

class PropertyService:
    """Сервіс для роботи з майном"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    @staticmethod
    def compress_image(image_data: bytes, max_size: int = 800, quality: int = 85) -> bytes:
        """Стискає зображення до розумного розміру"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # Конвертуємо в RGB якщо потрібно
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Зменшуємо розмір якщо потрібно
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Зберігаємо з оптимізацією
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Error compressing image: {e}")
            return image_data
    
    @staticmethod
    def image_to_base64(image_data: bytes) -> str:
        """Конвертує зображення в Base64"""
        try:
            compressed_data = PropertyService.compress_image(image_data)
            b64 = base64.b64encode(compressed_data).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            return ""
    
    async def add_property(self, profile_id: int, property_data: PropertyData) -> int:
        """Додає нове майно"""
        try:
            # Валідація
            errors = property_data.validate()
            if errors:
                raise ValueError("; ".join(errors))
            
            # Додаємо майно
            new_id = await self.dm.add_property(
                profile_id=profile_id,
                name=property_data.name.strip(),
                price=property_data.price,
                image_b64=property_data.image_b64 or "",
                purchase_date=property_data.purchase_date
            )
            
            # Створюємо транзакцію покупки
            purchase_desc = f"Покупка майна: {property_data.name}"
            await self.dm.add_transaction(
                profile_id=profile_id,
                trans_type=TRANSACTION_TYPE_EXPENSE,
                category=PROPERTY_PURCHASE_CATEGORY,
                description=purchase_desc,
                amount=property_data.price,
            )
            
            logger.info(f"Property '{property_data.name}' added successfully")
            return new_id
            
        except Exception as e:
            logger.error(f"Error adding property: {e}")
            raise
    
    async def update_property(self, property_id: int, property_data: PropertyData) -> bool:
        """Оновлює існуюче майно"""
        try:
            # Валідація
            errors = property_data.validate()
            if errors:
                raise ValueError("; ".join(errors))
            
            # Отримуємо поточні дані майна
            old_property = await self.dm.get_property(property_id)
            if not old_property:
                raise ValueError("Майно не знайдено")
            
            # Оновлюємо майно
            await self.dm.update_property(
                property_id,
                name=property_data.name.strip(),
                price=property_data.price,
                image_b64=property_data.image_b64 or "",
                purchase_date=property_data.purchase_date
            )
            
            # Оновлюємо транзакцію покупки якщо змінилася ціна
            if old_property['price'] != property_data.price:
                # Знаходимо та оновлюємо транзакцію покупки
                txns = await self.dm.load_transactions(old_property['profile_id'], limit=1000)
                for txn in txns:
                    description = txn.get("description") or ""
                    category = txn.get("category") or ""
                    if (category == PROPERTY_PURCHASE_CATEGORY and 
                        f"Покупка майна: {old_property['name']}" in description):
                        # Оновлюємо транзакцію з новою ціною
                        await self.dm.update_transaction(
                            txn.get("id"),
                            amount=property_data.price,
                            description=f"Покупка майна: {property_data.name.strip()}"
                        )
                        break
            
            logger.info(f"Property '{property_data.name}' updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating property: {e}")
            raise
    
    async def sell_property(self, property_id: int, selling_price: float, notes: str = "") -> bool:
        """Продає майно"""
        try:
            if selling_price <= 0:
                raise ValueError("Ціна продажу має бути більше 0")
            
            # Отримуємо дані майна
            property_info = await self.dm.get_property(property_id)
            if not property_info:
                raise ValueError("Майно не знайдено")
            
            # Продаємо майно
            await self.dm.sell_property(property_id, selling_price)
            
            # Створюємо транзакцію продажу
            sale_desc = notes or f"Продаж майна: {property_info['name']}"
            await self.dm.add_transaction(
                profile_id=property_info['profile_id'],
                trans_type=TRANSACTION_TYPE_INCOME,
                category=PROPERTY_SALE_CATEGORY,
                description=sale_desc,
                amount=selling_price,
            )
            
            logger.info(f"Property '{property_info['name']}' sold successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error selling property: {e}")
            raise
    
    async def delete_property(self, property_id: int) -> bool:
        """Видаляє майно та пов'язані транзакції"""
        try:
            logger.info(f"🔄 Attempting to delete property with ID: {property_id}")
            
            # Отримуємо дані майна
            property_info = await self.dm.get_property(property_id)
            if not property_info:
                logger.error(f"❌ Property with ID {property_id} not found in database")
                raise ValueError("Майно не знайдено")
            
            logger.info(f"✅ Found property: {property_info.get('name', 'Unknown')} (ID: {property_id})")
            
            # Видаляємо пов'язані транзакції
            property_name = property_info['name']
            txns = await self.dm.load_transactions(property_info['profile_id'], limit=1000)
            for txn in txns:
                description = txn.get("description") or ""
                category = txn.get("category") or ""
                # Видаляємо транзакції покупки та продажу для цього майна
                if (category == PROPERTY_PURCHASE_CATEGORY and f"Покупка майна: {property_name}" in description) or \
                   (category == PROPERTY_SALE_CATEGORY and f"Продаж майна: {property_name}" in description):
                    await self.dm.delete_transaction(txn.get("id"))
            
            # Видаляємо майно
            await self.dm.delete_property_permanently(property_id)
            
            logger.info(f"✅ Property '{property_info['name']}' deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting property: {e}")
            raise

    async def restore_property(self, property_id: int) -> bool:
        """Повертає майно з проданого в активне"""
        try:
            logger.info(f"🔄 PropertyService.restore_property called for ID: {property_id}")
            
            # Отримуємо дані майна
            property_info = await self.dm.get_property(property_id)
            if not property_info:
                logger.error(f"❌ Property not found for ID: {property_id}")
                raise ValueError("Майно не знайдено")
            
            logger.info(f"✅ Property found: {property_info.get('name', 'Unknown')} (status: {property_info.get('status')})")
            
            if property_info.get("status") != "sold":
                logger.error(f"❌ Property status is not 'sold': {property_info.get('status')}")
                raise ValueError("Можна повертати тільки продане майно")
            
            # Отримуємо дані про продаж
            selling_price = float(property_info.get("selling_price") or 0)
            sold_timestamp = property_info.get("sold_timestamp")
            logger.info(f"✅ Property was sold for: {selling_price} at {sold_timestamp}")
            
            # Повертаємо майно в активне
            logger.info(f"🔄 Calling data_manager.restore_property for ID: {property_id}")
            await self.dm.restore_property(property_id)
            logger.info("✅ Property status updated in database")
            
            # Видаляємо транзакцію продажу
            property_name = property_info['name']
            logger.info(f"🔄 Looking for sale transaction for property: {property_name}")
            txns = await self.dm.load_transactions(property_info['profile_id'], limit=1000)
            
            sale_transaction_found = False
            for txn in txns:
                description = txn.get("description") or ""
                category = txn.get("category") or ""
                if category == PROPERTY_SALE_CATEGORY and f"Продаж майна: {property_name}" in description:
                    logger.info(f"🔄 Found sale transaction: {txn.get('id')}")
                    await self.dm.delete_transaction(txn.get("id"))
                    sale_transaction_found = True
                    logger.info("✅ Sale transaction deleted")
                    break
            
            if not sale_transaction_found:
                logger.warning("⚠️ No sale transaction found to delete")
            
            logger.info(f"✅ Property '{property_info['name']}' restored successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error restoring property: {e}")
            raise
    
    async def get_properties(self, profile_id: int, status: str = "active") -> List[Dict]:
        """Отримує список майна з пагінацією"""
        try:
            return await self.dm.load_properties(profile_id, status=status)
        except Exception as e:
            logger.error(f"Error loading properties: {e}")
            raise
    
    async def update_properties_order(self, profile_id: int, property_ids: List[int]) -> bool:
        """Оновлює порядок майна"""
        try:
            await self.dm.update_properties_order(profile_id, property_ids)
            return True
        except Exception as e:
            logger.error(f"Error updating properties order: {e}")
            raise
    
    async def update_sold_properties_order(self, profile_id: int, sold_properties: List[Dict]) -> bool:
        """Оновлює порядок проданого майна"""
        try:
            property_ids = [prop.get("id") for prop in sold_properties if prop.get("id")]
            await self.dm.update_sold_properties_order(profile_id, property_ids)
            return True
        except Exception as e:
            logger.error(f"Error updating sold properties order: {e}")
            raise
    
    async def get_property_summary(self, profile_id: int) -> Dict[str, float]:
        """Отримує підсумок по майну"""
        try:
            active_props = await self.dm.load_properties(profile_id, status="active")
            sold_props = await self.dm.load_properties(profile_id, status="sold")
            
            active_total = sum(float(p.get("price") or 0) for p in active_props)
            sold_total = sum(float(p.get("selling_price") or 0) for p in sold_props)
            
            return {
                "active_total": active_total,
                "sold_total": sold_total,
                "active_count": len(active_props),
                "sold_count": len(sold_props)
            }
        except Exception as e:
            logger.error(f"Error getting property summary: {e}")
            raise
