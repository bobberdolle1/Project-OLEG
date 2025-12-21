"""
Sticker Pack Service for OLEG v6.0 Fortress Update.

Provides automatic sticker pack management for chat quotes.
Handles pack creation, sticker addition/removal, and auto-rotation.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import StickerPack, Quote
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Maximum stickers per pack before rotation (Requirement 8.2)
MAX_STICKERS_PER_PACK = 120


@dataclass
class StickerPackInfo:
    """Information about a sticker pack."""
    id: int
    name: str
    title: str
    sticker_count: int
    is_full: bool
    is_current: bool
    chat_id: int
    owner_user_id: Optional[int] = None  # Telegram user ID who owns the pack


@dataclass
class AddStickerResult:
    """Result of adding a sticker to a pack."""
    success: bool
    sticker_file_id: Optional[str] = None
    pack_name: Optional[str] = None
    error: Optional[str] = None
    pack_rotated: bool = False
    new_pack_name: Optional[str] = None


class StickerPackService:
    """
    Service for managing sticker packs per chat.
    
    Supports:
    - Getting current pack for a chat
    - Adding stickers to packs
    - Removing stickers from packs
    - Auto-rotating packs at 120 stickers
    - Creating new packs
    
    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
    """
    
    def __init__(self, bot_username: str = "OlegBot"):
        """
        Initialize the sticker pack service.
        
        Args:
            bot_username: The bot's username for pack naming
        """
        self.bot_username = bot_username
    
    def _generate_pack_name(self, chat_id: int, version: int = 1) -> str:
        """
        Generate a unique pack name for a chat.
        
        Args:
            chat_id: The chat ID
            version: Pack version number
        
        Returns:
            A unique pack name string
        """
        # Telegram pack names must end with _by_<bot_username>
        # and contain only alphanumeric characters and underscores
        chat_id_str = str(abs(chat_id))
        return f"oleg_quotes_{chat_id_str}_v{version}_by_{self.bot_username}"
    
    def _generate_pack_title(self, chat_title: str = "Chat", version: int = 1) -> str:
        """
        Generate a human-readable pack title.
        
        Args:
            chat_title: The chat's title
            version: Pack version number
        
        Returns:
            A pack title string
        """
        title = f"Цитаты Олега - {chat_title}"
        if version > 1:
            title += f" (том {version})"
        # Telegram limits title to 64 characters
        return title[:64]

    async def get_current_pack(self, chat_id: int) -> Optional[StickerPackInfo]:
        """
        Get the current active sticker pack for a chat.
        
        Requirements: 8.1
        
        Args:
            chat_id: The chat ID
        
        Returns:
            StickerPackInfo if a pack exists, None otherwise
        """
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(StickerPack)
                .filter_by(chat_id=chat_id, is_current=True)
                .order_by(StickerPack.created_at.desc())
            )
            pack = result.scalars().first()
            
            if pack:
                return StickerPackInfo(
                    id=pack.id,
                    name=pack.pack_name,
                    title=pack.pack_title,
                    sticker_count=pack.sticker_count,
                    is_full=pack.sticker_count >= MAX_STICKERS_PER_PACK,
                    is_current=pack.is_current,
                    chat_id=pack.chat_id,
                    owner_user_id=pack.owner_user_id
                )
            return None
    
    async def get_pack_by_id(self, pack_id: int) -> Optional[StickerPackInfo]:
        """
        Get a sticker pack by its database ID.
        
        Args:
            pack_id: The pack's database ID
        
        Returns:
            StickerPackInfo if found, None otherwise
        """
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(StickerPack).filter_by(id=pack_id)
            )
            pack = result.scalars().first()
            
            if pack:
                return StickerPackInfo(
                    id=pack.id,
                    name=pack.pack_name,
                    title=pack.pack_title,
                    sticker_count=pack.sticker_count,
                    is_full=pack.sticker_count >= MAX_STICKERS_PER_PACK,
                    is_current=pack.is_current,
                    chat_id=pack.chat_id,
                    owner_user_id=pack.owner_user_id
                )
            return None
    
    async def get_all_packs(self, chat_id: int) -> List[StickerPackInfo]:
        """
        Get all sticker packs for a chat.
        
        Args:
            chat_id: The chat ID
        
        Returns:
            List of StickerPackInfo objects
        """
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(StickerPack)
                .filter_by(chat_id=chat_id)
                .order_by(StickerPack.created_at.desc())
            )
            packs = result.scalars().all()
            
            return [
                StickerPackInfo(
                    id=pack.id,
                    name=pack.pack_name,
                    title=pack.pack_title,
                    sticker_count=pack.sticker_count,
                    is_full=pack.sticker_count >= MAX_STICKERS_PER_PACK,
                    is_current=pack.is_current,
                    chat_id=pack.chat_id,
                    owner_user_id=pack.owner_user_id
                )
                for pack in packs
            ]
    
    async def create_new_pack(
        self, 
        chat_id: int, 
        chat_title: str = "Chat",
        owner_user_id: Optional[int] = None
    ) -> StickerPackInfo:
        """
        Create a new sticker pack for a chat.
        
        Requirements: 8.2
        
        Args:
            chat_id: The chat ID
            chat_title: The chat's title for the pack name
            owner_user_id: Telegram user ID who will own the pack
        
        Returns:
            StickerPackInfo for the new pack
        """
        async_session = get_session()
        async with async_session() as session:
            # Get the next version number
            result = await session.execute(
                select(StickerPack)
                .filter_by(chat_id=chat_id)
                .order_by(StickerPack.created_at.desc())
            )
            existing_packs = result.scalars().all()
            version = len(existing_packs) + 1
            
            # If no owner specified, try to get from existing pack
            if owner_user_id is None and existing_packs:
                owner_user_id = existing_packs[0].owner_user_id
            
            # Mark all existing packs as not current
            if existing_packs:
                await session.execute(
                    update(StickerPack)
                    .where(StickerPack.chat_id == chat_id)
                    .values(is_current=False)
                )
            
            # Create new pack
            pack_name = self._generate_pack_name(chat_id, version)
            pack_title = self._generate_pack_title(chat_title, version)
            
            new_pack = StickerPack(
                chat_id=chat_id,
                pack_name=pack_name,
                pack_title=pack_title,
                sticker_count=0,
                is_current=True,
                owner_user_id=owner_user_id
            )
            session.add(new_pack)
            await session.commit()
            await session.refresh(new_pack)
            
            logger.info(f"Created new sticker pack '{pack_name}' for chat {chat_id}, owner: {owner_user_id}")
            
            return StickerPackInfo(
                id=new_pack.id,
                name=new_pack.pack_name,
                title=new_pack.pack_title,
                sticker_count=0,
                is_full=False,
                is_current=True,
                chat_id=chat_id,
                owner_user_id=owner_user_id
            )

    async def rotate_pack_if_needed(
        self, 
        chat_id: int, 
        chat_title: str = "Chat"
    ) -> Optional[StickerPackInfo]:
        """
        Check if the current pack is full and create a new one if needed.
        
        Requirements: 8.2
        Property 20: Pack rotation threshold - auto-rotate at 120 stickers
        
        Args:
            chat_id: The chat ID
            chat_title: The chat's title for the new pack name
        
        Returns:
            StickerPackInfo for the new pack if rotation occurred, None otherwise
        """
        current_pack = await self.get_current_pack(chat_id)
        
        if current_pack is None:
            # No pack exists, create the first one
            return await self.create_new_pack(chat_id, chat_title)
        
        if current_pack.sticker_count >= MAX_STICKERS_PER_PACK:
            # Pack is full, create a new one
            logger.info(
                f"Pack '{current_pack.name}' is full ({current_pack.sticker_count} stickers), "
                f"rotating to new pack for chat {chat_id}"
            )
            return await self.create_new_pack(chat_id, chat_title)
        
        return None
    
    async def add_sticker(
        self, 
        chat_id: int, 
        quote_id: int,
        sticker_file_id: str,
        chat_title: str = "Chat"
    ) -> AddStickerResult:
        """
        Add a sticker to the current pack for a chat.
        
        Requirements: 8.1, 8.2, 8.3, 8.4
        Property 20: Pack rotation threshold
        Property 21: Sticker record update
        
        Args:
            chat_id: The chat ID
            quote_id: The quote's database ID
            sticker_file_id: The Telegram file ID of the sticker
            chat_title: The chat's title (for pack creation if needed)
        
        Returns:
            AddStickerResult with operation details
        """
        async_session = get_session()
        async with async_session() as session:
            # Check if pack rotation is needed (Property 20)
            rotated_pack = await self.rotate_pack_if_needed(chat_id, chat_title)
            pack_rotated = rotated_pack is not None
            
            # Get current pack
            current_pack = await self.get_current_pack(chat_id)
            if current_pack is None:
                # Create first pack if none exists
                current_pack = await self.create_new_pack(chat_id, chat_title)
            
            # Update the quote record with sticker info (Property 21)
            quote_result = await session.execute(
                select(Quote).filter_by(id=quote_id)
            )
            quote = quote_result.scalars().first()
            
            if not quote:
                return AddStickerResult(
                    success=False,
                    error=f"Quote with ID {quote_id} not found"
                )
            
            # Update quote with sticker info
            quote.is_sticker = True
            quote.sticker_file_id = sticker_file_id
            quote.sticker_pack_id = current_pack.id
            
            # Increment pack sticker count
            pack_result = await session.execute(
                select(StickerPack).filter_by(id=current_pack.id)
            )
            pack = pack_result.scalars().first()
            if pack:
                pack.sticker_count += 1
            
            await session.commit()
            
            logger.info(
                f"Added sticker for quote {quote_id} to pack '{current_pack.name}' "
                f"(now {pack.sticker_count if pack else 'unknown'} stickers)"
            )
            
            return AddStickerResult(
                success=True,
                sticker_file_id=sticker_file_id,
                pack_name=current_pack.name,
                pack_rotated=pack_rotated,
                new_pack_name=rotated_pack.name if rotated_pack else None
            )
    
    async def remove_sticker(
        self, 
        quote_id: int
    ) -> bool:
        """
        Remove a sticker from its pack.
        
        Requirements: 8.5
        
        Args:
            quote_id: The quote's database ID
        
        Returns:
            True if successful, False otherwise
        """
        async_session = get_session()
        async with async_session() as session:
            # Get the quote
            quote_result = await session.execute(
                select(Quote).filter_by(id=quote_id)
            )
            quote = quote_result.scalars().first()
            
            if not quote:
                logger.warning(f"Quote with ID {quote_id} not found for sticker removal")
                return False
            
            if not quote.is_sticker or not quote.sticker_pack_id:
                logger.warning(f"Quote {quote_id} is not a sticker")
                return False
            
            pack_id = quote.sticker_pack_id
            
            # Clear sticker info from quote
            quote.is_sticker = False
            quote.sticker_file_id = None
            quote.sticker_pack_id = None
            
            # Decrement pack sticker count
            pack_result = await session.execute(
                select(StickerPack).filter_by(id=pack_id)
            )
            pack = pack_result.scalars().first()
            if pack and pack.sticker_count > 0:
                pack.sticker_count -= 1
            
            await session.commit()
            
            logger.info(f"Removed sticker for quote {quote_id} from pack {pack_id}")
            return True
    
    async def get_pack_stickers(self, pack_id: int) -> List[Quote]:
        """
        Get all quotes/stickers in a pack.
        
        Args:
            pack_id: The pack's database ID
        
        Returns:
            List of Quote objects that are stickers in this pack
        """
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(Quote)
                .filter_by(sticker_pack_id=pack_id, is_sticker=True)
                .order_by(Quote.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def update_quote_sticker_file_id(
        self, 
        quote_id: int, 
        sticker_file_id: str
    ) -> bool:
        """
        Update the sticker file ID for a quote.
        
        Requirements: 8.4
        Property 21: Sticker record update
        
        Args:
            quote_id: The quote's database ID
            sticker_file_id: The new Telegram file ID
        
        Returns:
            True if successful, False otherwise
        """
        async_session = get_session()
        async with async_session() as session:
            quote_result = await session.execute(
                select(Quote).filter_by(id=quote_id)
            )
            quote = quote_result.scalars().first()
            
            if not quote:
                logger.warning(f"Quote with ID {quote_id} not found")
                return False
            
            quote.sticker_file_id = sticker_file_id
            await session.commit()
            
            logger.info(f"Updated sticker file ID for quote {quote_id}")
            return True


# Singleton instance
sticker_pack_service = StickerPackService()
