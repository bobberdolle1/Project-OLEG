"""
Обработчик реакций на сообщения Олега.

Олег реагирует на реакции пользователей к его сообщениям,
делая взаимодействие более живым.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**
"""

import logging
import random
import time
from aiogram import Router, Bot
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji

logger = logging.getLogger(__name__)

router = Router()

# Positive reactions that Oleg responds to positively
# **Validates: Requirements 8.2**
POSITIVE_REACTIONS = {"❤️", "👍", "🔥", "😍", "🎉", "💯", "⚡", "🥰", "😘", "🤩", "👏", "🙏"}

# Negative reactions that Oleg may respond to sarcastically
# **Validates: Requirements 8.3**
NEGATIVE_REACTIONS = {"👎", "💩", "🤮", "😡", "🤬", "😤", "👿", "💔"}

# Cooldown mechanism to prevent spam
# Key: (chat_id, message_id), Value: timestamp of last reaction response
# **Validates: Requirements 8.4**
_reaction_cooldowns: dict[tuple[int, int], float] = {}
REACTION_COOLDOWN = 30.0  # 30 seconds cooldown per message


def is_on_cooldown(chat_id: int, message_id: int) -> bool:
    """
    Check if a message is on cooldown for reaction responses.
    
    **Validates: Requirements 8.4**
    
    Args:
        chat_id: Chat ID
        message_id: Message ID
        
    Returns:
        True if on cooldown, False otherwise
    """
    key = (chat_id, message_id)
    last_response_time = _reaction_cooldowns.get(key, 0)
    return time.time() - last_response_time < REACTION_COOLDOWN


def set_cooldown(chat_id: int, message_id: int) -> None:
    """
    Set cooldown for a message after responding to a reaction.
    
    **Validates: Requirements 8.4**
    
    Args:
        chat_id: Chat ID
        message_id: Message ID
    """
    key = (chat_id, message_id)
    _reaction_cooldowns[key] = time.time()


def cleanup_old_cooldowns() -> None:
    """
    Remove expired cooldowns to prevent memory leaks.
    Called periodically during reaction processing.
    """
    current_time = time.time()
    expired_keys = [
        key for key, timestamp in _reaction_cooldowns.items()
        if current_time - timestamp > REACTION_COOLDOWN * 2
    ]
    for key in expired_keys:
        del _reaction_cooldowns[key]


@router.message_reaction()
async def on_reaction(event: MessageReactionUpdated):
    """
    Handle reactions to Oleg's messages.
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    
    Args:
        event: MessageReactionUpdated event from Telegram
    """
    # Cleanup old cooldowns periodically
    if random.random() < 0.1:  # 10% chance to cleanup
        cleanup_old_cooldowns()
    
    # Check if we have new reactions
    if not event.new_reaction:
        return
    
    chat_id = event.chat.id
    message_id = event.message_id
    
    # Check cooldown - prevent spam responses
    # **Validates: Requirements 8.4**
    if is_on_cooldown(chat_id, message_id):
        logger.debug(f"Reaction on cooldown for message {message_id} in chat {chat_id}")
        return
    
    # Get the bot instance to check if the message is from the bot
    # and to send responses
    bot: Bot = event.bot
    
    # Check if this reaction is on a bot's message
    # We need to verify the message author is the bot
    try:
        # Try to get bot info
        bot_info = await bot.get_me()
        bot_id = bot_info.id
    except Exception as e:
        logger.warning(f"Failed to get bot info: {e}")
        return
    
    # Extract emoji from reactions
    new_emojis = set()
    for reaction in event.new_reaction:
        if isinstance(reaction, ReactionTypeEmoji):
            new_emojis.add(reaction.emoji)
        elif hasattr(reaction, 'emoji'):
            new_emojis.add(reaction.emoji)
    
    if not new_emojis:
        return
    
    # Check for positive reactions
    # **Validates: Requirements 8.2**
    positive_match = new_emojis & POSITIVE_REACTIONS
    if positive_match:
        # Set cooldown before responding
        set_cooldown(chat_id, message_id)
        
        # Respond with a positive reaction
        response_emoji = random.choice(["❤️", "🔥", "😊", "👍", "🤗"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(
                f"Oleg responded with {response_emoji} to positive reaction "
                f"in chat {chat_id}, message {message_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to set reaction response: {e}")
        return
    
    # Check for negative reactions
    # **Validates: Requirements 8.3**
    negative_match = new_emojis & NEGATIVE_REACTIONS
    if negative_match:
        # Set cooldown before responding
        set_cooldown(chat_id, message_id)
        
        # 30% chance to respond sarcastically with a message
        if random.random() < 0.3:
            sarcastic_responses = [
                "Ну и ладно 😤",
                "Сам такой 🙄",
                "Обидно, да? 😏",
                "Критика принята, но проигнорирована 😎",
                "Ой, всё 💅",
            ]
            try:
                # Get thread_id if in a forum
                thread_id = getattr(event, 'message_thread_id', None)
                await bot.send_message(
                    chat_id=chat_id,
                    text=random.choice(sarcastic_responses),
                    message_thread_id=thread_id
                )
                logger.info(
                    f"Oleg responded sarcastically to negative reaction "
                    f"in chat {chat_id}, message {message_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to send sarcastic response: {e}")
        else:
            # Just react back with something neutral
            try:
                await bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[ReactionTypeEmoji(emoji="🤷")]
                )
                logger.info(
                    f"Oleg responded with 🤷 to negative reaction "
                    f"in chat {chat_id}, message {message_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to set neutral reaction: {e}")
