# --- START OF FILE src/data/data_manager.py ---
import logging
from src.utils.config import TRANSACTION_TYPE_INCOME, TRANSACTION_TYPE_EXPENSE, INITIAL_BALANCE_CATEGORY, CORRECTION_CATEGORY, PROPERTY_SALE_CATEGORY, PROPERTY_PURCHASE_CATEGORY
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

import aiosqlite as sqlite3
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# Повертаємо базові системи оптимізації
try:
    from src.core.database_pool import get_db_pool
    from src.utils.metrics_collector import track_operation
    from src.utils.error_handler import handle_errors, ErrorCategory, ErrorSeverity
    from src.utils.performance.optimizer import PerformanceOptimizer
    OPTIMIZATION_ENABLED = True
    print("✅ Database pool system enabled")
except ImportError as e:
    print(f"⚠️ Database pool not available: {e}")
    OPTIMIZATION_ENABLED = False

# Ініціалізуємо Performance Optimizer
_performance_optimizer = None

def get_performance_optimizer():
    """Отримує екземпляр Performance Optimizer"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer

# Fallback Database Manager видалено, оскільки не використовується

logger = logging.getLogger(__name__)

# Розміщення файлу бази даних у кореневій директорії проекту
DB_FILE = "tracker.db"


@asynccontextmanager
async def get_db_connection():
    """
    Створює, налаштовує та надає асинхронне з'єднання з БД
    як контекстний менеджер, що гарантує його закриття.
    """
    if OPTIMIZATION_ENABLED:
        # Використовуємо connection pooling
        try:
            db_pool = await get_db_pool()
            async with db_pool.get_connection_context() as conn:
                yield conn
            return
        except Exception as e:
            logger.warning(f"Connection pool failed, falling back to direct connection: {e}")
    
    # Fallback до прямого з'єднання
    conn = await sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    await conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
    finally:
        await conn.close()


async def init_db():
    """
    Ініціалізує структуру бази даних.
    Створює всі необхідні таблиці, індекси та виконує міграцію.
    """
    async with get_db_connection() as conn:
        # --- Створення таблиць ---
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                avatar_b64 TEXT
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                color TEXT,
                FOREIGN KEY (profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
                UNIQUE (profile_id, name, type)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT,
                description TEXT,
                amount REAL NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles (id) ON DELETE CASCADE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                image_b64 TEXT,
                status TEXT DEFAULT 'active',
                display_order INTEGER DEFAULT 0,
                sold_timestamp TEXT,
                selling_price REAL,
                FOREIGN KEY (profile_id) REFERENCES profiles (id) ON DELETE CASCADE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # --- Створення індексів для оптимізації ---
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_profile_date 
            ON transactions(profile_id, timestamp)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_profile_type 
            ON transactions(profile_id, type)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_properties_profile_status 
            ON properties(profile_id, status)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_properties_order 
            ON properties(profile_id, display_order)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_categories_profile_type 
            ON categories(profile_id, type)
        ''')
        
        # Додаткові індекси для оптимізації
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_profiles_name 
            ON profiles(name)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_category 
            ON transactions(profile_id, category)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_properties_created 
            ON properties(profile_id, created_timestamp)
        ''')
        
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_app_settings_key 
            ON app_settings(key)
        ''')

        # --- Міграція: додавання нових полів, якщо їх немає ---
        cursor = await conn.execute("PRAGMA table_info(properties)")
        prop_columns = [row['name'] for row in await cursor.fetchall()]

        if 'status' not in prop_columns:
            await conn.execute("ALTER TABLE properties ADD COLUMN status TEXT DEFAULT 'active'")
        if 'display_order' not in prop_columns:
            await conn.execute("ALTER TABLE properties ADD COLUMN display_order INTEGER DEFAULT 0")
            await conn.execute("UPDATE properties SET display_order = id WHERE display_order IS NULL")
        if 'sold_timestamp' not in prop_columns:
            await conn.execute("ALTER TABLE properties ADD COLUMN sold_timestamp TEXT")
        if 'selling_price' not in prop_columns:
            await conn.execute("ALTER TABLE properties ADD COLUMN selling_price REAL")
        if 'created_timestamp' not in prop_columns:
            await conn.execute("ALTER TABLE properties ADD COLUMN created_timestamp TEXT")

        await conn.commit()


async def save_setting(key: str, value: str):
    async with get_db_connection() as conn:
        await conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
        await conn.commit()


async def get_setting(key: str, default: str | None = None) -> str | None:
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row['value'] if row else default


async def get_profile_list() -> list[dict]:
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT id, name, avatar_b64 FROM profiles ORDER BY name")
        profiles = await cursor.fetchall()
        return [dict(p) for p in profiles]


async def get_profile_id(profile_name: str) -> int | None:
    if not profile_name: return None
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT id FROM profiles WHERE name = ?", (profile_name,))
        profile = await cursor.fetchone()
        return profile['id'] if profile else None


@track_operation("create_profile") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.HIGH, "Помилка створення профілю") if OPTIMIZATION_ENABLED else lambda x: x
async def create_profile(profile_name: str, avatar_b64: str | None = None) -> dict:
    async with get_db_connection() as conn:
        cursor = await conn.execute("INSERT INTO profiles (name, avatar_b64) VALUES (?, ?)", (profile_name, avatar_b64))
        await conn.commit()
        profile_id = cursor.lastrowid
        return {"id": profile_id, "name": profile_name, "avatar_b64": avatar_b64}


@track_operation("update_profile") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.HIGH, "Помилка оновлення профілю") if OPTIMIZATION_ENABLED else lambda x: x
async def update_profile(profile_id: int, new_name: str, new_avatar_b64: str | None):
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT avatar_b64 FROM profiles WHERE id = ?", (profile_id,))
        row = await cursor.fetchone()
        current_avatar = row['avatar_b64'] if row else None
        avatar_to_save = new_avatar_b64 if new_avatar_b64 is not None else current_avatar
        await conn.execute("UPDATE profiles SET name = ?, avatar_b64 = ? WHERE id = ?", (new_name, avatar_to_save, profile_id))
        await conn.commit()


@track_operation("delete_profile") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.HIGH, "Помилка видалення профілю") if OPTIMIZATION_ENABLED else lambda x: x
async def delete_profile(profile_id: int):
    if not profile_id: return
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        await conn.commit()


# --- ЗМІНЕНО: Повна реалізація фільтрації та пагінації ---
@track_operation("load_transactions") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.MEDIUM, "Помилка завантаження транзакцій") if OPTIMIZATION_ENABLED else lambda x: x
@get_performance_optimizer().measure_performance("load_transactions")
async def load_transactions(profile_id: int, start_date: datetime = None, end_date: datetime = None, limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Завантажує транзакції з пагінацією та фільтрацією.
    За замовчуванням повертає 50 записів для оптимізації продуктивності.
    """
    if not profile_id:
        return []

    base_query = "SELECT id, timestamp, type, category, description, amount FROM transactions WHERE profile_id = ?"
    params = [profile_id]

    if start_date:
        base_query += " AND timestamp >= ?"
        params.append(start_date.isoformat())
    if end_date:
        base_query += " AND timestamp <= ?"
        params.append(end_date.isoformat())

    base_query += " ORDER BY timestamp DESC"

    if limit is not None:
        base_query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    async with get_db_connection() as conn:
        cursor = await conn.execute(base_query, tuple(params))
        transactions = await cursor.fetchall()
        return [dict(row) for row in transactions]

async def get_transactions_count(profile_id: int, start_date: datetime = None, end_date: datetime = None) -> int:
    """Повертає загальну кількість транзакцій для пагінації"""
    if not profile_id:
        return 0

    base_query = "SELECT COUNT(*) as count FROM transactions WHERE profile_id = ?"
    params = [profile_id]

    if start_date:
        base_query += " AND timestamp >= ?"
        params.append(start_date.isoformat())
    if end_date:
        base_query += " AND timestamp <= ?"
        params.append(end_date.isoformat())

    async with get_db_connection() as conn:
        cursor = await conn.execute(base_query, tuple(params))
        row = await cursor.fetchone()
        return row['count'] if row else 0


# --- ДОДАНО: Нова функція для отримання статистики за період ---
# --- НОВА, ВИПРАВЛЕНА ВЕРСІЯ МЕТОДУ ---
@get_performance_optimizer().measure_performance("get_transactions_stats")
async def get_transactions_stats(profile_id: int, start_date: Optional[datetime], end_date: Optional[datetime]) -> dict:
    stats = {'income': 0.0, 'expense': 0.0}
    if not profile_id:
        return stats

    # Виключаємо транзакції майна з розрахунків доходів/витрат
    query_parts = [
        "SELECT type, SUM(amount) as total FROM transactions WHERE profile_id = ?",
        "AND category NOT IN (?, ?)",
        "AND description NOT LIKE 'Покупка майна:%'",
        "AND description NOT LIKE 'Продаж майна:%'"
    ]
    params = [profile_id, PROPERTY_PURCHASE_CATEGORY, PROPERTY_SALE_CATEGORY]

    if start_date:
        query_parts.append("AND timestamp >= ?")
        params.append(start_date.isoformat())
    if end_date:
        # Для коректного включення транзакцій поточного дня
        end_date_inclusive = end_date.replace(hour=23, minute=59, second=59)
        query_parts.append("AND timestamp <= ?")
        params.append(end_date_inclusive.isoformat())

    query_parts.append("GROUP BY type")
    query = " ".join(query_parts)

    async with get_db_connection() as conn:
        cursor = await conn.execute(query, tuple(params))
        rows = await cursor.fetchall()
        for row in rows:
            if row['type'] == TRANSACTION_TYPE_INCOME:
                stats['income'] = row['total'] or 0.0
            elif row['type'] == TRANSACTION_TYPE_EXPENSE:
                stats['expense'] = row['total'] or 0.0
    return stats


# --- ДОДАНО: Нова функція для розрахунку загального балансу ---
@get_performance_optimizer().measure_performance("get_total_balance")
async def get_total_balance(profile_id: int) -> float:
    if not profile_id:
        return 0.0
    
    # Перевіряємо кеш
    cache_key = f"balance_{profile_id}"
    optimizer = get_performance_optimizer()
    cached_balance = optimizer.get_cached_result(cache_key)
    if cached_balance is not None:
        return cached_balance
    
    query = """
        SELECT SUM(CASE WHEN type = 'дохід' THEN amount ELSE -amount END) as balance
        FROM transactions
        WHERE profile_id = ?
    """
    async with get_db_connection() as conn:
        cursor = await conn.execute(query, (profile_id,))
        result = await cursor.fetchone()
        balance = result['balance'] if result and result['balance'] is not None else 0.0
        
        # Кешуємо результат на 30 секунд
        optimizer.cache_result(cache_key, balance, ttl=30)
        return balance


# --- ЗМІНЕНО: Приймає profile_id ---
@track_operation("add_transaction") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.HIGH, "Помилка додавання транзакції") if OPTIMIZATION_ENABLED else lambda x: x
async def add_transaction(profile_id: int, trans_type: str, category: str, description: str, amount: float):
    if not profile_id:
        return
    timestamp = datetime.now().isoformat()
    async with get_db_connection() as conn:
        await conn.execute(
            "INSERT INTO transactions (profile_id, timestamp, type, category, description, amount) VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, timestamp, trans_type, category, description, amount)
        )
        await conn.commit()
        
        # Очищуємо кеш балансу
        optimizer = get_performance_optimizer()
        cache_key = f"balance_{profile_id}"
        if cache_key in optimizer.cache:
            del optimizer.cache[cache_key]


async def delete_transaction(transaction_id: int):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        await conn.commit()


async def update_transaction(transaction_id: int, trans_type: str = None, category: str = None, description: str = None, amount: float = None):
    """Оновлює транзакцію з можливістю оновлення тільки певних полів"""
    if not transaction_id:
        return
    
    # Будуємо динамічний SQL запит
    update_parts = []
    params = []
    
    if trans_type is not None:
        update_parts.append("type = ?")
        params.append(trans_type)
    
    if category is not None:
        update_parts.append("category = ?")
        params.append(category)
    
    if description is not None:
        update_parts.append("description = ?")
        params.append(description)
    
    if amount is not None:
        update_parts.append("amount = ?")
        params.append(amount)
    
    if not update_parts:
        return  # Нічого оновлювати
    
    params.append(transaction_id)
    query = f"UPDATE transactions SET {', '.join(update_parts)} WHERE id = ?"
    
    async with get_db_connection() as conn:
        await conn.execute(query, tuple(params))
        await conn.commit()


# --- ЗМІНЕНО: Приймає profile_id ---
async def load_categories(profile_id: int) -> dict[str, list]:
    if not profile_id:
        return {"дохід": [], "витрата": []}

    categories_by_type = {"дохід": [], "витрата": []}
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT name, type, color FROM categories WHERE profile_id = ?", (profile_id,))
        rows = await cursor.fetchall()
        for row in rows:
            if row['type'] in categories_by_type:
                categories_by_type[row['type']].append({"name": row['name'], "color": row['color']})
    return categories_by_type


# --- ЗМІНЕНО: Приймає profile_id ---
async def add_category(profile_id: int, category_type: str, category_name: str, color: str | None = None):
    if not profile_id:
        return
    async with get_db_connection() as conn:
        await conn.execute(
            "INSERT INTO categories (profile_id, type, name, color) VALUES (?, ?, ?, ?)",
            (profile_id, category_type, category_name, color)
        )
        await conn.commit()


# --- ЗМІНЕНО: Приймає profile_id ---
async def delete_category(profile_id: int, category_type: str, category_name: str):
    if not profile_id:
        return
    async with get_db_connection() as conn:
        await conn.execute(
            "DELETE FROM categories WHERE profile_id = ? AND type = ? AND name = ?",
            (profile_id, category_type, category_name)
        )
        await conn.commit()


# --- ЗМІНЕНО: Приймає profile_id ---
# --- НОВА, ВИПРАВЛЕНА ВЕРСІЯ МЕТОДУ ---
@track_operation("load_properties") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.MEDIUM, "Помилка завантаження майна") if OPTIMIZATION_ENABLED else lambda x: x
async def load_properties(profile_id: int, status: str = 'active') -> list[dict]:
    """
    Завантажує майно для профілю, фільтруючи за статусом ('active' або 'sold').
    """
    if not profile_id:
        return []

    # Сортуємо за порядком, встановленим користувачем для обох типів майна
    order_by_clause = "ORDER BY display_order"

    async with get_db_connection() as conn:
        cursor = await conn.execute(
            f"SELECT id, name, price, image_b64, display_order, selling_price, sold_timestamp, created_timestamp FROM properties WHERE profile_id = ? AND status = ? {order_by_clause}",
            (profile_id, status)
        )
        properties = await cursor.fetchall()
        result = [dict(row) for row in properties]
        
        return result


# --- ЗМІНЕНО: Приймає profile_id ---
@track_operation("add_property") if OPTIMIZATION_ENABLED else lambda x: x
@handle_errors(ErrorCategory.DATABASE, ErrorSeverity.HIGH, "Помилка додавання майна") if OPTIMIZATION_ENABLED else lambda x: x
async def add_property(profile_id: int, name: str, price: float, image_b64: str) -> int | None:
    if not profile_id:
        return None
    
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT MAX(display_order) FROM properties WHERE profile_id = ?", (profile_id,))
        max_order = await cursor.fetchone()
        # row is sqlite3.Row; access by index or key
        max_val = max_order[0] if max_order is not None else 0
        next_order = (max_val or 0) + 1
        created_timestamp = datetime.now().isoformat()
        insert_cursor = await conn.execute(
            "INSERT INTO properties (profile_id, name, price, image_b64, display_order, created_timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, name, price, image_b64, next_order, created_timestamp)
        )
        await conn.commit()
        try:
            new_id = insert_cursor.lastrowid
            return new_id
        except Exception as e:
            logger.error(f"Error getting lastrowid: {e}")
            return None


async def update_property(property_id: int, name: str, price: float, image_b64: str):
    async with get_db_connection() as conn:
        await conn.execute(
            "UPDATE properties SET name = ?, price = ?, image_b64 = ? WHERE id = ?",
            (name, price, image_b64, property_id)
        )
        await conn.commit()


# --- НОВІ МЕТОДИ ---
async def sell_property(property_id: int, selling_price: float):
    """Оновлює статус майна на 'sold' і зберігає ціну та дату продажу."""
    sold_timestamp = datetime.now().isoformat()
    async with get_db_connection() as conn:
        await conn.execute(
            "UPDATE properties SET status = 'sold', selling_price = ?, sold_timestamp = ? WHERE id = ?",
            (selling_price, sold_timestamp, property_id)
        )
        await conn.commit()


async def delete_property_permanently(property_id: int):
    """Фізично видаляє запис про майно з бази даних."""
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        await conn.commit()

async def restore_property(property_id: int):
    """Повертає майно з проданого в активне."""
    async with get_db_connection() as conn:
        await conn.execute(
            "UPDATE properties SET status = 'active', selling_price = NULL, sold_timestamp = NULL WHERE id = ?",
            (property_id,)
        )
        await conn.commit()

async def get_property(property_id: int) -> Optional[dict]:
    """Повертає дані майна за id або None."""
    if not property_id:
        logger.warning("⚠️ get_property called with None or empty property_id")
        return None
    
    logger.info(f"🔄 Looking for property with ID: {property_id}")
    
    async with get_db_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, profile_id, name, price, image_b64, status, display_order, selling_price, sold_timestamp, created_timestamp FROM properties WHERE id = ?",
            (property_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            logger.info(f"✅ Found property: {row['name']} (ID: {property_id})")
            return dict(row)
        else:
            logger.warning(f"⚠️ No property found with ID: {property_id}")
            return None

async def update_properties_order(profile_id: int, ordered_ids: list[int]):
    if not profile_id or not ordered_ids:
        return
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            for index, prop_id in enumerate(ordered_ids):
                await cursor.execute(
                    "UPDATE properties SET display_order = ? WHERE id = ? AND profile_id = ?",
                    (index, prop_id, profile_id)
                )
        await conn.commit()

async def update_sold_properties_order(profile_id: int, ordered_ids: list[int]):
    if not profile_id or not ordered_ids:
        return
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            for index, prop_id in enumerate(ordered_ids):
                await cursor.execute(
                    "UPDATE properties SET display_order = ? WHERE id = ? AND profile_id = ? AND status = 'sold'",
                    (index, prop_id, profile_id)
                )
        await conn.commit()



async def get_category_summary(profile_id: int, start_date: Optional[datetime], end_date: Optional[datetime]) -> Tuple[Dict[str, float], Dict[str, float]]:
    income_by_category = defaultdict(float)
    expense_by_description = defaultdict(float)
    if not profile_id:
        return dict(income_by_category), dict(expense_by_description)

    query_parts = [
        "SELECT type, category, description, SUM(amount) as total",
        "FROM transactions",
        "WHERE profile_id = ?"
    ]
    params = [profile_id]

    if start_date:
        query_parts.append("AND timestamp >= ?")
        params.append(start_date.isoformat())
    if end_date:
        end_date_inclusive = end_date.replace(hour=23, minute=59, second=59)
        query_parts.append("AND timestamp <= ?")
        params.append(end_date_inclusive.isoformat())

    query_parts.append("GROUP BY type, category, description")
    query = " ".join(query_parts)

    async with get_db_connection() as conn:
        cursor = await conn.execute(query, tuple(params))
        rows = await cursor.fetchall()
        for row in rows:
            # Виключаємо транзакції майна з доходів/витрат
            description = row['description'] or ""
            category = row['category'] or ""
            
            # Перевіряємо чи це транзакція майна
            is_property_transaction = (
                category in [PROPERTY_PURCHASE_CATEGORY, PROPERTY_SALE_CATEGORY] or
                description.startswith("Покупка майна:") or
                description.startswith("Продаж майна:")
            )
            
            # Виключаємо всі транзакції майна з розрахунків доходів/витрат
            if not is_property_transaction:
                if row['type'] == TRANSACTION_TYPE_INCOME and category and category not in [INITIAL_BALANCE_CATEGORY, CORRECTION_CATEGORY, PROPERTY_SALE_CATEGORY]:
                    income_by_category[category] += row['total']
                elif row['type'] == TRANSACTION_TYPE_EXPENSE and description and category not in [PROPERTY_PURCHASE_CATEGORY]:
                    expense_by_description[description] += row['total']

    return dict(income_by_category), dict(expense_by_description)


# --- НОВА, ВИПРАВЛЕНА ВЕРСІЯ МЕТОДУ ---
async def merge_categories(profile_id: int, source_names: list[str], target_name: str, category_type: str,
                           new_color: str):
    """
    Об'єднує кілька категорій в одну нову, оновлюючи транзакції.
    Виконується в одній транзакції БД для атомарності.
    """
    if not profile_id or not source_names or not target_name:
        return

    async with get_db_connection() as conn:
        try:
            # 1. Створити нову цільову категорію
            await conn.execute(
                "INSERT INTO categories (profile_id, type, name, color) VALUES (?, ?, ?, ?)",
                (profile_id, category_type, target_name, new_color)
            )

            # 2. Оновити всі транзакції, що використовували старі категорії
            placeholders = ", ".join("?" for _ in source_names)
            update_query = f"UPDATE transactions SET category = ? WHERE profile_id = ? AND category IN ({placeholders})"

            params = [target_name, profile_id] + source_names
            await conn.execute(update_query, tuple(params))

            # 3. Видалити старі категорії
            delete_query = f"DELETE FROM categories WHERE profile_id = ? AND name IN ({placeholders})"
            delete_params = [profile_id] + source_names
            await conn.execute(delete_query, tuple(delete_params))

            # 4. Якщо все успішно, підтверджуємо транзакцію
            await conn.commit()

        except Exception as e:
            pass
            # У разі помилки - відкочуємо всі зміни
            await conn.rollback()

# --- FALLBACK DATABASE MANAGER ФУНКЦІЇ ---
# Синхронні функції видалені, оскільки не використовуються