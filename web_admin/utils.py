"""Вспомогательные функции для веб-админки."""

import asyncio
from functools import wraps
from typing import Any, Callable, Awaitable


def async_to_sync(async_func: Callable[..., Awaitable[Any]]):
    """
    Декоратор для вызова асинхронных функций из синхронного контекста Flask.
    
    Args:
        async_func: Асинхронная функция для оборачивания
        
    Returns:
        Синхронная функция, которая вызывает асинхронную
    """
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        # Если уже в асинхронном цикле - используем create_task
        try:
            loop = asyncio.get_running_loop()
            # Если мы уже в цикле, создаем задачу и ждем её
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(async_func(*args, **kwargs))
                )
                return future.result()
        except RuntimeError:
            # Если не в цикле, просто запускаем
            return asyncio.run(async_func(*args, **kwargs))
    
    return wrapper


# Альтернативная реализация для более надежной работы
def run_async(coro):
    """
    Запускает асинхронную корутину в синхронном контексте.
    
    Args:
        coro: Асинхронная корутина
        
    Returns:
        Результат выполнения корутины
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # Если цикла нет, создаем новый
        loop = None
    
    if loop and loop.is_running():
        # Если в асинхронном контексте, используем run_coroutine_threadsafe
        import threading
        if threading.current_thread() is threading.main_thread():
            # Создаем временный цикл в отдельном потоке
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(coro))
                return future.result()
        else:
            # В другом потоке создаем новый цикл
            return asyncio.run(coro)
    else:
        # Если цикл не запущен, используем его
        if loop is None:
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)