"""Text-to-Speech service for voice message generation.

This module provides TTS functionality including:
- Voice message generation with text truncation
- Auto-voice probability check (0.1% chance)
- Fallback to text on service unavailability

**Feature: fortress-update**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# TTS Configuration
MAX_TEXT_LENGTH = 500
TRUNCATION_SUFFIX = "...и так далее"
AUTO_VOICE_PROBABILITY = 0.001  # 0.1%


@dataclass
class TTSResult:
    """Result of TTS generation."""
    audio_data: bytes
    duration_seconds: float
    format: str  # ogg
    original_text: str
    was_truncated: bool


class TTSService:
    """
    Text-to-Speech service for generating voice messages.
    
    Provides voice generation with Oleg's characteristic voice,
    text truncation for long messages, and auto-voice probability.
    
    **Feature: fortress-update**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
    """
    
    def __init__(self, tts_model: Optional[str] = None):
        """
        Initialize TTS service.
        
        Args:
            tts_model: TTS model to use (optional, for future extensibility)
        """
        self._tts_model = tts_model
        self._is_available = True  # Track service availability
    
    def truncate_text(self, text: str, max_length: int = MAX_TEXT_LENGTH) -> tuple[str, bool]:
        """
        Truncate text to maximum length with suffix.
        
        **Property 12: Text truncation**
        For any text input longer than 500 characters, the TTS output text 
        SHALL be truncated to 500 characters with "...и так далее" suffix.
        
        Args:
            text: Text to truncate
            max_length: Maximum length (default 500)
            
        Returns:
            Tuple of (truncated_text, was_truncated)
        """
        if not text:
            return "", False
        
        if len(text) <= max_length:
            return text, False
        
        # Calculate how much space we need for the suffix
        suffix_length = len(TRUNCATION_SUFFIX)
        
        # Truncate to max_length - suffix_length, then add suffix
        truncated = text[:max_length - suffix_length] + TRUNCATION_SUFFIX
        
        return truncated, True
    
    def should_auto_voice(self) -> bool:
        """
        Check if response should be auto-voiced.
        
        **Property 13: Auto-voice probability**
        For any large sample of text responses (n > 1000), the proportion 
        converted to voice SHALL be approximately 0.1% (within statistical tolerance).
        
        Returns:
            True if response should be converted to voice (0.1% chance)
        """
        return random.random() < AUTO_VOICE_PROBABILITY
    
    async def generate_voice(
        self,
        text: str,
        max_chars: int = MAX_TEXT_LENGTH
    ) -> Optional[TTSResult]:
        """
        Generate voice message from text.
        
        Truncates text if longer than max_chars and generates
        voice using Oleg's characteristic voice profile.
        
        Args:
            text: Text to convert to speech
            max_chars: Maximum characters (default 500)
            
        Returns:
            TTSResult with audio data, or None if service unavailable
        """
        if not text:
            return None
        
        # Truncate text if needed
        processed_text, was_truncated = self.truncate_text(text, max_chars)
        
        if was_truncated:
            logger.info(f"Text truncated from {len(text)} to {len(processed_text)} chars")
        
        try:
            # Generate voice using TTS model
            audio_data = await self._generate_audio(processed_text)
            
            if audio_data is None:
                return None
            
            return TTSResult(
                audio_data=audio_data,
                duration_seconds=self._estimate_duration(processed_text),
                format="ogg",
                original_text=processed_text,
                was_truncated=was_truncated
            )
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            self._is_available = False
            return None
    
    async def _generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generate audio data from text using TTS model.
        
        This is a placeholder implementation. In production, this would
        call an actual TTS service (e.g., Silero, Coqui, or cloud TTS).
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data in OGG format, or None if unavailable
        """
        # TODO: Implement actual TTS generation
        # For now, return None to indicate service unavailable
        # This will trigger the fallback to text response
        
        if not self._is_available:
            return None
        
        # Placeholder: In production, call actual TTS service here
        # Example with Silero TTS:
        # import torch
        # model, _ = torch.hub.load('snakers4/silero-models', 'silero_tts', ...)
        # audio = model.apply_tts(text=text, speaker='ru_v3')
        
        logger.debug(f"TTS generation requested for text: {text[:50]}...")
        
        # Return None to indicate TTS not yet implemented
        # This triggers fallback behavior
        return None
    
    def _estimate_duration(self, text: str) -> float:
        """
        Estimate audio duration based on text length.
        
        Assumes average speaking rate of ~150 words per minute
        or ~10 characters per second for Russian.
        
        Args:
            text: Text to estimate duration for
            
        Returns:
            Estimated duration in seconds
        """
        # Rough estimate: 10 characters per second for Russian speech
        chars_per_second = 10
        return len(text) / chars_per_second
    
    @property
    def is_available(self) -> bool:
        """Check if TTS service is currently available."""
        return self._is_available
    
    def set_available(self, available: bool) -> None:
        """Set TTS service availability status."""
        self._is_available = available
        if available:
            logger.info("TTS service marked as available")
        else:
            logger.warning("TTS service marked as unavailable")
    
    async def queue_tts_task(
        self,
        text: str,
        chat_id: int,
        reply_to: int,
        max_chars: int = MAX_TEXT_LENGTH
    ) -> Optional[str]:
        """
        Queue TTS generation task for async processing via Arq worker.
        
        **Validates: Requirements 14.1**
        
        Args:
            text: Text to convert to speech
            chat_id: Target chat ID
            reply_to: Message ID to reply to
            max_chars: Maximum characters (default 500)
            
        Returns:
            Task ID if queued successfully, None otherwise
        """
        try:
            from app.worker import enqueue_tts_task
            from app.config import settings
            
            # Check if worker is enabled
            if not settings.worker_enabled or not settings.redis_enabled:
                logger.debug(f"Worker not enabled, TTS task not queued for chat {chat_id}")
                return None
            
            job = await enqueue_tts_task(
                text=text,
                chat_id=chat_id,
                reply_to=reply_to,
                max_chars=max_chars,
            )
            
            if job is not None:
                logger.info(f"TTS task queued for chat {chat_id}: {job.job_id}")
                return job.job_id
            
            return None
            
        except ImportError:
            logger.warning("Arq worker module not available")
            return None
        except Exception as e:
            logger.error(f"Failed to queue TTS task: {e}")
            return None


# Global TTS service instance
tts_service = TTSService()
