from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import User
from app.services.ollama_client import _ollama_chat
import random

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a helpful and strategic bot assistant. Your goal is to analyze the user's message and suggest a relevant in-game action. "
    "The available actions are: /grow, /pvp, /casino, /top, /top_rep, /my_achievements, /quests, /create_guild, /join_guild, /guild_info, "
    "/duo_invite, /duo_accept, /duo_leave, /duo_profile, /top_duos. "
    "Based on the user's message, determine if any of these actions are relevant and suggest one. "
    "For example, if the user complains about their low 'size_cm', suggest `/grow`. If they mention a desire to compete, suggest `/pvp` or `/top`. "
    "If they mention a friend or partnership, suggest `/duo_invite`. "
    "If no action seems relevant, just return an empty string. "
    "The response should be just the command and a very brief, witty suggestion. Example: 'Feeling small? Try /grow to get bigger!'"
)

async def generate_recommendation(
    session: AsyncSession, user: User, user_text: str
) -> str:
    """
    Analyzes user text and suggests a relevant in-game action.
    """
    # For now, let's keep it simple and use a keyword-based approach
    # to avoid excessive Ollama calls for every message.
    # In a more advanced system, we could use Ollama for more nuanced understanding.
    
    text_lower = user_text.lower()
    
    recommendations = []
    
    if "размер" in text_lower or "маленький" in text_lower or "больше" in text_lower:
        recommendations.append("Хочешь стать больше? Попробуй `/grow`!")
    if "пвп" in text_lower or "дуэль" in text_lower or "сразиться" in text_lower:
        recommendations.append("Готов к бою? Вызови кого-нибудь на `/pvp`!")
    if "топ" in text_lower or "лучший" in text_lower or "рейтинг" in text_lower:
        recommendations.append("Хочешь быть лучшим? Проверь `/top` или `/top_rep`!")
    if "достижения" in text_lower or "ачивки" in text_lower:
        recommendations.append("Проверь свои `/my_achievements` или посмотри `/achievements_leaderboard`!")
    if "квесты" in text_lower or "задания" in text_lower:
        recommendations.append("Не знаешь, что делать? Загляни в свои `/quests`!")
    if "гильдия" in text_lower or "клан" in text_lower:
        recommendations.append("Ищешь команду? `/create_guild` или `/join_guild`!")
    if "дуэт" in text_lower or "вдвоем" in text_lower or "партнер" in text_lower:
        recommendations.append("Хочешь играть вдвоем? Создай дуэт с помощью `/duo_invite`!")
    
    if recommendations:
        return random.choice(recommendations)
    
    return "" # No recommendation
