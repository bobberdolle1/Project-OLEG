"""Text-to-Speech service for voice message generation.

This module provides TTS functionality including:
- Voice message generation with text truncation
- Auto-voice probability check (0.1% chance)
- Fallback to text on service unavailability
- Edge TTS for Russian voice synthesis (Microsoft)

**Feature: fortress-update, oleg-commands-fix**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import io
import logging
import random
import asyncio
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
    format: str  # mp3
    original_text: str
    was_truncated: bool


class TTSService:
    """
    Text-to-Speech service for generating voice messages.
    
    Provides voice generation with Oleg's characteristic voice,
    text truncation for long messages, and auto-voice probability.
    Uses Edge TTS (Microsoft) for Russian voice synthesis.
    
    **Feature: fortress-update, oleg-commands-fix**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
    """
    
    # Edge TTS configuration - Russian male voice
    EDGE_VOICE = "ru-RU-DmitryNeural"  # Russian male voice (closest to "Oleg")
    
    def __init__(self, tts_model: Optional[str] = None):
        """
        Initialize TTS service.
        
        Args:
            tts_model: TTS model/voice to use (optional)
        """
        self._voice = tts_model or self.EDGE_VOICE
        self._is_available = True
    
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
            # Generate voice using Edge TTS
            audio_data = await self._generate_audio(processed_text)
            
            if audio_data is None:
                return None
            
            return TTSResult(
                audio_data=audio_data,
                duration_seconds=self._estimate_duration(processed_text),
                format="mp3",
                original_text=processed_text,
                was_truncated=was_truncated
            )
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None
    
    async def _generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generate audio data from text using Edge TTS.
        
        **Feature: oleg-commands-fix**
        **Validates: Requirements 2.1, 5.1**
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data in MP3 format, or None if unavailable
        """
        if not self._is_available:
            return None
        
        try:
            import edge_tts
            
            logger.debug(f"TTS generation requested for text: {text[:50]}...")
            
            # Create communicate object with Russian male voice
            communicate = edge_tts.Communicate(text, self._voice)
            
            # Collect audio data
            audio_buffer = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            
            audio_data = audio_buffer.getvalue()
            
            if not audio_data:
                logger.error("Edge TTS returned empty audio")
                return None
            
            logger.info(f"Generated TTS audio: {len(audio_data)} bytes")
            return audio_data
            
        except ImportError:
            logger.error("edge-tts not installed. Install with: pip install edge-tts")
            self._is_available = False
            return None
        except Exception as e:
            logger.error(f"TTS audio generation failed: {e}")
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
