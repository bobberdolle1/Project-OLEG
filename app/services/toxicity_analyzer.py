"""Toxicity Analyzer Service - AI-powered toxicity detection.

This module provides context-aware toxicity analysis using LLM,
detecting insults, hate speech, threats, and spam while distinguishing
between sarcastic insults and genuine compliments.

**Feature: fortress-update**
**Validates: Requirements 2.1, 2.3, 2.4**
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ToxicityLog
from app.database.session import get_session
from app.services.citadel import DEFCONLevel
from app.services.ollama_client import _ollama_chat
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes and Enums
# ============================================================================

class ToxicityCategory(str, Enum):
    """Categories of toxic content."""
    INSULT = "insult"
    HATE_SPEECH = "hate_speech"
    THREAT = "threat"
    SPAM = "spam"


class ModerationAction(str, Enum):
    """Actions to take based on toxicity analysis."""
    NONE = "none"
    WARN = "warn"
    DELETE = "delete"
    DELETE_AND_MUTE = "delete_and_mute"


@dataclass
class ToxicityResult:
    """
    Result of toxicity analysis.
    
    Attributes:
        score: Toxicity score from 0-100
        category: Detected toxicity category (insult, hate_speech, threat, spam)
        confidence: Confidence level from 0.0-1.0
        is_sarcasm: Whether the message appears to be sarcastic
        raw_response: Raw LLM response for debugging
        
    **Validates: Requirements 2.3**
    """
    score: int  # 0-100
    category: Optional[str]  # insult, hate_speech, threat, spam
    confidence: float  # 0.0-1.0
    is_sarcasm: bool = False
    raw_response: str = ""
    
    def __post_init__(self):
        """Validate and normalize fields."""
        # Ensure score is within bounds
        self.score = max(0, min(100, self.score))
        # Ensure confidence is within bounds
        self.confidence = max(0.0, min(1.0, self.confidence))
        # Normalize category
        if self.category:
            self.category = self.category.lower().replace(" ", "_")
            # Validate category
            valid_categories = {c.value for c in ToxicityCategory}
            if self.category not in valid_categories:
                self.category = None


# ============================================================================
# System Prompts
# ============================================================================

TOXICITY_SYSTEM_PROMPT = """You are a toxicity detection model for a Russian-speaking Telegram chat. 
Analyze the user's message and return a JSON response with the following structure:
{
    "score": <integer 0-100, where 0 is non-toxic and 100 is highly toxic>,
    "category": <string or null: "insult", "hate_speech", "threat", or "spam">,
    "confidence": <float 0.0-1.0, how confident you are in your assessment>,
    "is_sarcasm": <boolean, true if the message appears to be sarcastic or ironic>
}

Guidelines:
- Consider context: distinguish between friendly banter and genuine insults
- Detect sarcasm: "Какой ты умный" might be sarcastic depending on context
- Categories:
  - insult: Personal attacks, name-calling, degrading language
  - hate_speech: Discrimination based on race, religion, gender, etc.
  - threat: Threats of violence or harm
  - spam: Repetitive content, promotional spam, flood
- Score guidelines:
  - 0-20: Clean, friendly message
  - 21-40: Mild negativity, borderline content
  - 41-60: Moderately toxic, clear negativity
  - 61-80: Highly toxic, offensive content
  - 81-100: Extremely toxic, severe violations

Return ONLY the JSON object, no additional text."""


# ============================================================================
# Toxicity Analyzer Functions
# ============================================================================

async def analyze_toxicity(
    session: AsyncSession,
    user_text: str
) -> ToxicityResult:
    """
    Analyze user text for toxicity using LLM.
    
    Returns a structured ToxicityResult with score, category, confidence,
    and sarcasm detection.
    
    Args:
        session: Database session (for future use)
        user_text: Text to analyze
        
    Returns:
        ToxicityResult with analysis results
        
    **Feature: fortress-update, Property 9: Toxicity result structure**
    **Validates: Requirements 2.1, 2.3**
    """
    if not user_text or not user_text.strip():
        return ToxicityResult(
            score=0,
            category=None,
            confidence=1.0,
            is_sarcasm=False,
            raw_response=""
        )
    
    messages = [
        {"role": "system", "content": TOXICITY_SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    
    try:
        response = await _ollama_chat(messages, temperature=0.1, use_cache=True)
        return _parse_toxicity_response(response)
    except Exception as e:
        logger.error(f"Toxicity analysis failed: {e}")
        # Default to non-toxic on error
        return ToxicityResult(
            score=0,
            category=None,
            confidence=0.0,
            is_sarcasm=False,
            raw_response=str(e)
        )


def _parse_toxicity_response(response: str) -> ToxicityResult:
    """
    Parse LLM response into ToxicityResult.
    
    Handles both JSON responses and legacy integer-only responses.
    """
    raw_response = response
    
    # Try to parse as JSON first
    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove markdown code block
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
            cleaned = cleaned.rstrip("`").strip()
        
        data = json.loads(cleaned)
        
        # Check if it's a dict (JSON object) vs just a number
        if isinstance(data, dict):
            return ToxicityResult(
                score=int(data.get("score", 0)),
                category=data.get("category"),
                confidence=float(data.get("confidence", 0.5)),
                is_sarcasm=bool(data.get("is_sarcasm", False)),
                raw_response=raw_response
            )
        elif isinstance(data, (int, float)):
            # JSON parsed as a number - treat as legacy format
            return ToxicityResult(
                score=int(data),
                category=None,
                confidence=0.5,
                is_sarcasm=False,
                raw_response=raw_response
            )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # Fallback: try to extract just a number (legacy format)
    try:
        # Find first number in response
        match = re.search(r'\d+', response)
        if match:
            score = int(match.group())
            return ToxicityResult(
                score=score,
                category=None,
                confidence=0.5,
                is_sarcasm=False,
                raw_response=raw_response
            )
    except (ValueError, TypeError):
        pass
    
    # Default fallback
    return ToxicityResult(
        score=0,
        category=None,
        confidence=0.0,
        is_sarcasm=False,
        raw_response=raw_response
    )


# ============================================================================
# DEFCON-Aware Action Mapping
# ============================================================================

def get_action_for_score(
    score: int,
    defcon_level: DEFCONLevel,
    threshold: int = 75
) -> ModerationAction:
    """
    Determine moderation action based on toxicity score and DEFCON level.
    
    Action mapping:
    - Score <= threshold: No action
    - Score > threshold at DEFCON 1: Warn
    - Score > threshold at DEFCON 2: Delete
    - Score > threshold at DEFCON 3: Delete and mute
    
    Args:
        score: Toxicity score (0-100)
        defcon_level: Current DEFCON protection level
        threshold: Score threshold for action (default 75)
        
    Returns:
        ModerationAction to take
        
    **Feature: fortress-update, Property 8: Toxicity action mapping**
    **Validates: Requirements 2.2**
    """
    if score <= threshold:
        return ModerationAction.NONE
    
    # Score exceeds threshold - action depends on DEFCON level
    if defcon_level == DEFCONLevel.PEACEFUL:
        return ModerationAction.WARN
    elif defcon_level == DEFCONLevel.STRICT:
        return ModerationAction.DELETE
    else:  # MARTIAL_LAW
        return ModerationAction.DELETE_AND_MUTE


# ============================================================================
# Incident Logging
# ============================================================================

async def log_incident(
    chat_id: int,
    user_id: int,
    message_text: str,
    result: ToxicityResult,
    action_taken: str,
    session: Optional[AsyncSession] = None
) -> ToxicityLog:
    """
    Log a toxicity incident to the database.
    
    Creates a record in toxicity_logs with message text, score,
    category, and action taken.
    
    Args:
        chat_id: Telegram chat ID
        user_id: Telegram user ID
        message_text: Original message text
        result: ToxicityResult from analysis
        action_taken: Action that was taken (warn, delete, mute, etc.)
        session: Optional database session
        
    Returns:
        Created ToxicityLog record
        
    **Feature: fortress-update, Property 10: Toxicity incident logging**
    **Validates: Requirements 2.4**
    """
    close_session = False
    if session is None:
        async_session = get_session()
        session = async_session()
        close_session = True
    
    try:
        log_entry = ToxicityLog(
            chat_id=chat_id,
            user_id=user_id,
            message_text=message_text,
            score=float(result.score),
            category=result.category,
            action_taken=action_taken,
            created_at=utc_now()
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        
        logger.info(
            f"Toxicity incident logged: chat={chat_id}, user={user_id}, "
            f"score={result.score}, category={result.category}, action={action_taken}"
        )
        
        return log_entry
        
    finally:
        if close_session:
            await session.close()


async def get_recent_incidents(
    chat_id: int,
    user_id: Optional[int] = None,
    limit: int = 10,
    session: Optional[AsyncSession] = None
) -> list[ToxicityLog]:
    """
    Get recent toxicity incidents for a chat or user.
    
    Args:
        chat_id: Telegram chat ID
        user_id: Optional user ID to filter by
        limit: Maximum number of incidents to return
        session: Optional database session
        
    Returns:
        List of ToxicityLog records
    """
    close_session = False
    if session is None:
        async_session = get_session()
        session = async_session()
        close_session = True
    
    try:
        query = select(ToxicityLog).filter_by(chat_id=chat_id)
        
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        
        query = query.order_by(ToxicityLog.created_at.desc()).limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())
        
    finally:
        if close_session:
            await session.close()
