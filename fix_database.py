#!/usr/bin/env python3
"""
Скрипт для виправлення бази даних - додавання колонки created_timestamp
"""
import asyncio
import aiosqlite
from datetime import datetime

async def fix_database():
    print('🔧 Виправляємо базу даних...')
    
    try:
        async with aiosqlite.connect('tracker.db') as conn:
            # Перевіряємо структуру таблиці properties
            cursor = await conn.execute('PRAGMA table_info(properties)')
            columns = [row[1] for row in await cursor.fetchall()]
            
            print(f'📋 Поточні колонки в таблиці properties: {columns}')
            
            if 'created_timestamp' not in columns:
                print('📝 Додаємо колонку created_timestamp...')
                await conn.execute('ALTER TABLE properties ADD COLUMN created_timestamp TEXT')
                
                # Заповнюємо існуючі записи поточною датою
                await conn.execute('UPDATE properties SET created_timestamp = ? WHERE created_timestamp IS NULL', 
                                 (datetime.now().isoformat(),))
                await conn.commit()
                print('✅ Колонка created_timestamp додана та заповнена!')
            else:
                print('✅ Колонка created_timestamp вже існує!')
            
            # Перевіряємо результат
            cursor = await conn.execute('PRAGMA table_info(properties)')
            columns_after = [row[1] for row in await cursor.fetchall()]
            print(f'📋 Колонки після міграції: {columns_after}')
            
    except Exception as e:
        print(f'❌ Помилка: {e}')
        return False
    
    print('🎯 База даних успішно виправлена!')
    return True

if __name__ == "__main__":
    asyncio.run(fix_database())
