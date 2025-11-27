"""Middleware для защиты от 'дрючки' - спама командами от одного пользователя."""

import logging
import time
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Структура для отслеживания активности пользователей
class UserSpamTracker:
    def __init__(self):
        # Словарь: user_id -> {'command_times': [timestamps], 'blocked_until': timestamp}
        self.users = {}
        self.command_limit = 5  # Максимальное количество команд за период
        self.time_window = 60  # Временной интервал в секундах
        self.block_duration = 300  # Длительность блокировки в секундах (5 минут)

    def add_command(self, user_id: int) -> bool:
        """
        Добавляет команду от пользователя и проверяет, не превышен ли лимит.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True, если пользователь может продолжать, False если заблокирован
        """
        current_time = time.time()
        
        if user_id not in self.users:
            self.users[user_id] = {
                'command_times': [],
                'blocked_until': 0,
                'complaints_count': 0
            }
        
        user_data = self.users[user_id]
        
        # Проверяем, заблокирован ли пользователь
        if current_time < user_data['blocked_until']:
            # Увеличиваем счётчик жалоб, если пользователь продолжает спамить
            user_data['complaints_count'] += 1
            return False
        
        # Удаляем старые команды из временного окна
        user_data['command_times'] = [
            t for t in user_data['command_times'] 
            if current_time - t < self.time_window
        ]
        
        # Добавляем текущую команду
        user_data['command_times'].append(current_time)
        
        # Проверяем, превышен ли лимит
        if len(user_data['command_times']) > self.command_limit:
            # Блокируем пользователя
            user_data['blocked_until'] = current_time + self.block_duration
            user_data['complaints_count'] = 0  # Сбрасываем счётчик при блокировке
            logger.warning(f"Пользователь {user_id} заблокирован за спам ({len(user_data['command_times'])} команд за {self.time_window}с)")
            return False
        
        return True

    def is_blocked(self, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь."""
        if user_id not in self.users:
            return False
        
        current_time = time.time()
        user_data = self.users[user_id]
        
        if current_time < user_data['blocked_until']:
            return True
        else:
            # Разблокируем пользователя, если время блокировки истекло
            user_data['blocked_until'] = 0
            return False


# Глобальный трекер
user_tracker = UserSpamTracker()


class SpamControlMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем, является ли сообщение командой
        if event.text and event.text.startswith('/'):
            user_id = event.from_user.id
            
            # Добавляем команду в трекер
            if not user_tracker.add_command(user_id):
                # Пользователь превысил лимит - игнорируем команду
                logger.info(f"Команда от пользователя {user_id} проигнорирована (спам-фильтр)")
                
                # Проверим, сколько раз пользователь продолжал слать команды после блокировки
                complaints = user_tracker.users[user_id]['complaints_count'] if user_id in user_tracker.users else 0
                
                # Если пользователь продолжает спамить после блокировки, время от времени
                # отправляем ему грубый ответ
                if complaints > 0 and complaints % 3 == 0:  # Каждые 3 попытки
                    try:
                        # Отправляем грубый ответ, имитируя Олега
                        responses = [
                            f"Слышь, @{event.from_user.username or 'чувак'}, заебал уже, дай отдохнуть",
                            f"Ты чё, @{event.from_user.username or 'идиот'}, залип по командам? Отдохни чуток.",
                            f"Пользователь @{event.from_user.username or 'незнакомец'}, хватит спамить!",
                            f"Ну ты и дрючка, @{event.from_user.username or 'дружище'}! Дай другим слово сказать."
                        ]
                        await event.answer(responses[min(complaints // 3, len(responses) - 1)])
                    except Exception:
                        pass  # Игнорируем ошибки при отправке сообщения
                
                return  # Не передаем управление дальше - команда игнорируется
            
            # Пользователь в пределах лимита - продолжаем обычную обработку
            return await handler(event, data)
        
        # Если сообщение не является командой, передаем дальше
        return await handler(event, data)