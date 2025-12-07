"""Text-to-Speech service for voice message generation.

This module provides TTS functionality including:
- Voice message generation with text truncation
- Auto-voice probability check (0.1% chance)
- Fallback to text on service unavailability
- Silero TTS model for Russian voice synthesis

**Feature: fortress-update, oleg-commands-fix**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import io
import logging
import random
from dataclasses import dataclass
from typing import Optional, Any

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
    Uses Silero TTS model for Russian voice synthesis.
    
    **Feature: fortress-update, oleg-commands-fix**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
    """
    
    # Silero TTS configuration
    SILERO_REPO = 'snakers4/silero-models'
    SILERO_MODEL = 'silero_tts'
    SILERO_LANGUAGE = 'ru'
    SILERO_SPEAKER = 'baya'  # Russian male voice
    SILERO_SAMPLE_RATE = 48000
    
    def __init__(self, tts_model: Optional[str] = None):
        """
        Initialize TTS service.
        
        Args:
            tts_model: TTS model to use (optional, for future extensibility)
        """
        self._tts_model_name = tts_model
        self._model: Optional[Any] = None  # Cached Silero model
        self._is_available = True  # Track service availability
        self._model_load_attempted = False  # Track if we tried to load model
    
    def _load_model(self) -> bool:
        """
        Lazy load Silero TTS model on first use.
        
        **Feature: oleg-commands-fix**
        **Validates: Requirements 5.1, 5.3**
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        # Return cached model if already loaded
        if self._model is not None:
            return True
        
        # Don't retry if we already failed
        if self._model_load_attempted and self._model is None:
            return False
        
        self._model_load_attempted = True
        
        try:
            import torch
            
            logger.info("Loading Silero TTS model...")
            
            # Load Silero TTS model from torch hub
            model, _ = torch.hub.load(
                repo_or_dir=self.SILERO_REPO,
                model=self.SILERO_MODEL,
                language=self.SILERO_LANGUAGE,
                speaker=self.SILERO_MODEL
            )
            
            self._model = model
            logger.info("Silero TTS model loaded successfully")
            return True
            
        except ImportError as e:
            logger.error(f"PyTorch not installed, TTS unavailable: {e}")
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"Failed to load Silero TTS model: {e}")
            self._is_available = False
            return False
    
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
        Generate audio data from text using Silero TTS model.
        
        **Feature: oleg-commands-fix**
        **Validates: Requirements 2.1, 5.1**
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data in OGG format, or None if unavailable
        """
        if not self._is_available:
            return None
        
        # Try to load model if not already loaded
        if not self._load_model():
            logger.warning("TTS model not available, returning None")
            return None
        
        try:
            import torch
            
            logger.debug(f"TTS generation requested for text: {text[:50]}...")
            
            # Generate audio tensor using Silero model
            audio_tensor = self._model.apply_tts(
                text=text,
                speaker=self.SILERO_SPEAKER,
                sample_rate=self.SILERO_SAMPLE_RATE
            )
            
            # Convert tensor to OGG format for Telegram
            ogg_data = self._convert_to_ogg(audio_tensor, self.SILERO_SAMPLE_RATE)
            
            if ogg_data is None:
                logger.error("Failed to convert audio to OGG format")
                return None
            
            logger.info(f"Generated TTS audio: {len(ogg_data)} bytes")
            return ogg_data
            
        except Exception as e:
            logger.error(f"TTS audio generation failed: {e}")
            return None
    
    def _convert_to_ogg(self, audio_tensor: Any, sample_rate: int) -> Optional[bytes]:
        """
        Convert audio tensor to OGG format for Telegram voice messages.
        
        **Feature: oleg-commands-fix**
        **Validates: Requirements 5.2**
        
        Args:
            audio_tensor: PyTorch tensor with audio data
            sample_rate: Sample rate of the audio
            
        Returns:
            OGG audio data as bytes, or None on failure
        """
        try:
            import numpy as np
            import soundfile as sf
            
            # Convert tensor to numpy array
            if hasattr(audio_tensor, 'numpy'):
                audio_np = audio_tensor.numpy()
            else:
                audio_np = np.array(audio_tensor)
            
            # Ensure audio is 1D
            if audio_np.ndim > 1:
                audio_np = audio_np.squeeze()
            
            # Normalize audio to [-1, 1] range if needed
            if audio_np.max() > 1.0 or audio_np.min() < -1.0:
                audio_np = audio_np / max(abs(audio_np.max()), abs(audio_np.min()))
            
            # Write to OGG format in memory
            buffer = io.BytesIO()
            sf.write(buffer, audio_np, sample_rate, format='OGG', subtype='VORBIS')
            buffer.seek(0)
            
            ogg_data = buffer.read()
            
            # Verify OGG magic bytes
            if not ogg_data.startswith(b'OggS'):
                logger.error("Generated audio does not have valid OGG header")
                return None
            
            return ogg_data
            
        except ImportError as e:
            logger.error(f"soundfile not installed, cannot convert to OGG: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to convert audio to OGG: {e}")
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
