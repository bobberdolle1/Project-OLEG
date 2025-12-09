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
    - 1.2: Show game options
    - 1.3: Navigate to game interface on button click
    
    Updated in v7.5 with new games.
    """
    
    BUTTONS_PAGE_1 = [
        ("🔫 Рулетка", "game:roulette"),
        ("🎲 Кости", "game:dice"),
        ("🥒 Пиписомер", "game:grow"),
        ("⚔️ PvP Дуэль", "game:duel"),
        ("🤖 Бой с Олегом", "game:pve"),
        ("🃏 Блэкджек", "game:blackjack"),
    ]
    
    BUTTONS_PAGE_2 = [
        ("🎰 Казино", "game:casino"),
        ("🎣 Рыбалка", "game:fish"),
        ("🚀 Краш", "game:crash"),
        ("🎡 Колесо", "game:wheel"),
        ("🃏 Война", "game:war"),
        ("🔮 Угадай", "game:guess"),
    ]
    
    BUTTONS_PAGE_3 = [
        ("📦 Лутбоксы", "game:loot"),
        ("🐔 Петухи", "game:cockfight"),
        ("🏪 Магазин", "game:shop"),
        ("🎒 Инвентарь", "game:inventory"),
        ("📊 Топ", "game:top"),
        ("💰 Баланс", "game:balance"),
    ]
    
    @classmethod
    def get_keyboard(cls, page: int = 1) -> InlineKeyboardMarkup:
        """Create inline keyboard with game buttons.
        
        Args:
            page: Page number (1, 2, or 3)
        
        Returns:
            InlineKeyboardMarkup with game buttons in 2x3 grid
        """
        if page == 1:
            buttons_list = cls.BUTTONS_PAGE_1
        elif page == 2:
            buttons_list = cls.BUTTONS_PAGE_2
        else:
            buttons_list = cls.BUTTONS_PAGE_3
        
        # Create 2x3 grid of buttons
        keyboard = []
        for i in range(0, len(buttons_list), 2):
            row = []
            for text, callback_data in buttons_list[i:i+2]:
                row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            keyboard.append(row)
        
        # Add navigation buttons
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"game:page:{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/3", callback_data="game:noop"))
        if page < 3:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"game:page:{page+1}"))
        keyboard.append(nav_row)
        
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
        
        game_type = callback.data[len(GAME_PREFIX):]
        
        # Handle pagination
        if game_type.startswith("page:"):
            page = int(game_type.split(":")[1])
            await callback.message.edit_reply_markup(reply_markup=cls.get_keyboard(page))
            await callback.answer()
            return
        
        if game_type == "noop":
            await callback.answer()
            return
        
        # Check if user is already playing (Requirements 2.2, 2.3)
        if await state_manager.is_playing(user_id, chat_id):
            session = await state_manager.get_session(user_id, chat_id)
            game_name = session.game_type if session else "игру"
            await callback.answer(
                f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру.",
                show_alert=True
            )
            return
        
        # Route to appropriate game - launch directly!
        await callback.answer()
        
        # Lazy imports to avoid circular dependencies
        from app.handlers import mini_games, games, blackjack, challenges, shop as shop_handler
        
        # Create a fake message object for handlers that expect Message
        # Use model_copy() since aiogram 3.x Message objects are frozen (Pydantic v2)
        fake_message = callback.message.model_copy(update={"from_user": callback.from_user})
        
        try:
            if game_type == "roulette":
                await games.cmd_roulette(fake_message)
            elif game_type == "dice":
                await mini_games.cmd_dice(fake_message)
            elif game_type == "grow":
                await games.cmd_grow(fake_message)
            elif game_type == "duel":
                await callback.message.answer(
                    "⚔️ <b>PvP Дуэль</b>\n\n"
                    "Вызови соперника: /challenge @username [ставка]\n"
                    "Или /challenge для боя с Олегом!",
                    parse_mode="HTML"
                )
            elif game_type == "pve":
                await challenges.cmd_challenge(fake_message)
            elif game_type == "blackjack":
                await blackjack.cmd_blackjack(fake_message)
            elif game_type == "casino":
                await games.cmd_casino(fake_message)
            elif game_type == "fish":
                await mini_games.cmd_fish(fake_message)
            elif game_type == "crash":
                await mini_games.cmd_crash(fake_message)
            elif game_type == "wheel":
                await mini_games.cmd_wheel(fake_message)
            elif game_type == "war":
                await mini_games.cmd_war(fake_message)
            elif game_type == "guess":
                await mini_games.cmd_guess(fake_message)
            elif game_type == "loot":
                await mini_games.cmd_loot(fake_message)
            elif game_type == "cockfight":
                await mini_games.cmd_cockfight(fake_message)
            elif game_type == "shop":
                await shop_handler.cmd_shop(fake_message)
            elif game_type == "inventory":
                await mini_games.cmd_inventory(fake_message)
            elif game_type == "top":
                await games.cmd_top(fake_message)
            elif game_type == "balance":
                await mini_games.cmd_balance(fake_message)
            else:
                await callback.message.answer("Неизвестная игра")
        except Exception as e:
            logger.error(f"Error launching game {game_type}: {e}")
            await callback.message.answer(f"Ошибка запуска игры: {e}")
        
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
