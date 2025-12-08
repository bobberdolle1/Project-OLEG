"""Game Hub UI - Central menu for all games.

Provides an inline keyboard interface for accessing all games.
Requirements: 1.1, 1.2, 1.3, 2.2, 2.3
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from app.services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = Router()

# Game Hub banner text
GAME_HUB_BANNER = """
🎮 <b>Игровой Хаб Олега</b>

Выбери игру, сталкер! Здесь ты найдёшь всё для азартного времяпрепровождения.

<i>Быстрые команды: /roulette, /bj, /grow, /challenge</i>
"""

# Callback data prefixes
GAME_PREFIX = "game:"


class GameHubUI:
    """Central game menu with inline buttons.
    
    Requirements:
    - 1.1: Display inline message with banner and game buttons
    - 1.2: Show 6 game options
    - 1.3: Navigate to game interface on button click
    """
    
    BUTTONS = [
        ("🔫 Рулетка", "game:roulette"),
        ("🎲 Кости", "game:dice"),
        ("🥒 Пиписомер", "game:grow"),
        ("⚔️ Дуэль", "game:duel"),
        ("📊 Топ Элиты", "game:top"),
        ("🏆 Турниры", "game:tournaments"),
    ]
    
    @classmethod
    def get_keyboard(cls) -> InlineKeyboardMarkup:
        """Create inline keyboard with game buttons.
        
        Returns:
            InlineKeyboardMarkup with 6 game buttons in 2x3 grid
        """
        # Create 2x3 grid of buttons
        keyboard = []
        for i in range(0, len(cls.BUTTONS), 2):
            row = []
            for text, callback_data in cls.BUTTONS[i:i+2]:
                row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            keyboard.append(row)
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @classmethod
    async def show_hub(cls, message: Message) -> None:
        """Display the game hub menu.
        
        Args:
            message: Telegram message to reply to
        """
        await message.reply(
            GAME_HUB_BANNER,
            reply_markup=cls.get_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Game hub shown to user {message.from_user.id}")
    
    @classmethod
    async def handle_button(cls, callback: CallbackQuery) -> None:
        """Handle game button click.
        
        Args:
            callback: Callback query from button press
        """
        if not callback.data or not callback.from_user:
            return
        
        user_id = callback.from_user.id
        chat_id = callback.message.chat.id if callback.message else 0
        
        # Check if user is already playing (Requirements 2.2, 2.3)
        if await state_manager.is_playing(user_id, chat_id):
            session = await state_manager.get_session(user_id, chat_id)
            game_name = session.game_type if session else "игру"
            await callback.answer(
                f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру.",
                show_alert=True
            )
            return
        
        game_type = callback.data[len(GAME_PREFIX):]
        
        # Route to appropriate game
        if game_type == "roulette":
            await callback.answer("🔫 Используй /roulette для игры!")
            await callback.message.answer(
                "🔫 <b>Русская рулетка</b>\n\n"
                "Крути барабан командой /roulette\n"
                "Или /roulette [ставка] для игры на монеты",
                parse_mode="HTML"
            )
        elif game_type == "dice":
            await callback.answer("🎲 Используй /casino для игры!")
            await callback.message.answer(
                "🎲 <b>Кости (Казино)</b>\n\n"
                "Крути слоты командой /casino [ставка]\n"
                "Пример: /casino 100",
                parse_mode="HTML"
            )
        elif game_type == "grow":
            await callback.answer("🥒 Используй /grow для игры!")
            await callback.message.answer(
                "🥒 <b>Пиписомер</b>\n\n"
                "Выращивай свою гордость командой /grow\n"
                "Кулдаун: 12-24 часа",
                parse_mode="HTML"
            )
        elif game_type == "duel":
            await callback.answer("⚔️ Используй /challenge для дуэли!")
            await callback.message.answer(
                "⚔️ <b>Дуэль</b>\n\n"
                "Вызови соперника: /challenge @username [ставка]\n"
                "Или /pvp @username для быстрой дуэли",
                parse_mode="HTML"
            )
        elif game_type == "top":
            await callback.answer("📊 Показываю топ!")
            await callback.message.answer(
                "📊 <b>Топ Элиты</b>\n\n"
                "/top — Топ по размеру\n"
                "/top_rep — Топ по репутации",
                parse_mode="HTML"
            )
        elif game_type == "tournaments":
            await callback.answer("🏆 Турниры!")
            await callback.message.answer(
                "🏆 <b>Турниры</b>\n\n"
                "/tournament — Текущий турнир\n"
                "/tournament_top — Таблица лидеров",
                parse_mode="HTML"
            )
        else:
            await callback.answer("Неизвестная игра", show_alert=True)
        
        logger.info(f"Game hub button '{game_type}' clicked by user {user_id}")


# Global instance
game_hub = GameHubUI()


@router.message(Command("games"))
async def cmd_games(message: Message):
    """Command /games - Show the game hub menu.
    
    Requirements: 1.1
    """
    await game_hub.show_hub(message)


@router.callback_query(F.data.startswith(GAME_PREFIX))
async def callback_game_button(callback: CallbackQuery):
    """Handle game hub button clicks.
    
    Requirements: 1.3, 2.2, 2.3
    """
    await game_hub.handle_button(callback)
