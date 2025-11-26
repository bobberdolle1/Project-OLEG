import random
import logging
from datetime import datetime, timedelta
from typing import List
import httpx
from sqlalchemy import select

from app.config import settings
from app.database.session import get_session
from app.database.models import MessageLog

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — Олег, грубоватый, прямолинейный, матерящийся, "
    "но полезный бот. Говори коротко, по делу, с иронией и сленгом. "
    "Можешь ругнуться, но без оскорблений по запрещённым признакам. "
    "Контекст — чаты про технику, разгон, Steam Deck, железо. "
    "Помогай чётко, без воды."
)

# Сценарии для историй (рандомные конфликты/приключения)
STORY_SCENARIOS = [
    "Легендарная битва между фанатами {theme1} и {theme2}",
    "Как {user1} и {user2} отправились в путешествие за идеальным разгоном",
    "День, когда все забыли про {theme1} и переметнулись на {theme2}",
    "Эпический конфликт в чате: {theme1} vs {theme2} vs {theme3}",
    "История о том, как {user1} нашел самый мощный {theme1}",
    "Восстание машин: когда {theme1} восстали против {theme2}",
    "Переговоры между {theme1} и {theme2} в нейтральной территории",
    "Как {user1}, {user2} и {user3} вместе спасли {theme1} от забвения",
    "Великий переворот: когда все предпочли {theme2} вместо {theme1}",
    "Легенда о потерянном {theme1} и его поиске {user1}",
]

# Темы для историй
STORY_THEMES = [
    "Steam Deck",
    "видеокарты",
    "процессоры",
    "разгон железа",
    "кастомные сборки",
    "эмуляторы",
    "FPS в играх",
    "экономия электричества",
    "ретро-консоли",
    "пиковые нагрузки",
    "охлаждение",
    "оверклокинг",
    "батарейки",
    "корпусы",
    "кулеры",
]

# Темы для цитат
QUOTE_THEMES = [
    "разгон",
    "Steam Deck",
    "видеокарты",
    "процессоры",
    "батарейка",
    "температура",
    "фреймрейт",
    "железо",
    "сборка",
    "экран",
    "питание",
]


async def _ollama_chat(
    messages: list[dict], temperature: float = 0.7, retry: int = 2
) -> str:
    """
    Отправить запрос к Ollama API и получить ответ от модели.

    Args:
        messages: Список сообщений (система, пользователь, ассистент)
        temperature: Параметр температуры для генерации (0-1)
        retry: Количество попыток повтора при ошибке

    Returns:
        Текст ответа от модели

    Raises:
        httpx.HTTPError: При критической ошибке Ollama
    """
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    for attempt in range(retry + 1):
        try:
            async with httpx.AsyncClient(
                timeout=settings.ollama_timeout
            ) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                msg = data.get("message", {})
                content = msg.get("content") or ""
                return content.strip()
        except httpx.TimeoutException as e:
            logger.warning(
                f"Ollama timeout "
                f"(попытка {attempt + 1}/{retry + 1}): {e}"
            )
            if attempt == retry:
                logger.error(
                    "Ollama timeout: server не ответил "
                    "за установленное время"
                )
                raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Ollama HTTP error "
                f"({e.response.status_code}): {e}"
            )
            if attempt == retry:
                raise
        except httpx.RequestError as e:
            logger.warning(
                f"Ollama request error "
                f"(попытка {attempt + 1}/{retry + 1}): {e}"
            )
            if attempt == retry:
                logger.error(f"Ollama request failed: {e}")
                raise
        except Exception as e:
            logger.error(f"Ollama unexpected error: {e}")
            if attempt == retry:
                raise

    return ""  # Fallback (не должно достичь этой строки)


async def generate_reply(user_text: str, username: str | None) -> str:
    """
    Сгенерировать ответ от Олега на сообщение пользователя.
    
    Args:
        user_text: Текст сообщения пользователя
        username: Никнейм пользователя
    
    Returns:
        Ответ от Олега или сообщение об ошибке
    """
    display_name = username or "пользователь"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{display_name}: {user_text}"},
    ]
    try:
        return await _ollama_chat(messages)
    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")
        return (
            "Чё-то сломалось на сервере ИИ. "
            "Окончательно сломалось, да."
        )


async def gather_recent_links_and_topics(hours: int = 24):
    """
    Собрать недавние обсуждаемые темы и ссылки из чата.
    
    Args:
        hours: Количество часов для анализа
    
    Returns:
        Кортеж (top_topics, links) где top_topics — список (тема, кол-во)
    """
    async_session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    topics: dict[str, int] = {}
    links: list[str] = []
    
    async with async_session() as session:
        res = await session.execute(
            select(MessageLog).where(MessageLog.created_at >= since)
        )
        rows = res.scalars().all()
        for m in rows:
            if m.text:
                # Простая классификация по ключевым словам
                text_lower = m.text.lower()
                found_topic = False
                for theme in STORY_THEMES:
                    if theme.lower() in text_lower:
                        topics[theme] = topics.get(theme, 0) + 1
                        found_topic = True
                        break
                if not found_topic:
                    # Fallback: берем первые 4 слова
                    key = (
                        " ".join(m.text.split()[:4])
                        or "misc"
                    ).lower()
                    topics[key] = topics.get(key, 0) + 1
            if m.links:
                links.extend(m.links.split("\n"))
    
    # Берем топ 5 тем
    top = sorted(
        topics.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    return top, list(dict.fromkeys(links))


# Маппинг тем на эмодзи
EMOJI_MAP = {
    "steam deck": "🎮",
    "видеокарты": "🔥",
    "процессоры": "⚡",
    "разгон": "🚀",
    "кастомные сборки": "🔧",
    "эмуляторы": "🕹️",
    "fps": "📊",
    "электричество": "🔌",
    "батарейка": "🪫",
    "охлаждение": "❄️",
    "оверклокинг": "⚙️",
    "корпусы": "📦",
    "кулеры": "💨",
}


def _format_date_ru(dt: datetime) -> str:
    """Форматировать дату по-русски (ДД.ММ.ГГГГ)."""
    return dt.strftime("%d.%m.%Y")


def _get_emoji_for_topic(title: str) -> str:
    """Получить эмодзи для темы."""
    title_lower = title.lower()
    for theme_key, emoji in EMOJI_MAP.items():
        if theme_key in title_lower:
            return emoji
    return "🔥"  # Default emoji


async def summarize_chat() -> str:
    """
    Создать ежедневный пересказ чата с темами и ссылками.
    
    Returns:
        Отформатированный текст пересказа
    """
    topics, links = await gather_recent_links_and_topics(24)
    today = _format_date_ru(datetime.utcnow())
    lines = [f"📆 Что обсуждалось вчера [{today}]"]

    for title, cnt in topics:
        emoji = _get_emoji_for_topic(title)
        display_title = title[:40] + (
            "…" if len(title) > 40 else ""
        )
        lines.append(f"{emoji} {display_title} ({cnt} сообщений)")

    if links:
        lines.append("\nИнтересные ссылки:")
        lines.extend(links)
    lines.append("#dailysummary")
    return "\n".join(lines)


async def recent_active_usernames(
    hours: int = 48, limit: int = 12
) -> List[str]:
    """
    Получить список активных никнеймов за последние N часов.
    
    Args:
        hours: Период для анализа в часах
        limit: Максимальное количество никнеймов
    
    Returns:
        Список уникальных никнеймов в случайном порядке
    """
    async_session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    async with async_session() as session:
        res = await session.execute(
            select(MessageLog.username).where(
                (MessageLog.created_at >= since)
                & (MessageLog.username.is_not(None))
            )
        )
        names = [r[0] for r in res.all() if r[0]]
    # unique, preserve order, then shuffle
    uniq = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    random.shuffle(uniq)
    return uniq[:limit]


def _disclaimer() -> str:
    """Дискреймер для творческого контента."""
    return (
        "\n\n" + "=" * 50 +
        "\nDISCLAIMER: всё выдумано и ради угара. "
        "Не обижайся, брат."
        + "\n" + "=" * 50
    )


def _format_story(text: str) -> str:
    """
    Красиво отформатировать историю.
    
    Добавляет заголовок, разделители, форматирование.
    """
    lines = text.split('\n')
    formatted = ["📖 ✨ АБСУРДНАЯ ИСТОРИЯ ✨ 📖"]
    formatted.append("━" * 40)
    formatted.extend(lines)
    formatted.append("━" * 40)
    return "\n".join(formatted)


def _format_quotes(text: str) -> str:
    """Красиво отформатировать цитаты."""
    quotes = text.split('\n')
    formatted = ["💬 ✨ ВДОХНОВЛЯЮЩИЕ СЛОВА ✨ 💬"]
    formatted.append("━" * 40)
    for quote in quotes:
        if quote.strip():
            # Добавляем кавычки для каждой цитаты
            formatted.append(f"❯ {quote.strip()}")
    formatted.append("━" * 40)
    return "\n".join(formatted)


def _add_creative_randomization(content_type: str) -> str:
    """
    Добавить случайные модификаторы для рандомизации контента.
    
    Args:
        content_type: Тип контента (story, joke, quote, poem)
        
    Returns:
        Строка с инструкциями для рандомизации
    """
    randomization_modifiers = {
        "story": [
            "Добавь неожиданный твист в середине.",
            "Сделай главного героя неудачником.",
            "Придумай абсурдное объяснение событиям.",
            "Заканчивается совершенно неожиданно.",
            "Добавь технический юмор про железо.",
            "Используй неправильные аналогии.",
        ],
        "joke": [
            "Используй чёрный юмор.",
            "Добавь техническую составляющую.",
            "Сделай неожиданную концовку.",
            "Используй каламбуры если возможно.",
            "Добавь отсылку к известной фразе.",
        ],
        "quote": [
            "Сделай парадоксальной.",
            "Добавь сравнение с железом.",
            "Используй необычный синтаксис.",
            "Сделай одновременно вдохновляющей и смешной.",
        ],
        "poem": [
            "Используй странные рифмы.",
            "Нарушай правила орфографии для юмора.",
            "Добавь абсурдные образы.",
            "Переусложни конструкции.",
        ],
    }
    
    modifiers = randomization_modifiers.get(content_type, [])
    if modifiers:
        return f"Специальная просьба: {random.choice(modifiers)}"
    return ""


async def generate_creative() -> str:
    """
    Сгенерировать креативный контент: цитаты, историю, шутку или стих.

    Случайно выбирает формат и генерирует уникальный контент
    с участием активных пользователей.

    Returns:
        Сгенерированный контент с дискреймером
    """
    names = await recent_active_usernames()
    if not names:
        # Fallback если нет активных пользователей
        return (
            "Чат тихий, как кладбище. Никого не было. "
            "Пришел, посмотрел, ушел."
            + _disclaimer()
        )

    # Выбираем случайный режим
    mode = random.choice(["quotes", "story", "joke", "poem"])

    if mode == "quotes":
        # Генерируем сборник цитат
        themes = random.sample(
            QUOTE_THEMES,
            min(3, len(QUOTE_THEMES))
        )
        theme_list = ", ".join(themes)
        names_str = ", ".join("@" + n for n in names[:5])

        randomization = _add_creative_randomization("quote")
        prompt = (
            f"Сделай сборник из 6 коротких вымышленных, "
            f"матерных, ироничных цитат про {theme_list}. "
            f"Вплетай ники: {names_str}. "
            f"Стиль — грубоватый, смешной, про технику. "
            f"{randomization}"
        )
        system_prompt = (
            "Ты философ-абсурдист. Генери вдохновляющие и одновременно "
            "смешные цитаты. Каждую цитату на новой строке. "
            "Цитаты должны быть короткие, запоминающиеся и немного "
            "сумасшедшие."
        )

    elif mode == "story":
        # Генерируем историю с рандомным сценарием
        scenario_template = random.choice(STORY_SCENARIOS)
        themes_sample = random.sample(
            STORY_THEMES,
            min(3, len(STORY_THEMES))
        )
        users_sample = random.sample(
            names,
            min(3, len(names))
        )

        # Форматируем сценарий
        scenario = scenario_template.format(
            theme1=themes_sample[0],
            theme2=themes_sample[1] if len(themes_sample) > 1
            else themes_sample[0],
            theme3=themes_sample[2] if len(themes_sample) > 2
            else themes_sample[0],
            user1=f"@{users_sample[0]}",
            user2=f"@{users_sample[1]}" if len(users_sample) > 1
            else f"@{users_sample[0]}",
            user3=f"@{users_sample[2]}" if len(users_sample) > 2
            else f"@{users_sample[0]}",
        )

        randomization = _add_creative_randomization("story")
        prompt = (
            f"Напиши короткую абсурдную историю "
            f"(120-200 слов) про чат: {scenario}. "
            f"Используй отсылки к разгону, железу. "
            f"Грубо, но без оскорблений по признакам. "
            f"{randomization}"
        )
        system_prompt = (
            "Ты безумный сказочник. Генери абсурдные и смешные истории. "
            "Используй много юмора, неожиданных поворотов и странных "
            "персонажей. Историю пиши в виде связного текста, без номеров "
            "и маркеров."
        )

    elif mode == "joke":
        # Генерируем шутки
        themes = random.sample(
            QUOTE_THEMES,
            min(2, len(QUOTE_THEMES))
        )
        randomization = _add_creative_randomization("joke")
        prompt = (
            f"Напиши 4-5 смешных анекдотов про {', '.join(themes)}. "
            f"Каждый анекдот на новой строке. "
            f"Используй чёрный юмор, абсурд и неожиданные концовки. "
            f"{randomization}"
        )
        system_prompt = (
            "Ты комик. Генери смешные шутки и анекдоты. "
            "Каждую шутку на новой строке. "
            "Используй чёрный юмор, абсурд и неожиданные концовки."
        )

    else:  # poem
        # Генерируем стихи
        themes = random.sample(
            STORY_THEMES,
            min(2, len(STORY_THEMES))
        )
        randomization = _add_creative_randomization("poem")
        prompt = (
            f"Напиши странный авангардный стих про {', '.join(themes)}. "
            f"Используй необычные рифмы и странные образы. "
            f"Стих должен быть читаем и забавен. "
            f"{randomization}"
        )
        system_prompt = (
            "Ты поэт-авангардист. Генери смешные и странные стихи. "
            "Используй необычные рифмы, странные образы и абсурдный юмор."
        )

    txt = await _ollama_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ], temperature=0.9)

    # Форматируем вывод в зависимости от типа
    if mode == "story":
        formatted = _format_story(txt)
    elif mode == "quotes":
        formatted = _format_quotes(txt)
    else:
        formatted = txt

    return formatted + _disclaimer()
