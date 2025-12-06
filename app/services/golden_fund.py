"""
Golden Fund Service for OLEG v6.0 Fortress Update.

Manages the "Golden Fund" - a collection of the best quotes that have
received 5+ reactions. Provides RAG-based semantic search for contextually
relevant quotes.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Constants
GOLDEN_FUND_REACTION_THRESHOLD = 5  # Requirement 9.1: 5+ reactions
GOLDEN_FUND_RESPONSE_PROBABILITY = 0.05  # Requirement 9.2: 5% chance
GOLDEN_FUND_COLLECTION_NAME = "golden_fund_quotes"


@dataclass
class GoldenQuote:
    """Represents a quote from the Golden Fund."""
    id: int
    text: str
    username: str
    sticker_file_id: Optional[str]
    likes_count: int
    chat_id: Optional[int]


@dataclass
class GoldenFundSearchResult:
    """Result of a Golden Fund search."""
    quote: Optional[GoldenQuote]
    similarity_score: float
    found: bool


class GoldenFundService:
    """
    Service for managing the Golden Fund - a collection of best quotes.
    
    Features:
    - Automatic promotion of quotes with 5+ reactions (Requirement 9.1)
    - RAG-based semantic search for relevant quotes (Requirement 9.4)
    - 5% probability to respond with a Golden Fund quote (Requirement 9.2)
    - Notification when quotes enter the Golden Fund (Requirement 9.5)
    
    Properties:
    - Property 22: Golden promotion threshold
    - Property 23: Golden search probability
    """
    
    def __init__(self):
        """Initialize the Golden Fund service."""
        self._vector_db = None
    
    @property
    def vector_db(self):
        """Lazy load vector database to avoid circular imports."""
        if self._vector_db is None:
            try:
                from app.services.vector_db import vector_db
                self._vector_db = vector_db
            except Exception as e:
                logger.warning(f"Failed to initialize vector DB: {e}")
        return self._vector_db
    
    def check_and_promote(self, reaction_count: int) -> bool:
        """
        Check if a quote should be promoted to the Golden Fund.
        
        Property 22: Golden promotion threshold
        *For any* quote with 5 or more fire/thumbs-up reactions, 
        is_golden_fund SHALL be true.
        
        Requirement 9.1: WHEN a quote sticker receives 5 or more 
        fire/thumbs-up reactions THEN the Golden Fund System SHALL 
        mark the quote as part of the Golden Fund.
        
        Args:
            reaction_count: Number of reactions on the quote
        
        Returns:
            True if the quote should be promoted to Golden Fund
        """
        return reaction_count >= GOLDEN_FUND_REACTION_THRESHOLD
    
    async def promote_quote(
        self, 
        session: AsyncSession, 
        quote_id: int
    ) -> bool:
        """
        Promote a quote to the Golden Fund.
        
        Requirement 9.1: Mark the quote as part of the Golden Fund.
        
        Args:
            session: Database session
            quote_id: ID of the quote to promote
        
        Returns:
            True if promotion was successful
        """
        from app.database.models import Quote
        
        try:
            # Get the quote
            result = await session.execute(
                select(Quote).filter_by(id=quote_id)
            )
            quote = result.scalars().first()
            
            if not quote:
                logger.warning(f"Quote {quote_id} not found for promotion")
                return False
            
            if quote.is_golden_fund:
                logger.debug(f"Quote {quote_id} is already in Golden Fund")
                return True
            
            # Promote to Golden Fund
            quote.is_golden_fund = True
            await session.commit()
            
            # Add to vector database for RAG search (Requirement 9.4)
            await self._add_to_vector_db(quote)
            
            logger.info(f"Quote {quote_id} promoted to Golden Fund")
            return True
            
        except Exception as e:
            logger.error(f"Failed to promote quote {quote_id}: {e}")
            await session.rollback()
            return False
    
    async def _add_to_vector_db(self, quote) -> None:
        """
        Add a quote to the vector database for semantic search.
        
        Requirement 9.4: Use semantic similarity between the current 
        message and stored quote texts.
        
        Args:
            quote: Quote model instance
        """
        if self.vector_db is None:
            logger.warning("Vector DB not available, skipping indexing")
            return
        
        try:
            metadata = {
                "quote_id": quote.id,
                "username": quote.username or "",
                "chat_id": quote.telegram_chat_id or 0,
                "likes_count": quote.likes_count,
                "has_sticker": bool(quote.sticker_file_id),
            }
            
            self.vector_db.add_fact(
                collection_name=GOLDEN_FUND_COLLECTION_NAME,
                fact_text=quote.text,
                metadata=metadata,
                doc_id=f"golden_quote_{quote.id}"
            )
            
            logger.debug(f"Added quote {quote.id} to vector DB")
            
        except Exception as e:
            logger.warning(f"Failed to add quote to vector DB: {e}")
    
    def should_respond_with_quote(self) -> bool:
        """
        Determine if Oleg should respond with a Golden Fund quote.
        
        Property 23: Golden search probability
        *For any* large sample of response generations (n > 1000), 
        the proportion that search Golden Fund SHALL be approximately 
        5% (within statistical tolerance).
        
        Requirement 9.2: WHEN Oleg generates a response THEN the 
        Golden Fund System SHALL have a 5% chance to search the 
        Golden Fund for a contextually relevant quote using RAG.
        
        Returns:
            True if should search and respond with a Golden Fund quote
        """
        return random.random() < GOLDEN_FUND_RESPONSE_PROBABILITY
    
    async def search_relevant_quote(
        self, 
        context: str, 
        chat_id: Optional[int] = None,
        limit: int = 5
    ) -> Optional[GoldenQuote]:
        """
        Search for a contextually relevant quote from the Golden Fund.
        
        Requirement 9.3: WHEN a relevant Golden Fund quote is found 
        THEN the Golden Fund System SHALL respond with the quote 
        sticker instead of generating new text.
        
        Requirement 9.4: WHEN searching for relevant quotes THEN the 
        Golden Fund System SHALL use semantic similarity between the 
        current message and stored quote texts.
        
        Args:
            context: The current message context to match against
            chat_id: Optional chat ID to filter quotes from same chat
            limit: Maximum number of results to consider
        
        Returns:
            GoldenQuote if a relevant quote is found, None otherwise
        """
        if self.vector_db is None:
            logger.warning("Vector DB not available for search")
            return None
        
        if not context or len(context.strip()) < 3:
            return None
        
        try:
            # Build filter for chat-specific search if chat_id provided
            where_filter = None
            if chat_id:
                where_filter = {"chat_id": chat_id}
            
            # Search using semantic similarity (Requirement 9.4)
            results = self.vector_db.search_facts(
                collection_name=GOLDEN_FUND_COLLECTION_NAME,
                query=context,
                n_results=limit,
                where=where_filter
            )
            
            if not results:
                # Try without chat filter if no results
                if chat_id:
                    results = self.vector_db.search_facts(
                        collection_name=GOLDEN_FUND_COLLECTION_NAME,
                        query=context,
                        n_results=limit
                    )
            
            if not results:
                return None
            
            # Get the best match
            best_match = results[0]
            
            # Check similarity threshold (distance < 1.0 is considered relevant)
            distance = best_match.get('distance', 1.0)
            if distance is None or distance > 0.8:
                logger.debug(f"No sufficiently relevant quote found (distance: {distance})")
                return None
            
            # Extract quote info from metadata
            metadata = best_match.get('metadata', {})
            quote_id = metadata.get('quote_id')
            
            if not quote_id:
                return None
            
            # Fetch full quote from database
            return await self._get_quote_by_id(quote_id)
            
        except Exception as e:
            logger.error(f"Failed to search Golden Fund: {e}")
            return None
    
    async def _get_quote_by_id(self, quote_id: int) -> Optional[GoldenQuote]:
        """
        Get a quote by ID from the database.
        
        Args:
            quote_id: ID of the quote
        
        Returns:
            GoldenQuote if found, None otherwise
        """
        from app.database.session import get_session
        from app.database.models import Quote
        
        try:
            async_session = get_session()
            async with async_session() as session:
                result = await session.execute(
                    select(Quote).filter_by(id=quote_id, is_golden_fund=True)
                )
                quote = result.scalars().first()
                
                if not quote:
                    return None
                
                return GoldenQuote(
                    id=quote.id,
                    text=quote.text,
                    username=quote.username,
                    sticker_file_id=quote.sticker_file_id,
                    likes_count=quote.likes_count,
                    chat_id=quote.telegram_chat_id
                )
                
        except Exception as e:
            logger.error(f"Failed to get quote {quote_id}: {e}")
            return None
    
    async def get_golden_quotes(
        self, 
        chat_id: Optional[int] = None, 
        limit: int = 10
    ) -> List[GoldenQuote]:
        """
        Get a list of Golden Fund quotes.
        
        Args:
            chat_id: Optional chat ID to filter quotes
            limit: Maximum number of quotes to return
        
        Returns:
            List of GoldenQuote objects
        """
        from app.database.session import get_session
        from app.database.models import Quote
        
        try:
            async_session = get_session()
            async with async_session() as session:
                query = select(Quote).filter_by(is_golden_fund=True)
                
                if chat_id:
                    query = query.filter_by(telegram_chat_id=chat_id)
                
                query = query.order_by(Quote.likes_count.desc()).limit(limit)
                
                result = await session.execute(query)
                quotes = result.scalars().all()
                
                return [
                    GoldenQuote(
                        id=q.id,
                        text=q.text,
                        username=q.username,
                        sticker_file_id=q.sticker_file_id,
                        likes_count=q.likes_count,
                        chat_id=q.telegram_chat_id
                    )
                    for q in quotes
                ]
                
        except Exception as e:
            logger.error(f"Failed to get golden quotes: {e}")
            return []
    
    async def get_random_golden_quote(
        self, 
        chat_id: Optional[int] = None
    ) -> Optional[GoldenQuote]:
        """
        Get a random quote from the Golden Fund.
        
        Useful for daily quotes feature.
        
        Args:
            chat_id: Optional chat ID to filter quotes
        
        Returns:
            Random GoldenQuote if available, None otherwise
        """
        quotes = await self.get_golden_quotes(chat_id=chat_id, limit=50)
        
        if not quotes:
            return None
        
        return random.choice(quotes)
    
    async def index_existing_golden_quotes(self) -> int:
        """
        Index all existing Golden Fund quotes in the vector database.
        
        Useful for initial setup or re-indexing.
        
        Returns:
            Number of quotes indexed
        """
        from app.database.session import get_session
        from app.database.models import Quote
        
        if self.vector_db is None:
            logger.warning("Vector DB not available for indexing")
            return 0
        
        try:
            async_session = get_session()
            async with async_session() as session:
                result = await session.execute(
                    select(Quote).filter_by(is_golden_fund=True)
                )
                quotes = result.scalars().all()
                
                indexed = 0
                for quote in quotes:
                    try:
                        await self._add_to_vector_db(quote)
                        indexed += 1
                    except Exception as e:
                        logger.warning(f"Failed to index quote {quote.id}: {e}")
                
                logger.info(f"Indexed {indexed} Golden Fund quotes")
                return indexed
                
        except Exception as e:
            logger.error(f"Failed to index golden quotes: {e}")
            return 0


# Singleton instance
golden_fund_service = GoldenFundService()
