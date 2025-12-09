"""Система рекомендаций для пользователей."""

import random
import time
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User

# Кулдаун рекомендаций для каждого пользователя (в секундах)
RECOMMENDATION_COOLDOWN = 300  # 5 минут
# Шанс показа рекомендации (даже если сработало ключевое слово)
RECOMMENDATION_CHANCE = 0.15  # 15%

# Трекер последних рекомендаций для каждого пользователя
_last_recommendation_time: dict[int, float] = defaultdict(float)
_last_recommendation_type: dict[int, str] = {}


# Расширенный список рекомендаций по категориям
RECOMMENDATIONS = {
    "grow": [
        "Хочешь стать больше? Попробуй `/grow`!",
        "Размер имеет значение! Жми `/grow`",
        "Маловат? `/grow` поможет!",
    ],
    "pvp": [
        "Готов к бою? Вызови кого-нибудь на `/pvp`!",
        "Хочешь проверить силу? `/pvp @ник` — и вперёд!",
        "Дуэль? `/pvp` ждёт тебя!",
    ],
    "top": [
        "Хочешь быть лучшим? Проверь `/top`!",
        "Глянь `/top_rep` — может ты уже в топе?",
        "Рейтинг ждёт: `/top` или `/top_rep`",
    ],
    "achievements": [
        "Проверь свои `/my_achievements`!",
        "Ачивки ждут! `/my_achievements`",
        "Загляни в `/achievements_leaderboard`!",
    ],
    "quests": [
        "Не знаешь, что делать? Загляни в `/quests`!",
        "Квесты дают награды! `/quests`",
        "Проверь задания: `/quests`",
    ],
    "guild": [
        "Ищешь команду? `/create_guild` или `/join_guild`!",
        "Гильдия — сила! `/guild_info`",
        "Создай свою гильдию: `/create_guild`",
    ],
    "duo": [
        "Хочешь играть вдвоем? `/duo_invite @друг`",
        "Дуэт сильнее! `/duo_invite`",
        "Проверь свой дуэт: `/duo_profile`",
    ],
    "casino": [
        "Чувствуешь удачу? `/casino` ждёт!",
        "Рискни в `/casino`! Но не всё сразу",
        "Слоты крутятся: `/casino [ставка]`",
    ],
    "games": [
        "Все игры тут: `/games`",
        "Не знаешь с чего начать? `/games`",
        "Полный список команд: `/games`",
    ],
    "profile": [
        "Глянь свой профиль: `/profile`",
        "Статистика ждёт: `/profile`",
    ],
    "blackjack": [
        "Любишь карты? `/blackjack`!",
        "21 очко: `/blackjack [ставка]`",
    ],
    "fish": [
        "Порыбачь: `/fish`!",
        "Рыбалка расслабляет: `/fish`",
    ],
    "crash": [
        "Испытай удачу в `/crash`!",
        "Успей выйти вовремя: `/crash`",
    ],
}

# Ключевые слова для каждой категории
KEYWORDS = {
    "grow": ["размер", "маленький", "больше", "вырасти", "рост"],
    "pvp": ["пвп", "дуэль", "сразиться", "бой", "драка", "побить"],
    "top": ["топ", "лучший", "рейтинг", "первый", "лидер"],
    "achievements": ["достижения", "ачивки", "награды", "медали"],
    "quests": ["квесты", "задания", "миссии", "что делать"],
    "guild": ["гильдия", "клан", "команда", "объединение"],
    "duo": ["дуэт", "вдвоем", "партнер", "напарник", "друг"],
    "casino": ["казино", "ставка", "удача", "выиграть", "слоты"],
    "games": ["игры", "команды", "что есть", "функции"],
    "profile": ["профиль", "статистика", "мои данные"],
    "blackjack": ["блэкджек", "карты", "21"],
    "fish": ["рыба", "рыбалка", "ловить"],
    "crash": ["краш", "множитель"],
}


def _can_show_recommendation(user_id: int, category: str) -> bool:
    """Проверяет, можно ли показать рекомендацию пользователю."""
    now = time.time()
    last_time = _last_recommendation_time.get(user_id, 0)
    last_type = _last_recommendation_type.get(user_id)
    
    # Проверяем кулдаун
    if now - last_time < RECOMMENDATION_COOLDOWN:
        return False
    
    # Не показываем ту же категорию подряд
    if last_type == category:
        return False
    
    return True


def _record_recommendation(user_id: int, category: str):
    """Записывает факт показа рекомендации."""
    _last_recommendation_time[user_id] = time.time()
    _last_recommendation_type[user_id] = category


async def generate_recommendation(
    session: AsyncSession, user: User, user_text: str
) -> str:
    """
    Анализирует текст пользователя и предлагает релевантную игровую команду.
    
    Рекомендации показываются:
    - С шансом 15%
    - Не чаще раза в 5 минут для одного пользователя
    - Не повторяют предыдущую категорию
    """
    # Проверяем шанс показа
    if random.random() > RECOMMENDATION_CHANCE:
        return ""
    
    text_lower = user_text.lower()
    matched_categories = []
    
    # Ищем совпадения по ключевым словам
    for category, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                matched_categories.append(category)
                break
    
    if not matched_categories:
        return ""
    
    # Фильтруем категории по кулдауну
    available_categories = [
        cat for cat in matched_categories 
        if _can_show_recommendation(user.id, cat)
    ]
    
    if not available_categories:
        return ""
    
    # Выбираем случайную категорию и рекомендацию
    category = random.choice(available_categories)
    recommendation = random.choice(RECOMMENDATIONS[category])
    
    # Записываем показ
    _record_recommendation(user.id, category)
    
    return recommendation
