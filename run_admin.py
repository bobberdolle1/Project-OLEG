#!/usr/bin/env python3
"""Скрипт для запуска веб-админки Олега."""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_web_admin():
    """Запускает веб-админку Flask."""
    from web_admin.app import app
    
    print("Запуск веб-админки Олега...")
    print("Адрес: http://localhost:5000")
    print("Для входа используйте:")
    print("  Логин: admin")
    print("  Пароль: oleg123")
    print("или значения из переменных окружения:")
    print("  ADMIN_USERNAME")
    print("  ADMIN_PASSWORD")
    print()
    
    # Запускаем Flask приложение
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # В продакшене всегда False
    )

if __name__ == "__main__":
    run_web_admin()