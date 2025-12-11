#!/usr/bin/env python3
"""
Полный вайп базы данных и векторной памяти.
Сбрасывает всё к начальному состоянию.

Использование:
    python wipe_all.py
"""

import asyncio
import shutil
import os
from pathlib import Path


async def wipe_database():
    """Сбросить все таблицы в базе данных."""
    print("🗄️  Сброс базы данных...")
    
    from app.database.session import get_session
    from sqlalchemy import text
    
    async_session = get_session()
    
    async with async_session() as session:
        # Сбрасываем active_topic_id для всех чатов
        await session.execute(text("UPDATE chats SET active_topic_id = NULL"))
        
        # Очищаем таблицу сообщений
        await session.execute(text("DELETE FROM messages"))
        
        # Очищаем историю вопросов
        await session.execute(text("DELETE FROM user_question_history"))
        
        await session.commit()
        print("   ✅ База данных очищена")


def wipe_vector_memory():
    """Удалить векторную базу данных (ChromaDB)."""
    print("🧠 Сброс векторной памяти...")
    
    from app.config import settings
    
    chromadb_path = Path(settings.chromadb_persist_dir)
    
    if chromadb_path.exists():
        shutil.rmtree(chromadb_path)
        print(f"   ✅ Удалена директория: {chromadb_path}")
    else:
        print(f"   ℹ️  Директория не существует: {chromadb_path}")
    
    # Создаём пустую директорию
    chromadb_path.mkdir(parents=True, exist_ok=True)
    print(f"   ✅ Создана пустая директория: {chromadb_path}")


async def main():
    print("=" * 50)
    print("🔥 ПОЛНЫЙ ВАЙП ДАННЫХ БОТА")
    print("=" * 50)
    print()
    
    # Подтверждение
    confirm = input("Вы уверены? Это удалит ВСЕ данные! (yes/no): ")
    if confirm.lower() != "yes":
        print("❌ Отменено")
        return
    
    print()
    
    # Вайп векторной памяти
    wipe_vector_memory()
    
    # Вайп базы данных
    await wipe_database()
    
    print()
    print("=" * 50)
    print("✅ ВАЙП ЗАВЕРШЁН")
    print("=" * 50)
    print()
    print("Перезапустите бота для применения изменений.")


if __name__ == "__main__":
    asyncio.run(main())
