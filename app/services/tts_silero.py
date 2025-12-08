"""Silero TTS Service for voice message generation.

Silero TTS - offline Russian TTS that works without internet restrictions.
Best option for Russia as it doesn't depend on external APIs.

Features:
- Works offline (no geo-blocking)
- High quality Russian voices
- Multiple voice options (male/female)
- Fast synthesis

**Feature: grand-casino-dictator**
"""

import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)


@dataclass
class SileroTTSResult:
    """Result of Silero TTS generation."""
    file_path: str
    audio_bytes: Optional[bytes]
    text: str
    speaker: str
    sample_rate: int
    created: bool
    sent: bool
    deleted: bool
    error: Optional[str]


class SileroTTSService:
    """
    TTS service using Silero models (offline, works in Russia).
    
    Available Russian speakers:
    - aidar (male)
    - baya (female)
    - kseniya (female)
    - xenia (female)
    - eugene (male)
    - random
    """
    
    SPEAKERS = {
        "male": "aidar",
        "male2": "eugene", 
        "female": "baya",
        "female2": "kseniya",
        "female3": "xenia",
    }
    
    DEFAULT_SPEAKER = "aidar"  # Male voice by default
    SAMPLE_RATE = 48000
    TEMP_DIR = tempfile.gettempdir()
    FILE_PREFIX = "oleg_silero_"
    FILE_SUFFIX = ".wav"
    
    def __init__(self, speaker: str = "male", preload: bool = False):
        """Initialize Silero TTS service.
        
        Args:
            speaker: Voice type - "male", "male2", "female", "female2", "female3"
            preload: If True, load model immediately (for Docker startup)
        """
        self._speaker = self.SPEAKERS.get(speaker, self.DEFAULT_SPEAKER)
        self._model = None
        self._is_available = True
        self._init_attempted = False
        
        if preload:
            # Sync preload for Docker startup
            self._preload_model()
    
    def _preload_model(self) -> None:
        """Preload model synchronously (for Docker startup)."""
        try:
            logger.info("Preloading Silero TTS model...")
            self._model = self._load_model()
            if self._model:
                logger.info(f"Silero TTS model preloaded, speaker: {self._speaker}")
                self._init_attempted = True
            else:
                logger.warning("Silero model preload failed")
                self._is_available = False
        except Exception as e:
            logger.error(f"Silero preload error: {e}")
            self._is_available = False
    
    async def _ensure_model(self) -> bool:
        """Lazy load Silero model on first use."""
        if self._model is not None:
            return True
        
        if self._init_attempted and not self._is_available:
            return False
        
        self._init_attempted = True
        
        try:
            import torch
            
            logger.info("Loading Silero TTS model...")
            
            # Load model in thread pool to not block
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(None, self._load_model)
            
            if self._model is None:
                self._is_available = False
                return False
            
            logger.info(f"Silero TTS model loaded, speaker: {self._speaker}")
            return True
            
        except ImportError as e:
            logger.error(f"Silero dependencies not installed: {e}")
            logger.error("Install with: pip install torch")
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"Failed to load Silero model: {e}")
            self._is_available = False
            return False
    
    def _load_model(self):
        """Load Silero model (sync, runs in executor)."""
        try:
            import torch
            
            device = torch.device('cpu')
            torch.set_num_threads(4)
            
            model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language='ru',
                speaker='v4_ru'
            )
            model.to(device)
            return model
        except Exception as e:
            logger.error(f"Silero model load error: {e}")
            return None
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._is_available
    
    @property
    def speaker(self) -> str:
        """Get current speaker."""
        return self._speaker
    
    def set_speaker(self, speaker: str) -> None:
        """Set speaker voice."""
        if speaker in self.SPEAKERS:
            self._speaker = self.SPEAKERS[speaker]
        elif speaker in self.SPEAKERS.values():
            self._speaker = speaker
        else:
            logger.warning(f"Unknown speaker '{speaker}', keeping {self._speaker}")
    
    def _generate_temp_path(self) -> str:
        """Generate unique temp file path."""
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{self.FILE_PREFIX}{unique_id}{self.FILE_SUFFIX}"
        return os.path.join(self.TEMP_DIR, filename)
    
    async def synthesize(self, text: str, speaker: Optional[str] = None) -> Optional[bytes]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to convert to speech
            speaker: Optional speaker override
            
        Returns:
            Audio bytes in WAV format, or None on failure
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None
        
        if not await self._ensure_model():
            return None
        
        use_speaker = speaker if speaker in self.SPEAKERS.values() else self._speaker
        if speaker in self.SPEAKERS:
            use_speaker = self.SPEAKERS[speaker]
        
        try:
            import torch
            import io
            import wave
            
            loop = asyncio.get_event_loop()
            
            def _synthesize():
                audio = self._model.apply_tts(
                    text=text,
                    speaker=use_speaker,
                    sample_rate=self.SAMPLE_RATE
                )
                return audio
            
            audio_tensor = await loop.run_in_executor(None, _synthesize)
            
            # Convert to WAV bytes
            audio_numpy = audio_tensor.numpy()
            
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.SAMPLE_RATE)
                # Convert float32 to int16
                import numpy as np
                audio_int16 = (audio_numpy * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            
            audio_bytes = buffer.getvalue()
            logger.info(f"Silero synthesized {len(audio_bytes)} bytes with {use_speaker}")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Silero synthesis failed: {e}")
            return None
    
    async def synthesize_to_file(self, text: str, speaker: Optional[str] = None) -> SileroTTSResult:
        """Synthesize speech and save to temp file."""
        file_path = self._generate_temp_path()
        use_speaker = self._speaker
        if speaker:
            if speaker in self.SPEAKERS:
                use_speaker = self.SPEAKERS[speaker]
            elif speaker in self.SPEAKERS.values():
                use_speaker = speaker
        
        result = SileroTTSResult(
            file_path=file_path,
            audio_bytes=None,
            text=text,
            speaker=use_speaker,
            sample_rate=self.SAMPLE_RATE,
            created=False,
            sent=False,
            deleted=False,
            error=None
        )
        
        if not text or not text.strip():
            result.error = "Empty text provided"
            return result
        
        if not await self._ensure_model():
            result.error = "Silero model not available"
            return result
        
        try:
            import torch
            
            loop = asyncio.get_event_loop()
            
            def _synthesize_to_file():
                audio = self._model.apply_tts(
                    text=text,
                    speaker=use_speaker,
                    sample_rate=self.SAMPLE_RATE
                )
                # Save directly using model's save method
                self._model.save_wav(audio=audio, path=file_path, sample_rate=self.SAMPLE_RATE)
                return True
            
            await loop.run_in_executor(None, _synthesize_to_file)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                result.created = True
                with open(file_path, "rb") as f:
                    result.audio_bytes = f.read()
                logger.info(f"Created Silero TTS file: {file_path}")
            else:
                result.error = "File creation failed"
                
        except Exception as e:
            result.error = str(e)
            logger.error(f"Silero file synthesis failed: {e}")
        
        return result
    
    def delete_temp_file(self, file_path: str) -> bool:
        """Delete temp file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted temp file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete temp file: {e}")
            return False
    
    async def send_voice(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        speaker: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> SileroTTSResult:
        """Generate and send voice message."""
        result = await self.synthesize_to_file(text, speaker)
        
        if not result.created:
            result.deleted = self.delete_temp_file(result.file_path)
            return result
        
        try:
            voice_file = FSInputFile(result.file_path)
            await bot.send_voice(
                chat_id=chat_id,
                voice=voice_file,
                reply_to_message_id=reply_to_message_id
            )
            result.sent = True
            logger.info(f"Sent Silero voice to chat {chat_id}")
        except Exception as e:
            result.error = f"Failed to send voice: {e}"
            logger.error(result.error)
        finally:
            result.deleted = self.delete_temp_file(result.file_path)
        
        return result


# Global instance
silero_tts_service = SileroTTSService()
