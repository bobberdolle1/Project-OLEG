"""Игровые механики и команды."""

import logging
import random
from datetime import datetime, timedelta
import io
from aiogram import Router, Bot
from aiogram.types import Message, BufferedInputFile
from aiogram import F
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat, Wallet
from app.services.achievements import check_and_award_achievements
from app.services.quests import check_and_update_quests
from app.services.profile import get_full_user_profile
from app.services.game_engine import game_engine
from app.services.leagues import league_service, League
from app.services.profile_generator import profile_generator, ProfileData
from app.services.tournaments import tournament_service, TournamentDiscipline
from app.services.state_manager import state_manager
from app.services.sparkline import sparkline_generator
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Справка по играм
GAMES_HELP = """
🎮 <b>Мини-игры Олега — Полный гайд</b>

<b>📏 /grow — Выращивание</b>
Увеличь свой "размер" на 1-20 см.
• Кулдаун: 12-24 часа (рандом)
• Чем больше размер — тем выше ранг
• Пример: <code>/grow</code>

<b>🔫 /roulette — Русская рулетка</b>
Крути барабан, испытай удачу!
• 1/6 шанс "выстрела" — теряешь 50 очков
• 5/6 шанс выжить — получаешь 10 очков
• Пример: <code>/roulette</code>

<b>🪙 /coinflip — Монетка</b>
Ставь на орла или решку!
• 50/50 вероятность
• Выигрыш: удвоение ставки
• Примеры:
  <code>/coinflip 50 орёл</code> — ставка 50 на орла
  <code>/coinflip 100 решка</code> — ставка 100 на решку
  <code>/coinflip 50 heads</code> — английский вариант

<b>⚔️ /challenge — PvP с согласием</b>
Вызови другого игрока на дуэль!
• Соперник должен принять вызов
• Ставки списываются только при согласии
• Таймаут: 5 минут
• Пример: <code>/challenge @username 100</code>

<b>⚔️ /pvp — Быстрая дуэль</b>
Сразись с другим игроком!
• Победитель забирает 10-30% размера проигравшего
• Победа: +5 репутации, поражение: -2
• Примеры:
  <code>/pvp @username</code> — по нику
  Или ответь на сообщение соперника и напиши <code>/pvp</code>

<b>🎰 /casino — Слоты</b>
Крути барабаны, выигрывай монеты!
• Ставка: 1-1000 монет (по умолчанию 10)
• 3 одинаковых = x5 (джекпот!)
• 2 одинаковых = x2
• Примеры:
  <code>/casino</code> — ставка 10
  <code>/casino 100</code> — ставка 100

<b>🏆 /top — Топ игроков</b>
Показывает топ-10 по размеру.

<b>⭐ /top_rep — Топ по репутации</b>
Топ-10 по репутации (растёт от побед).

<b>👤 /profile — Твой профиль</b>
Вся статистика: размер, ранг, монеты, победы.

<b>💡 Советы новичкам:</b>
1. Начни с /grow — получи первые сантиметры
2. /roulette — быстрый способ заработать (или потерять)
3. /coinflip — классика азарта
4. /challenge — честный PvP со ставками
5. Выполняй квесты (/quests) для бонусов

<i>Вопросы? Напиши "помоги с играми" — я объясню!</i>
"""

# Константы для баланса игр
GROW_MIN = 1
GROW_MAX = 20
GROW_COOLDOWN_MIN_HOURS = 12
GROW_COOLDOWN_MAX_HOURS = 24

CASINO_MIN_BET = 1
CASINO_MAX_BET = 1000
CASINO_DEFAULT_BET = 10

PVP_STEAL_MIN_PCT = 10
PVP_STEAL_MAX_PCT = 30

# Словарь рангов для игры /grow (ПИПИСОМЕТР 🍆)
RANKS = [
    # === МИКРОПИПИСЬКИ (0-10 см) ===
    (1, "Квантовый пупырышек"),
    (2, "Атом члена"),
    (3, "Клитор муравья"),
    (4, "Пиписька амёбы"),
    (5, "Хуинка"),
    (6, "Микрохуй"),
    (7, "Писюнчик бактерии"),
    (8, "Член инфузории"),
    (9, "Нанопенис"),
    (10, "Микрочлен"),

    # === МЕЛКИЕ ПИСЮНЫ (11-20 см) ===
    (11, "Пиписька первоклашки"),
    (12, "Детский писюн"),
    (13, "Несчастливый хуй"),
    (14, "Член-батарейка"),
    (15, "Огрызок хуя"),
    (16, "Писюн подростка"),
    (17, "Мизинчик в штанах"),
    (18, "Совершеннолетний микрочлен"),
    (19, "Почти не стыдно"),
    (20, "Двадцаточка! Уже что-то"),

    # === НАЧИНАЮЩИЕ ЧЛЕНЫ (21-30 см) ===
    (21, "Хуй-очко (21!)"),
    (22, "Два весёлых хуя"),
    (23, "Член Джордана"),
    (24, "Суточный стояк"),
    (25, "Четвертак в штанах"),
    (26, "Хуй рок-звезды"),
    (27, "Член клуба 27"),
    (28, "Лунный хуй"),
    (29, "Високосный член"),
    (30, "Тридцатник! Норм писюн"),

    # === ПОДРАСТАЮЩИЕ ХУИ (31-40 см) ===
    (31, "31 сантиметр счастья"),
    (32, "Битный хуй"),
    (33, "Член Христа"),
    (34, "Хуй по правилу 34"),
    (35, "Полтинник на двоих"),
    (36, "Хуй 6×6"),
    (37, "Температурный член"),
    (38, "38 попугаев в штанах"),
    (39, "Предсороковой хуй"),
    (40, "СОРОКОВНИК"),

    # === СРЕДНИЕ ЧЛЕНЫ (41-50 см) ===
    (41, "Хуй за сорок"),
    (42, "Ответ на всё (в штанах)"),
    (43, "Сорок три сантима"),
    (44, "Дабл-хуй"),
    (45, "Член-магнум"),
    (46, "Хромосомный хуй"),
    (47, "АК-47 в штанах"),
    (48, "Двухсуточный стояк"),
    (49, "Почти полтинник"),
    (50, "ПОЛТИННИК! Красавчик"),

    # === НОРМАЛЬНЫЕ ХУИ (51-60 см) ===
    (51, "Хуй из Зоны 51"),
    (52, "Колода хуёв"),
    (53, "Херовый номер"),
    (54, "Студийный член"),
    (55, "Скоростной хуй"),
    (56, "Пианинный член"),
    (57, "Кетчупный хуй"),
    (58, "Пенсионный член"),
    (59, "Предпенсионный хуй"),
    (60, "ШЕСТИДЕСЯТНИК"),

    # === УВАЖАЕМЫЕ ЧЛЕНЫ (61-70 см) ===
    (61, "Хуй-хайвей"),
    (62, "Мудрый член"),
    (63, "Кубический хуй"),
    (64, "Nintendo-член"),
    (65, "Бодрый пенсионный хуй"),
    (66, "Трасса 66 в штанах"),
    (67, "Хуй лета любви"),
    (68, "Революционный член"),
    (69, "🔥 НАЙС ХУЙ 🔥"),
    (70, "СЕМИДЕСЯТНИК"),

    # === АЛЬФА-ЧЛЕНЫ (71-80 см) ===
    (71, "Хуй вне зоны комфорта"),
    (72, "Рекордный член"),
    (73, "Умный хуй"),
    (74, "Тигриный член"),
    (75, "Три четверти метра хуя"),
    (76, "Тромбонный член"),
    (77, "Джекпот-хуй"),
    (78, "Виниловый член"),
    (79, "Предвосьмидесятый хуй"),
    (80, "ВОСЬМИДЕСЯТНИК"),

    # === ГИГАЧАД-ЧЛЕНЫ (81-90 см) ===
    (81, "Бинго-хуй!"),
    (82, "Миллениальный член"),
    (83, "Бодрый хуй"),
    (84, "Оруэлловский член"),
    (85, "Хуй из будущего"),
    (86, "Чернобыльский мутант-член"),
    (87, "Never gonna give хуй up"),
    (88, "Бесконечный хуй ∞"),
    (89, "Хуй, разрушивший стену"),
    (90, "ДЕВЯНОСТНИК"),

    # === СИГМА-ЧЛЕНЫ (91-100 см) ===
    (91, "Постсоветский хуй"),
    (92, "Олимпийский член"),
    (93, "Юрский хуй"),
    (94, "Гранжевый член"),
    (95, "Windows-хуй"),
    (96, "Покемон-член"),
    (97, "Титанический хуй"),
    (98, "Гугл-член"),
    (99, "Почти сотка хуя"),
    (100, "💯 СОТКА! МЕТРОВЫЙ ХУЙ 💯"),

    # === ЛЕГЕНДАРНЫЕ ХУИ (101-120 см) ===
    (102, "102 далматинца в штанах"),
    (104, "FM-хуй"),
    (106, "Сотка плюс"),
    (108, "Чёточный член"),
    (110, "110% хуя"),
    (112, "Экстренный хуй"),
    (114, "Элементарный член"),
    (116, "Сверхсотка"),
    (118, "Периодический хуй"),
    (120, "МЕТР ДВАДЦАТЬ ХУИЩА"),

    # === МИФИЧЕСКИЕ ЧЛЕНЫ (121-140 см) ===
    (122, "Мифический писюн"),
    (125, "Хуй с четвертью"),
    (128, "Бинарный член"),
    (130, "Чёртов хуй"),
    (133, "Скибиди-член"),
    (135, "Полтора метра почти"),
    (137, "L33T-хуй"),
    (140, "МЕТР СОРОК ХУИЩА"),

    # === ТИТАНИЧЕСКИЕ ХУИ (141-160 см) ===
    (142, "Пи-хуй"),
    (145, "Хуй ростом с тян"),
    (148, "Почти полтора метра"),
    (150, "🍆 ПОЛТОРА МЕТРА ХУИЩА 🍆"),
    (153, "Президентский член"),
    (155, "Наполеоновский хуй"),
    (158, "Хуй Месси"),
    (160, "МЕТР ШЕСТЬДЕСЯТ"),

    # === КОЛОССАЛЬНЫЕ ЧЛЕНЫ (161-180 см) ===
    (163, "Хуй среднего мужика"),
    (165, "Член твоей бывшей (шок)"),
    (168, "Голливудский хуй"),
    (170, "МЕТР СЕМЬДЕСЯТ ХУИЩА"),
    (173, "Рэперский член"),
    (175, "Нормисный хуй"),
    (178, "Илоновский член"),
    (180, "🔥 МЕТР ВОСЕМЬДЕСЯТ 🔥"),

    # === ГИГАНТСКИЕ ХУИ (181-200 см) ===
    (183, "Шестифутовый хуй"),
    (185, "Тиндер-член (минимум)"),
    (188, "Президентский хуй"),
    (190, "МЕТР ДЕВЯНОСТО"),
    (193, "Трамповский член"),
    (195, "Арнольдовский хуй"),
    (198, "Почти два метра"),
    (200, "🏆 ДВА МЕТРА ХУИЩА 🏆"),

    # === МЕГАХУИ (201-250 см) ===
    (205, "Шаковский хуй"),
    (210, "Баскетбольный член"),
    (215, "Хуй в дверной проём"),
    (220, "Йао Мин в штанах"),
    (225, "Два с четвертью метра"),
    (230, "Хуй-шкаф"),
    (235, "Хрущёвский потолок-член"),
    (240, "ДВА СОРОК ХУИЩА"),
    (245, "Жирафий писюн"),
    (250, "🍆 ДВА ПЯТЬДЕСЯТ 🍆"),

    # === УЛЬТРАХУИ (251-300 см) ===
    (255, "Ультрахуй"),
    (260, "Сталинский член"),
    (265, "Слоновий хуй"),
    (270, "Рекордный член"),
    (275, "Хуй Роберта Уодлоу"),
    (280, "ДВА ВОСЕМЬДЕСЯТ"),
    (285, "Жирафий член"),
    (290, "Почти три метра хуя"),
    (295, "Трёшка на подходе"),
    (300, "🔥 ТРИ МЕТРА ХУИЩА 🔥"),

    # === КОСМИЧЕСКИЕ ХУИ (301-400 см) ===
    (310, "Слоновий хуище"),
    (320, "Три двадцать хуя"),
    (330, "Жирафий хуй"),
    (340, "Три сорок члена"),
    (350, "Три пятьдесят хуища"),
    (360, "Полный оборот хуя"),
    (370, "Три семьдесят"),
    (380, "Три восемьдесят"),
    (390, "Почти четыре метра"),
    (400, "🚀 ЧЕТЫРЕ МЕТРА ХУИЩА 🚀"),

    # === ПЛАНЕТАРНЫЕ ЧЛЕНЫ (401-500 см) ===
    (410, "Тираннозавровый хуй"),
    (420, "🌿 BLAZE IT ХУЙ 🌿"),
    (430, "Четыре тридцать"),
    (440, "Четыре сорок хуя"),
    (450, "Четыре пятьдесят"),
    (460, "Четыре шестьдесят"),
    (470, "Четыре семьдесят"),
    (480, "Четыре восемьдесят"),
    (490, "Почти полтысячи хуя"),
    (500, "💎 ПОЛТЫСЯЧИ ХУИЩА 💎"),

    # === ЗВЁЗДНЫЕ ХУИ (501-750 см) ===
    (520, "Пять двадцать хуя"),
    (540, "Пять сорок члена"),
    (560, "Пять шестьдесят"),
    (580, "Пять восемьдесят хуища"),
    (600, "⭐ ШЕСТЬ МЕТРОВ ХУИЩА ⭐"),
    (630, "Шесть тридцать"),
    (666, "😈 ДЬЯВОЛЬСКИЙ ХУЙ 😈"),
    (690, "🔥 НАЙС ×10 ХУЙ 🔥"),
    (700, "СЕМЬ МЕТРОВ ЧЛЕНА"),
    (750, "Семь пятьдесят хуя"),

    # === ГАЛАКТИЧЕСКИЕ ЧЛЕНЫ (751-1000 см) ===
    (777, "🎰 ДЖЕКПОТ-ХУЙ 🎰"),
    (800, "ВОСЕМЬ МЕТРОВ ХУИЩА"),
    (850, "Восемь пятьдесят"),
    (900, "ДЕВЯТЬ МЕТРОВ ЧЛЕНА"),
    (911, "Экстренный хуй"),
    (950, "Девять пятьдесят"),
    (999, "Один до тысячи хуя"),
    (1000, "🔥🔥🔥 ТЫСЯЧА СМ ХУИЩА 🔥🔥🔥"),

    # === ВСЕЛЕНСКИЕ ХУИ (1001-2000 см) ===
    (1100, "Тысяча сто хуя"),
    (1200, "Тысяча двести члена"),
    (1234, "Раз-два-три-четыре хуя"),
    (1300, "Тысяча триста"),
    (1337, "L33T ХУЙ H4X0R"),
    (1400, "Тысяча четыреста"),
    (1488, "Тот самый хуй"),
    (1500, "Полторы тысячи хуища"),
    (1600, "Тысяча шестьсот"),
    (1700, "Тысяча семьсот"),
    (1800, "Тысяча восемьсот"),
    (1900, "Тысяча девятьсот"),
    (2000, "🏆 ДВЕ ТЫСЯЧИ СМ ХУИЩА 🏆"),

    # === МУЛЬТИВСЕЛЕНСКИЕ ЧЛЕНЫ (2001-5000 см) ===
    (2100, "Космический хуй одиссеи"),
    (2222, "Ангельский член"),
    (2500, "Две с половиной тысячи"),
    (3000, "ТРИ ТЫСЯЧИ ХУИЩА"),
    (3333, "Тройной хуй"),
    (3500, "Три с половиной тысячи"),
    (4000, "ЧЕТЫРЕ ТЫСЯЧИ ЧЛЕНА"),
    (4200, "🌿 BLAZE IT ×10 ХУЙ 🌿"),
    (4444, "Четыре четвёрки хуя"),
    (4500, "Четыре с половиной"),
    (5000, "💎 ПЯТЬ ТЫСЯЧ ХУИЩА 💎"),

    # === БОЖЕСТВЕННЫЕ ХУИ (5001-10000 см) ===
    (5500, "Пять с половиной тысяч"),
    (6000, "ШЕСТЬ ТЫСЯЧ ЧЛЕНА"),
    (6666, "😈 ЧИСЛО ЗВЕРЯ ХУЙ 😈"),
    (6900, "🔥 НАЙС ×100 ХУЙ 🔥"),
    (7000, "СЕМЬ ТЫСЯЧ ХУИЩА"),
    (7777, "🎰 МЕГА ДЖЕКПОТ-ЧЛЕН 🎰"),
    (8000, "ВОСЕМЬ ТЫСЯЧ"),
    (8888, "Китайский удачливый хуй"),
    (9000, "IT'S OVER 9000 ХУЯ!!!"),
    (9999, "Максимум RPG хуя"),
    (10000, "👑 ДЕСЯТЬ ТЫСЯЧ СМ ХУИЩА 👑"),

    # === ЗАПРЕДЕЛЬНЫЕ ЧЛЕНЫ (10001-50000 см) ===
    (12000, "Двенадцать тысяч хуя"),
    (13337, "ЭЛИТНЫЙ L33T ХУЙ"),
    (15000, "Пятнадцать тысяч"),
    (20000, "Двадцать тысяч хуища"),
    (25000, "Двадцать пять тысяч"),
    (30000, "Тридцать тысяч члена"),
    (40000, "Сорок тысяч хуя"),
    (42000, "Ответ на всё ×1000 хуй"),
    (50000, "💎 ПОЛСТА ТЫСЯЧ ХУИЩА 💎"),

    # === АБСОЛЮТНЫЕ ХУИ (50001-100000 см) ===
    (60000, "Шестьдесят тысяч хуя"),
    (69000, "🔥 НАЙС ×1000 ХУЙ 🔥"),
    (70000, "Семьдесят тысяч"),
    (77777, "🎰 УЛЬТРА ДЖЕКПОТ-ХУЙ 🎰"),
    (80000, "Восемьдесят тысяч"),
    (88888, "Пять восьмёрок хуя"),
    (90000, "Девяносто тысяч"),
    (99999, "Почти сотка тысяч хуища"),
    (100000, "🏆 СТО ТЫСЯЧ СМ ХУИЩА 🏆"),

    # === ТРАНСЦЕНДЕНТНЫЕ ЧЛЕНЫ (100001+ см) ===
    (150000, "Полторы сотни тысяч хуя"),
    (200000, "Двести тысяч члена"),
    (250000, "Четверть миллиона хуища"),
    (300000, "Триста тысяч хуя"),
    (420000, "🌿 BLAZE IT ×1000 ХУЙ 🌿"),
    (500000, "ПОЛМИЛЛИОНА ХУИЩА"),
    (690000, "🔥 НАЙС ×10000 ХУЙ 🔥"),
    (750000, "Три четверти миллиона"),
    (900000, "Девятьсот тысяч хуя"),
    (999999, "Почти миллион хуища"),
    (1000000, "👑👑👑 МИЛЛИОН СМ ХУИЩА 👑👑👑"),

    # === ФИНАЛЬНЫЕ БОССЫ-ЧЛЕНЫ ===
    (1337000, "L33T МИЛЛИОНЕР-ХУЙ"),
    (2000000, "Два миллиона хуя"),
    (5000000, "Пять миллионов члена"),
    (6900000, "🔥 НАЙС ×100000 ХУЙ 🔥"),
    (10000000, "Десять миллионов хуища"),
    (69000000, "🔥🔥🔥 НАЙС ×1000000 ХУЙ 🔥🔥🔥"),
    (100000000, "Сто миллионов хуя"),
    (420000000, "🌿 BLAZE IT ×1000000 ХУЙ 🌿"),
    (1000000000, "🌟 МИЛЛИАРД СМ ХУИЩА 🌟"),
    (float('inf'), "∞ БЕСКОНЕЧНЫЙ ХУЙ ∞")
]


# Russian to English coinflip choice mapping (Requirements 8.1)
COINFLIP_CHOICE_MAP = {
    # Russian variants
    "орёл": "heads",
    "орел": "heads",  # Without ё
    "решка": "tails",
    # English variants (pass through)
    "heads": "heads",
    "tails": "tails",
    "head": "heads",
    "tail": "tails",
}


def map_coinflip_choice(choice: str) -> str:
    """
    Map Russian or English coinflip choice to internal heads/tails.
    
    Requirements 8.1: Accept Russian input ("орёл"/"решка")
    
    Args:
        choice: User's choice in Russian or English
        
    Returns:
        Normalized choice: "heads" or "tails", or original if not recognized
    """
    if choice is None:
        return ""
    return COINFLIP_CHOICE_MAP.get(choice.lower().strip(), choice)


def get_rank_by_size(size_cm: int) -> str:
    """
    Возвращает ранг по размеру "пиписи".

    Args:
        size_cm: Размер в сантиметрах

    Returns:
        Название ранга
    """
    for threshold, rank_name in RANKS:
        if size_cm <= threshold:
            return rank_name
    return RANKS[-1][1]  # Возвращаем последний ранг, если размер больше всех порогов


async def ensure_user(tg_user) -> User:
    """
    Убедиться, что пользователь существует в БД.

    Если пользователь не существует, создает записи:
    - User (базовая информация)
    - GameStat (статистика игр, "размер")
    - Wallet (виртуальная валюта, начальный баланс 100)

    Args:
        tg_user: Объект пользователя Telegram

    Returns:
        User объект
    """
    async_session = get_session()
    async with async_session() as session:
        # Поиск существующего пользователя
        res = await session.execute(
            select(User).where(User.tg_user_id == tg_user.id)
        )
        user = res.scalars().first()
        if not user:
            user = User(
                tg_user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            session.add(user)
            await session.flush()

        # Убедиться в наличии GameStat
        res2 = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == tg_user.id
            )
        )
        gs = res2.scalars().first()
        if not gs:
            gs = GameStat(
                user_id=user.id,
                tg_user_id=tg_user.id,
                username=tg_user.username,
                size_cm=0
            )
            session.add(gs)
        else:
            # Обновить никнейм если изменился
            gs.username = tg_user.username

        # Убедиться в наличии Wallet
        res3 = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        w = res3.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)

        await session.commit()
        return user


@router.message(Command("games_help"))
async def cmd_games_help(msg: Message):
    """Команда /games_help — справка по всем мини-играм.
    
    Note: /games command is now handled by game_hub.py for the Game Hub UI.
    """
    await msg.reply(GAMES_HELP, parse_mode="HTML")
    logger.info(f"Games help requested by @{msg.from_user.username or msg.from_user.id}")


def update_grow_history(gs: GameStat, gain: int) -> None:
    """
    Update grow_history with the latest growth data.
    
    Keeps last 7 days of growth data for sparkline generation.
    Requirements: 7.4
    
    Args:
        gs: GameStat object to update
        gain: The amount of growth in this session
    """
    from datetime import date
    
    today = date.today().isoformat()
    
    # Initialize history if None
    if gs.grow_history is None:
        gs.grow_history = []
    
    # Create a mutable copy of the history
    history = list(gs.grow_history) if gs.grow_history else []
    
    # Check if we already have an entry for today
    today_entry = None
    for entry in history:
        if entry.get("date") == today:
            today_entry = entry
            break
    
    if today_entry:
        # Update existing entry for today
        today_entry["change"] = today_entry.get("change", 0) + gain
        today_entry["size"] = gs.size_cm
    else:
        # Add new entry for today
        history.append({
            "date": today,
            "size": gs.size_cm,
            "change": gain
        })
    
    # Keep only last 7 days
    history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)[:7]
    history = sorted(history, key=lambda x: x.get("date", ""))  # Sort chronologically
    
    gs.grow_history = history


@router.message(F.text.startswith("/grow"))
async def cmd_grow(msg: Message):
    """
    Команда /grow — увеличить "пиписю".

    Случайное увеличение размера (1-20 см) с кулдауном.
    """
    from app.services.inventory import inventory_service, ItemType as InvItemType
    
    async_session = get_session()
    user = await ensure_user(msg.from_user) # Get the User object here
    
    # Check if PP_CAGE is active (Requirements 10.4)
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    if await inventory_service.has_active_item(user_id, chat_id, InvItemType.PP_CAGE):
        return await msg.reply(
            "🔒 Клетка не даёт расти! Сними её через /inventory или подожди пока истечёт."
        )
    
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == msg.from_user.id
            )
        )
        gs = res.scalars().first()
        now = utc_now()
        # Ensure both datetimes are comparable (handle naive vs aware)
        next_grow = gs.next_grow_at
        if next_grow and next_grow.tzinfo is None:
            from datetime import timezone
            next_grow = next_grow.replace(tzinfo=timezone.utc)
        if next_grow and next_grow > now:
            delta = next_grow - now
            hours, remainder = divmod(
                int(delta.total_seconds()), 3600
            )
            minutes = remainder // 60
            return await msg.reply(
                f"Подожди ещё {hours}ч {minutes}м, "
                f"не спеши, чемпион."
            )
        gain = random.randint(GROW_MIN, GROW_MAX)
        cooldown_hours = random.randint(
            GROW_COOLDOWN_MIN_HOURS, GROW_COOLDOWN_MAX_HOURS
        )
        gs.size_cm += gain
        gs.grow_count += 1
        gs.next_grow_at = now + timedelta(hours=cooldown_hours)
        
        # Update grow history for sparkline (Requirements 7.4)
        update_grow_history(gs, gain)
        
        await session.commit()

        new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "grow")
        for achievement in new_achievements:
            await msg.answer(f"🎉 Новое достижение: {achievement.name}!")
        
        updated_quests = await check_and_update_quests(session, user, "grow")
        for quest in updated_quests:
            await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

        # Update tournament score for grow (Requirement 10.1)
        try:
            await tournament_service.update_score(
                user_id=msg.from_user.id,
                discipline=TournamentDiscipline.GROW,
                delta=gain,
                username=msg.from_user.username
            )
        except Exception as e:
            logger.warning(f"Failed to update tournament score: {e}")

        # Получить рейтинг
        res2 = await session.execute(
            select(GameStat).order_by(GameStat.size_cm.desc())
        )
        all_stats = res2.scalars().all()
        rank = next(
            (i + 1 for i, s in enumerate(all_stats)
             if s.tg_user_id == msg.from_user.id),
            1
        )
        # Получить ранг по размеру
        size_rank = get_rank_by_size(gs.size_cm)
        
        # Generate sparkline if we have enough history (Requirements 7.1)
        sparkline_bytes = None
        if gs.grow_history and len(gs.grow_history) >= 2:
            try:
                sparkline_bytes = sparkline_generator.generate(gs.grow_history)
            except Exception as e:
                logger.warning(f"Failed to generate sparkline: {e}")
        
        reply_text = (
            f"+{gain} см 📈\n"
            f"Текущий: {gs.size_cm} см\n"
            f"Ранг: {size_rank}\n"
            f"Место: #{rank}/{len(all_stats)}\n"
            f"Кулдаун: {cooldown_hours}ч\n"
            f"📋 /games"
        )
        
        # Send with sparkline image if available (Requirements 7.1)
        if sparkline_bytes:
            photo = BufferedInputFile(sparkline_bytes, filename="sparkline.png")
            await msg.reply_photo(photo=photo, caption=reply_text)
        else:
            await msg.reply(reply_text)
        
        logger.info(
            f"Grow: @{msg.from_user.username} "
            f"+{gain} cm (total: {gs.size_cm}, rank: {size_rank})"
        )


# Special titles for top rankings (Requirements 7.2, 7.3)
TITLE_LARGEST = "🧠 Гигант мысли"
TITLE_SMALLEST = "🔬 Нано-технолог"


def get_special_title(rank: int, total: int, is_largest: bool = False, is_smallest: bool = False) -> str:
    """
    Get special title for top rankings.
    
    Requirements: 7.2, 7.3
    
    Args:
        rank: Player's rank (1-based)
        total: Total number of players
        is_largest: True if this is the largest size
        is_smallest: True if this is the smallest size
        
    Returns:
        Special title string or empty string
    """
    if is_largest:
        return f" {TITLE_LARGEST}"
    if is_smallest:
        return f" {TITLE_SMALLEST}"
    return ""


@router.message(F.text.startswith("/top"))
async def cmd_top(msg: Message):
    """
    Команда /top — показать топ-10 игроков по размеру.
    
    Includes special titles:
    - "Гигант мысли" for the largest (Requirements 7.2)
    - "Нано-технолог" for the smallest (Requirements 7.3)
    """
    async_session = get_session()
    async with async_session() as session:
        # Get top 10 by size (descending)
        res = await session.execute(select(GameStat).order_by(GameStat.size_cm.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Никто не растил свою гордость.")
        
        # Get the smallest player for "Нано-технолог" title (Requirements 7.3)
        res_smallest = await session.execute(
            select(GameStat).where(GameStat.size_cm > 0).order_by(GameStat.size_cm.asc()).limit(1)
        )
        smallest = res_smallest.scalars().first()
        smallest_id = smallest.tg_user_id if smallest else None
        
        lines = []
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            size_rank = get_rank_by_size(s.size_cm)
            
            # Add special titles (Requirements 7.2, 7.3)
            special_title = ""
            if i == 1:  # Largest player gets "Гигант мысли"
                special_title = get_special_title(i, len(top10), is_largest=True)
            elif s.tg_user_id == smallest_id and s.size_cm > 0:  # Smallest gets "Нано-технолог"
                special_title = get_special_title(i, len(top10), is_smallest=True)
            
            lines.append(f"{i}. {name}: {s.size_cm} см ({size_rank}){special_title}")
        
        # Add smallest player info if not in top 10 (Requirements 7.3)
        smallest_line = ""
        if smallest and smallest.tg_user_id not in [s.tg_user_id for s in top10]:
            smallest_name = smallest.username or str(smallest.tg_user_id)
            smallest_line = f"\n\n{TITLE_SMALLEST}: {smallest_name} ({smallest.size_cm} см)"
        
        await msg.reply(
            "🏆 Топ-10:\n" + "\n".join(lines) + smallest_line +
            "\n📋 /games"
        )


@router.message(F.text.startswith("/top_rep"))
async def cmd_top_rep(msg: Message):
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(select(GameStat).order_by(GameStat.reputation.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Ни у кого нет репутации.")
        lines = []
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            lines.append(f"{i}. {name}: {s.reputation} репутации")
        await msg.reply(
            "⭐ Топ-10 по репутации:\n" + "\n".join(lines) +
            "\n📋 /games"
        )


@router.message(F.text.startswith("/profile"))
async def cmd_profile(msg: Message, bot: Bot):
    """
    Displays the user's comprehensive profile data as a generated image.
    
    Generates a PNG profile card with avatar, username, league badge, ELO, and stats.
    **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        user, game_stat, wallet, user_achievements, user_quests, guild_memberships, duo_team = \
            await get_full_user_profile(session, user.tg_user_id)

        if not user:
            return await msg.reply("Ваш профиль не найден. Пожалуйста, начните играть (например, /grow).")

        # Get league status (Requirement 12.2)
        try:
            league_status = await league_service.get_status(user.tg_user_id, session)
            elo = league_status.elo
            league = league_status.league
        except Exception as e:
            logger.warning(f"Failed to get league status: {e}")
            elo = 1000
            league = League.SCRAP
        
        # Try to get user avatar (Requirement 12.2)
        avatar_bytes = None
        try:
            photos = await bot.get_user_profile_photos(msg.from_user.id, limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]  # Get largest size
                file = await bot.get_file(photo.file_id)
                avatar_data = io.BytesIO()
                await bot.download_file(file.file_path, avatar_data)
                avatar_bytes = avatar_data.getvalue()
        except Exception as e:
            logger.warning(f"Failed to get avatar for user {msg.from_user.id}: {e}")
        
        # Calculate wins/losses (using pvp_wins as wins, estimate losses)
        wins = game_stat.pvp_wins
        # Estimate losses based on reputation (each loss = -2 rep, each win = +5 rep)
        # This is an approximation since we don't track losses directly
        losses = max(0, (wins * 5 - game_stat.reputation) // 2) if game_stat.reputation < wins * 5 else 0
        
        # Create profile data (Requirement 12.2)
        profile_data = ProfileData(
            username=user.username or user.first_name or f"User {user.tg_user_id}",
            avatar_bytes=avatar_bytes,
            elo=elo,
            league=league,
            wins=wins,
            losses=losses,
            size_cm=game_stat.size_cm,
            reputation=game_stat.reputation,
            balance=wallet.balance if wallet else 0,
            grow_count=game_stat.grow_count,
            casino_jackpots=game_stat.casino_jackpots,
        )
        
        # Generate profile image (Requirement 12.1, 12.3)
        try:
            image_bytes = profile_generator.generate(profile_data)
            photo = BufferedInputFile(image_bytes, filename="profile.png")
            
            # Build caption with additional info
            caption_parts = []
            
            if guild_memberships:
                guild_name = guild_memberships[0].guild.name
                guild_role = guild_memberships[0].role
                caption_parts.append(f"🛡️ Гильдия: {guild_name} ({guild_role})")
            
            if duo_team:
                partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
                caption_parts.append(f"🤝 Дуэт: @{partner.username or str(partner.tg_user_id)}")
            
            if user_achievements:
                achievements_text = ", ".join(ua.achievement.name for ua in user_achievements[:3])
                if len(user_achievements) > 3:
                    achievements_text += f" (+{len(user_achievements) - 3})"
                caption_parts.append(f"🏆 {achievements_text}")
            
            caption_parts.append("📋 /games")
            
            caption = "\n".join(caption_parts) if caption_parts else None
            
            # Send profile image (Requirement 12.4)
            await msg.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Failed to generate profile image: {e}")
            # Fallback to text profile
            await _send_text_profile(msg, user, game_stat, wallet, league, elo, 
                                    guild_memberships, duo_team, user_achievements, user_quests)


async def _send_text_profile(msg: Message, user, game_stat, wallet, league, elo,
                             guild_memberships, duo_team, user_achievements, user_quests):
    """Fallback text profile when image generation fails."""
    size_rank = get_rank_by_size(game_stat.size_cm)
    
    profile_text = (
        f"📈 <b>Ваш профиль, {user.username or user.first_name}:</b>\n"
        f"📏 Размер: {game_stat.size_cm} см\n"
        f"🏆 Ранг: {size_rank}\n"
        f"🏅 Репутация: {game_stat.reputation}\n"
        f"💰 Баланс: {wallet.balance if wallet else 0} монет\n"
        f"⚔️ Побед в PvP: {game_stat.pvp_wins}\n"
        f"🌱 Выращиваний: {game_stat.grow_count}\n"
        f"🎰 Джекпотов в казино: {game_stat.casino_jackpots}\n"
        f"\n🎖️ <b>Лига:</b> {league.display_name}\n"
        f"📊 ELO: {elo}\n"
    )

    if guild_memberships:
        guild_name = guild_memberships[0].guild.name
        guild_role = guild_memberships[0].role
        profile_text += f"🛡️ Гильдия: {guild_name} ({guild_role})\n"
    
    if duo_team:
        partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
        profile_text += f"🤝 Дуэт: @{partner.username or str(partner.tg_user_id)} (Рейтинг: {duo_team.stats.rating})\n"

    if user_achievements:
        profile_text += "\n🏆 <b>Достижения:</b>\n"
        for ua in user_achievements:
            profile_text += f"  - {ua.achievement.name}\n"
    
    if user_quests:
        profile_text += "\n📜 <b>Активные квесты:</b>\n"
        for uq in user_quests:
            status = "Выполнено" if uq.completed_at else f"Прогресс: {uq.progress}/{uq.quest.target_value}"
            profile_text += f"  - {uq.quest.name} ({status})\n"

    profile_text += "\n📋 /games"
    await msg.reply(profile_text, parse_mode="HTML")


@router.message(F.text.startswith("/pvp"))
async def cmd_pvp(msg: Message):
    """
    Redirect /pvp to /challenge for proper consent-based PvP.
    
    Old /pvp worked without opponent consent which was unfair.
    Now redirects to /challenge which requires acceptance.
    """
    # Parse arguments to pass to challenge
    parts = (msg.text or "").split()
    
    # Build help message
    help_text = (
        "⚔️ <b>PvP Дуэли</b>\n\n"
        "Используй /challenge для честных дуэлей:\n\n"
        "• <code>/challenge @username</code> — вызов игрока (ждёт согласия)\n"
        "• <code>/challenge @username 100</code> — вызов со ставкой\n"
        "• <code>/challenge</code> — бой с Олегом (ИИ)\n\n"
        "Соперник должен принять вызов кнопкой ✅\n"
        "Таймаут: 5 минут"
    )
    
    # If user specified opponent, suggest the command
    if len(parts) >= 2:
        opponent = parts[1]
        bet = parts[2] if len(parts) >= 3 else ""
        help_text += f"\n\n💡 Попробуй: <code>/challenge {opponent} {bet}</code>"
    
    await msg.reply(help_text, parse_mode="HTML")


SLOTS = ["🍒", "🍋", "🔧", "🧰", "🎮", "🔥"]


def roll_slots():
    return [random.choice(SLOTS) for _ in range(3)]


def slots_payout(reel: list[str]) -> int:
    # 3 same -> x5; 2 same -> x2; else 0
    if reel[0] == reel[1] == reel[2]:
        return 5
    if reel[0] == reel[1] or reel[1] == reel[2] or reel[0] == reel[2]:
        return 2
    return 0


@router.message(F.text.startswith("/casino"))
async def cmd_casino(msg: Message):
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    async_session = get_session()
    user = await ensure_user(msg.from_user)
    parts = (msg.text or "").split()
    bet = 10
    if len(parts) >= 2:
        try:
            bet = int(parts[1])
        except Exception:
            pass
    bet = max(1, min(1000, bet))
    async with async_session() as session:
        # load wallet
        resw = await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        w = resw.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)
            await session.flush()
        if w.balance < bet:
            return await msg.reply(f"У тебя {w.balance}, а ставка {bet}. Бедно живёшь. Пополнись победами в /pvp.")
        w.balance -= bet
        reel = roll_slots()
        mult = slots_payout(reel)
        win = bet * mult
        w.balance += win

        gs_res = await session.execute(select(GameStat).where(GameStat.user_id == user.id))
        gs = gs_res.scalars().first()

        board = " ".join(reel)
        if mult == 5:
            gs.casino_jackpots += 1
            text = (
                f"🎰 {board}\n"
                f"🎉 Джекпот! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        elif mult == 2:
            text = (
                f"🎰 {board}\n"
                f"✨ Норм, удвоил! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        else:
            text = (
                f"🎰 {board}\n"
                f"😢 Мимо, дружище\n"
                f"💰 Баланс: {w.balance}\n"
                f"📋 /games"
            )
        
        await session.commit()

        if mult == 5: # Only check for achievements if a jackpot occurred
            new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "casino_jackpot")
            for achievement in new_achievements:
                await msg.answer(f"🎉 Новое достижение: {achievement.name}!")
            
            updated_quests = await check_and_update_quests(session, user, "casino_jackpot")
            for quest in updated_quests:
                await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

        
        await msg.reply(text)


@router.message(Command("roulette"))
async def cmd_roulette(msg: Message):
    """
    Команда /roulette — Русская рулетка с анимацией.
    
    Использование:
      /roulette - стандартный режим (фиксированные очки)
      /roulette <ставка> - режим ставок (ставка на выживание)
    
    Игрок крутит барабан с 1 пулей в 6 камерах.
    - Выстрел (1/6): теряет очки/ставку
    - Выживание (5/6): получает очки/выигрыш
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    """
    import asyncio
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Parse bet amount from command (Requirements 5.4)
    parts = (msg.text or "").split()
    bet_amount = 0
    if len(parts) >= 2:
        try:
            bet_amount = int(parts[1])
            if bet_amount < 0:
                bet_amount = 0
        except ValueError:
            pass
    
    # Animation Phase 1: "Заряжаем..." (Requirements 5.1)
    bet_info = f"\n💰 Ставка: {bet_amount} очков" if bet_amount > 0 else ""
    anim_msg = await msg.reply(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"🔄 Заряжаем барабан...",
        parse_mode="HTML"
    )
    
    await asyncio.sleep(2)
    
    # Animation Phase 2: "Крутим..." (Requirements 5.1)
    await anim_msg.edit_text(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"🎰 Крутим барабан...",
        parse_mode="HTML"
    )
    
    await asyncio.sleep(2)
    
    # Play roulette using the game engine (Requirements 5.4, 5.5)
    result = game_engine.play_roulette(user_id, chat_id, bet_amount)
    
    # Handle errors (insufficient balance, etc.)
    if not result.success:
        await anim_msg.edit_text(
            f"🔫 <b>Русская рулетка</b>\n\n"
            f"❌ {result.message}",
            parse_mode="HTML"
        )
        return
    
    # Log the result
    logger.info(
        f"Roulette: @{msg.from_user.username or user_id} - "
        f"{'SHOT' if result.shot else 'SURVIVED'}, bet={bet_amount}, "
        f"change: {result.points_change}, balance: {result.new_balance}"
    )
    
    # Update tournament score for roulette survival (Requirement 10.1)
    if not result.shot:  # Only count survivals
        try:
            await tournament_service.update_score(
                user_id=user_id,
                discipline=TournamentDiscipline.ROULETTE,
                delta=1,  # 1 point per survival
                username=msg.from_user.username
            )
        except Exception as e:
            logger.warning(f"Failed to update tournament score: {e}")
    
    # Animation Phase 3: Result with dramatic effect (Requirements 5.2, 5.3)
    if result.shot:
        # Shot result (Requirements 5.2)
        result_emoji = "💥 БАХ! 💀"
    else:
        # Survival result (Requirements 5.3)
        result_emoji = "🔫 Щёлк... 😅"
    
    # Final message with result
    await anim_msg.edit_text(
        f"🔫 <b>Русская рулетка</b>{bet_info}\n\n"
        f"{result_emoji}\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"📋 /games",
        parse_mode="HTML"
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(msg: Message):
    """
    Команда /coinflip — Подбрасывание монетки.
    
    Использование: /coinflip <ставка> <орёл|решка|heads|tails>
    Примеры:
      /coinflip 50 heads
      /coinflip 100 tails
      /coinflip 50 орёл
      /coinflip 100 решка
    
    - 50/50 вероятность
    - Выигрыш: удвоение ставки
    - Проигрыш: потеря ставки
    
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Parse command arguments
    parts = (msg.text or "").split()
    
    # Default values
    bet_amount = 10
    choice = None
    
    # Parse bet amount and choice
    if len(parts) >= 2:
        try:
            bet_amount = int(parts[1])
        except ValueError:
            # Maybe they put choice first?
            choice = parts[1].lower()
    
    if len(parts) >= 3:
        choice = parts[2].lower()
    elif len(parts) == 2 and choice is None:
        # Only bet amount provided, no choice
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;орёл|решка&gt;</code>\n"
            "Примеры:\n"
            "  <code>/coinflip 50 орёл</code>\n"
            "  <code>/coinflip 100 решка</code>\n"
            "  <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: орёл (heads) или решка (tails)",
            parse_mode="HTML"
        )
    
    # Map Russian input to internal heads/tails (Requirements 8.1)
    choice = map_coinflip_choice(choice)
    
    # Validate choice
    if choice not in ("heads", "tails"):
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;орёл|решка&gt;</code>\n"
            "Примеры:\n"
            "  <code>/coinflip 50 орёл</code>\n"
            "  <code>/coinflip 100 решка</code>\n"
            "  <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: орёл (heads) или решка (tails)",
            parse_mode="HTML"
        )
    
    # Validate bet amount
    if bet_amount <= 0:
        return await msg.reply(
            "🪙 Ставка должна быть положительной, гений.",
            parse_mode="HTML"
        )
    
    # Play coin flip using the game engine
    result = game_engine.flip_coin(user_id, chat_id, bet_amount, choice)
    
    # Log the result
    logger.info(
        f"CoinFlip: @{msg.from_user.username or user_id} - "
        f"choice={result.choice}, result={result.result}, won={result.won}, "
        f"bet={result.bet_amount}, change={result.balance_change}, balance={result.new_balance}"
    )
    
    # Handle errors
    if not result.success:
        await msg.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"{result.message}",
            parse_mode="HTML"
        )
        return
    
    # Format choice display
    choice_display = "орёл" if result.choice == "heads" else "решка"
    result_display = "орёл" if result.result == "heads" else "решка"
    
    # Send the result message
    if result.won:
        emoji = "🎉"
        outcome = f"Выпало: {result_display.upper()}! Ты угадал!"
    else:
        emoji = "😢"
        outcome = f"Выпало: {result_display.upper()}! Мимо..."
    
    await msg.reply(
        f"🪙 <b>Монетка</b>\n\n"
        f"Твой выбор: {choice_display}\n"
        f"{emoji} {outcome}\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"📋 /games",
        parse_mode="HTML"
    )
