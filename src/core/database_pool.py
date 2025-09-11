"""
Connection pooling для оптимізації роботи з базою даних
"""

import asyncio
import aiosqlite
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PoolConfig:
    """Конфігурація пулу з'єднань"""
    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: int = 30
    idle_timeout: int = 300  # 5 хвилин

class DatabaseConnection:
    """Обгортка для з'єднання з БД"""
    
    def __init__(self, connection: aiosqlite.Connection, pool: 'DatabasePool'):
        self.connection = connection
        self.pool = pool
        self.created_at = asyncio.get_event_loop().time()
        self.last_used = self.created_at
        self.in_use = False
    
    def cursor(self):
        """Повертає курсор для з'єднання"""
        return self.connection.cursor()
    
    async def execute(self, query: str, params: tuple = ()):
        """Виконує SQL запит"""
        try:
            self.last_used = asyncio.get_event_loop().time()
            return await self.connection.execute(query, params)
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
    
    async def executemany(self, query: str, params_list: list):
        """Виконує SQL запит для множини параметрів"""
        try:
            self.last_used = asyncio.get_event_loop().time()
            return await self.connection.executemany(query, params_list)
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
    
    async def commit(self):
        """Підтверджує транзакцію"""
        await self.connection.commit()
    
    async def rollback(self):
        """Відкочує транзакцію"""
        await self.connection.rollback()
    
    async def close(self):
        """Закриває з'єднання"""
        await self.connection.close()
    
    # Додаткові методи для повної сумісності
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self.pool.return_connection(self)
    
    def __getattr__(self, name):
        """Делегує невідомі атрибути до базового з'єднання"""
        return getattr(self.connection, name)

class DatabasePool:
    """Пул з'єднань з базою даних"""
    
    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        self.db_path = db_path
        self.config = config or PoolConfig()
        self._pool: asyncio.Queue[DatabaseConnection] = asyncio.Queue()
        self._all_connections: set[DatabaseConnection] = set()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Ініціалізує пул з'єднань"""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            # Створюємо мінімальну кількість з'єднань
            for _ in range(self.config.min_connections):
                conn = await self._create_connection()
                await self._pool.put(conn)
                self._all_connections.add(conn)
            
            # Запускаємо cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())
            self._initialized = True
            
            logger.info(f"Database pool initialized with {self.config.min_connections} connections")
    
    async def _create_connection(self) -> DatabaseConnection:
        """Створює нове з'єднання з БД"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA cache_size = 10000")
        await conn.execute("PRAGMA temp_store = MEMORY")
        
        return DatabaseConnection(conn, self)
    
    async def get_connection(self) -> DatabaseConnection:
        """Отримує з'єднання з пулу"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Спробуємо отримати з'єднання з пулу
            connection = await asyncio.wait_for(
                self._pool.get(), 
                timeout=self.config.connection_timeout
            )
            connection.in_use = True
            return connection
        except asyncio.TimeoutError:
            # Якщо пул порожній, створюємо нове з'єднання
            async with self._lock:
                if len(self._all_connections) < self.config.max_connections:
                    connection = await self._create_connection()
                    connection.in_use = True
                    self._all_connections.add(connection)
                    logger.info(f"Created new connection. Total: {len(self._all_connections)}")
                    return connection
                else:
                    raise Exception("Maximum connections reached")
    
    async def return_connection(self, connection: DatabaseConnection):
        """Повертає з'єднання в пул"""
        if connection.in_use:
            connection.in_use = False
            connection.last_used = asyncio.get_event_loop().time()
            await self._pool.put(connection)
    
    async def _cleanup_idle_connections(self):
        """Очищає неактивні з'єднання"""
        while True:
            try:
                await asyncio.sleep(60)  # Перевіряємо кожну хвилину
                
                current_time = asyncio.get_event_loop().time()
                connections_to_remove = []
                
                async with self._lock:
                    for conn in self._all_connections:
                        if (not conn.in_use and 
                            current_time - conn.last_used > self.config.idle_timeout and
                            len(self._all_connections) > self.config.min_connections):
                            connections_to_remove.append(conn)
                
                for conn in connections_to_remove:
                    await conn.close()
                    self._all_connections.remove(conn)
                    logger.info(f"Removed idle connection. Total: {len(self._all_connections)}")
                    
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    @asynccontextmanager
    async def get_connection_context(self) -> AsyncGenerator[DatabaseConnection, None]:
        """Контекстний менеджер для роботи з з'єднанням"""
        connection = await self.get_connection()
        try:
            yield connection
        finally:
            await self.return_connection(connection)
    
    async def close_all(self):
        """Закриває всі з'єднання"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        async with self._lock:
            for conn in self._all_connections:
                await conn.close()
            self._all_connections.clear()
            self._initialized = False
        
        logger.info("All database connections closed")

# Глобальний екземпляр пулу
_db_pool: Optional[DatabasePool] = None

async def get_db_pool() -> DatabasePool:
    """Отримує глобальний екземпляр пулу БД"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool("tracker.db")
        await _db_pool.initialize()
    return _db_pool

async def close_db_pool():
    """Закриває глобальний пул БД"""
    global _db_pool
    if _db_pool:
        await _db_pool.close_all()
        _db_pool = None
