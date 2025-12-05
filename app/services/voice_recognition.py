"""Сервис распознавания голосовых сообщений (STT)."""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Флаг доступности whisper
_whisper_available = False
_whisper_model = None

try:
    import whisper
    _whisper_available = True
    logger.info("Whisper успешно импортирован")
except ImportError:
    logger.warning("Whisper не установлен. Распознавание голосовых недоступно. Установи: pip install openai-whisper")


async def init_whisper():
    """Инициализирует модель Whisper."""
    global _whisper_model
    
    if not _whisper_available:
        logger.warning("Whisper недоступен, пропускаем инициализацию")
        return False
    
    try:
        from app.config import settings
        model_name = settings.whisper_model
        
        logger.info(f"Загрузка модели Whisper: {model_name}...")
        _whisper_model = whisper.load_model(model_name)
        logger.info(f"Модель Whisper '{model_name}' загружена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке модели Whisper: {e}")
        return False


def is_available() -> bool:
    """Проверяет, доступно ли распознавание голоса."""
    return _whisper_available and _whisper_model is not None


async def transcribe_voice(file_path: str) -> Optional[str]:
    """
    Распознаёт речь из аудиофайла.
    
    Args:
        file_path: Путь к аудиофайлу (ogg, mp3, wav и т.д.)
        
    Returns:
        Распознанный текст или None при ошибке
    """
    if not is_available():
        logger.warning("Whisper недоступен для распознавания")
        return None
    
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return None
    
    try:
        logger.info(f"Начинаю распознавание: {file_path}")
        
        # Whisper работает синхронно, но файлы обычно небольшие
        result = _whisper_model.transcribe(
            file_path,
            language="ru",  # Приоритет русского языка
            fp16=False  # Для совместимости с CPU
        )
        
        text = result.get("text", "").strip()
        
        if text:
            logger.info(f"Распознано: {text[:100]}...")
        else:
            logger.warning("Пустой результат распознавания")
            
        return text if text else None
        
    except Exception as e:
        logger.error(f"Ошибка при распознавании голоса: {e}")
        return None


async def transcribe_voice_message(bot, file_id: str) -> Optional[str]:
    """
    Скачивает и распознаёт голосовое сообщение из Telegram.
    
    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        
    Returns:
        Распознанный текст или None
    """
    if not is_available():
        return None
    
    temp_file = None
    try:
        # Получаем информацию о файле
        file_info = await bot.get_file(file_id)
        
        # Создаём временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        temp_path = temp_file.name
        temp_file.close()
        
        # Скачиваем файл
        await bot.download_file(file_info.file_path, destination=temp_path)
        logger.info(f"Голосовое скачано: {temp_path}")
        
        # Распознаём
        text = await transcribe_voice(temp_path)
        
        return text
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        return None
        
    finally:
        # Удаляем временный файл
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Временный файл удалён: {temp_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл: {e}")


async def transcribe_video_note(bot, file_id: str) -> Optional[str]:
    """
    Скачивает видеосообщение (кружочек), извлекает аудио и распознаёт речь.
    
    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        
    Returns:
        Распознанный текст или None
    """
    import subprocess
    
    if not is_available():
        return None
    
    temp_video = None
    temp_audio = None
    try:
        # Получаем информацию о файле
        file_info = await bot.get_file(file_id)
        
        # Создаём временный файл для видео
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        video_path = temp_video.name
        temp_video.close()
        
        # Скачиваем видео
        await bot.download_file(file_info.file_path, destination=video_path)
        logger.info(f"Видеосообщение скачано: {video_path}")
        
        # Создаём временный файл для аудио
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_path = temp_audio.name
        temp_audio.close()
        
        # Извлекаем аудио с помощью ffmpeg
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn",  # Без видео
            "-acodec", "pcm_s16le",  # WAV формат
            "-ar", "16000",  # 16kHz для Whisper
            "-ac", "1",  # Моно
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg ошибка: {result.stderr}")
            return None
        
        logger.info(f"Аудио извлечено: {audio_path}")
        
        # Распознаём
        text = await transcribe_voice(audio_path)
        
        return text
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg таймаут при извлечении аудио")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg не найден. Установи ffmpeg для распознавания видеосообщений.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при обработке видеосообщения: {e}")
        return None
        
    finally:
        # Удаляем временные файлы
        for path in [video_path if temp_video else None, audio_path if temp_audio else None]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.debug(f"Временный файл удалён: {path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл: {e}")
