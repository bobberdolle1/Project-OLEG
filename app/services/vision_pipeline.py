"""
Vision Pipeline - двухэтапный pipeline для анализа изображений с сохранением личности Олега.

Step 1: Vision model описывает изображение (скрыто от пользователя)
Step 2: Oleg LLM комментирует описание в своём стиле
"""

import base64
import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

import httpx

from app.config import settings
from app.services.think_filter import think_filter

logger = logging.getLogger(__name__)


@dataclass
class VisionPipelineState:
    """Состояние pipeline для сериализации/десериализации."""
    
    image_hash: str
    description: str
    final_response: str
    
    def to_json(self) -> str:
        """Сериализует состояние в JSON строку."""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "VisionPipelineState":
        """Десериализует состояние из JSON строки."""
        data = json.loads(json_str)
        return cls(**data)


class VisionPipeline:
    """Двухэтапный pipeline для анализа изображений."""
    
    # Технический промпт для Vision модели (Step 1)
    VISION_DESCRIPTION_PROMPT = """Describe the image content in detail. Focus on:
- What objects, people, or scenes are visible
- Any text, error messages, or technical information shown
- Hardware components, software interfaces, or code if present
- Overall context and purpose of the image

Be factual and descriptive. Do not add opinions or commentary.

IMPORTANT: Respond with the description directly. Do NOT use <think> tags or any internal reasoning tags. Just describe what you see."""
    
    # Промпт для Oleg LLM (Step 2)
    OLEG_COMMENT_TEMPLATE = """Юзер прислал фото. На нем: {description}

{user_query}

Прокомментируй в своём стиле. Если это техническая проблема — дай решение. Если мем — кратко отреагируй."""
    
    # Системный промпт для Олега при комментировании изображений
    OLEG_VISION_SYSTEM_PROMPT = """ТЫ — ОЛЕГ, циничный IT-эксперт из технического чата. Сейчас 2025 год.

ТВОЯ ЗАДАЧА — прокомментировать изображение, которое тебе описали.

ПРАВИЛА:
• Говори как живой человек, не как робот
• Если видишь техническую проблему — сразу давай решение
• Если это мем или ерунда — кратко отреагируй, не растекайся
• Можешь подколоть если видишь косяк
• Не повторяй описание — сразу комментируй

ФАКТЧЕКИНГ (ВАЖНО):
• Если видишь железо (видеокарты, процессоры) — НЕ ВЫДУМЫВАЙ факты
• Если есть результаты поиска — ИСПОЛЬЗУЙ их для проверки
• RTX 50xx серия УЖЕ АНОНСИРОВАНА на CES 2025 — это не фейк
• Не говори что что-то "не существует" если не уверен — лучше промолчи

НЕ НЕСИ БРЕД:
• Описывай ТОЛЬКО то что реально видишь на фото
• НЕ выдумывай проблемы — "шланг не до конца подключен" это бред если ты этого не видишь
• Если не видишь явной проблемы — так и скажи, не придумывай диагнозы
• Лучше сказать "выглядит норм" чем выдумать несуществующую проблему

СТИЛЬ:
• Коротко и по делу (2-5 предложений)
• Технический жаргон где уместно
• Грубовато, но по существу
• Грамотно — следи за согласованием (неплохая сборка, не "неплохой")"""

    ERROR_VISION_UNAVAILABLE = "Глаза не работают, но уши на месте. Опиши словами что там."
    ERROR_ANALYSIS_FAILED = "Не смог разглядеть что там на картинке. Попробуй другую."
    
    def __init__(self):
        """Инициализация pipeline."""
        self._timeout = settings.ollama_timeout
        self._base_url = settings.ollama_base_url
    
    async def analyze(self, image_data: bytes, user_query: Optional[str] = None) -> str:
        """
        Анализирует изображение через 2-step pipeline.
        
        Step 1: Vision model описывает изображение (скрыто от пользователя)
        Step 2: Oleg LLM комментирует описание в своём стиле
        
        Args:
            image_data: Байты изображения
            user_query: Опциональный вопрос пользователя к изображению
            
        Returns:
            Комментарий Олега к изображению
        """
        # Step 1: Получаем описание от Vision модели
        description = await self._get_image_description(image_data)
        
        if not description:
            return self.ERROR_VISION_UNAVAILABLE
        
        # Step 2: Генерируем комментарий Олега
        final_response = await self._generate_oleg_comment(description, user_query)
        
        if not final_response:
            return self.ERROR_ANALYSIS_FAILED
        
        return final_response
    
    async def analyze_with_state(self, image_data: bytes, user_query: Optional[str] = None) -> tuple[str, VisionPipelineState]:
        """
        Анализирует изображение и возвращает состояние pipeline.
        
        Args:
            image_data: Байты изображения
            user_query: Опциональный вопрос пользователя
            
        Returns:
            Tuple (ответ, состояние pipeline)
        """
        # Вычисляем хеш изображения
        image_hash = hashlib.sha256(image_data).hexdigest()[:16]
        
        # Step 1: Получаем описание
        description = await self._get_image_description(image_data)
        
        if not description:
            state = VisionPipelineState(
                image_hash=image_hash,
                description="",
                final_response=self.ERROR_VISION_UNAVAILABLE
            )
            return self.ERROR_VISION_UNAVAILABLE, state
        
        # Step 2: Генерируем комментарий
        final_response = await self._generate_oleg_comment(description, user_query)
        
        if not final_response:
            final_response = self.ERROR_ANALYSIS_FAILED
        
        state = VisionPipelineState(
            image_hash=image_hash,
            description=description,
            final_response=final_response
        )
        
        return final_response, state
    
    async def _get_image_description(self, image_data: bytes) -> Optional[str]:
        """
        Получает техническое описание от Vision модели.
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Описание изображения или None при ошибке
        """
        try:
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Используем fallback vision модель если основная недоступна
            from app.services.ollama_client import get_active_model
            vision_model = await get_active_model("vision")
            
            # Формат для Ollama vision API
            # Некоторые модели требуют images на уровне сообщения, другие — отдельно
            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": self.VISION_DESCRIPTION_PROMPT,
                        "images": [image_base64]
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 4096,
                    "num_predict": 1024  # Увеличиваем лимит токенов
                }
            }
            
            # Логируем размер изображения
            logger.info(f"Vision Step 1: Image size {len(image_data)} bytes, base64 {len(image_base64)} chars")
            
            logger.info(f"Vision Step 1: Requesting description from {vision_model}")
            
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Логируем полный ответ для диагностики
                logger.debug(f"Vision Step 1: Full API response keys: {list(data.keys())}")
                
                message = data.get("message", {})
                raw_content = message.get("content", "").strip()
                
                # Проверяем альтернативные поля ответа
                if not raw_content:
                    # Некоторые модели возвращают в response напрямую
                    raw_content = data.get("response", "").strip()
                
                if not raw_content:
                    # Проверяем done_reason — может быть ошибка
                    done_reason = data.get("done_reason", "")
                    if done_reason:
                        logger.warning(f"Vision Step 1: done_reason={done_reason}")
                
                # Логируем сырой ответ для диагностики
                if raw_content:
                    logger.debug(f"Vision Step 1: Raw response ({len(raw_content)} chars): {raw_content[:200]}...")
                else:
                    logger.warning(f"Vision Step 1: Model returned empty content. Full response: {str(data)[:500]}")
                    return None
                
                # Фильтруем thinking-теги если есть
                content = think_filter.filter(raw_content)
                
                if content and content != think_filter.fallback_message:
                    logger.info(f"Vision Step 1: Got description ({len(content)} chars)")
                    return content
                
                # Если после фильтрации пусто — возможно весь ответ был в think-тегах
                # Попробуем извлечь контент из think-тегов как fallback
                import re
                think_match = re.search(r'<think>(.*?)</think>', raw_content, re.DOTALL | re.IGNORECASE)
                if think_match:
                    think_content = think_match.group(1).strip()
                    if think_content:
                        logger.warning(f"Vision Step 1: Using think content as fallback ({len(think_content)} chars)")
                        return think_content
                
                logger.warning(f"Vision Step 1: Empty after filter. Raw was: {raw_content[:100]}...")
                return None
                
        except httpx.ConnectError:
            logger.error("Vision Step 1: Cannot connect to Ollama server")
            return None
        except httpx.TimeoutException:
            logger.error("Vision Step 1: Timeout waiting for Vision model")
            return None
        except Exception as e:
            logger.error(f"Vision Step 1: Error getting description: {e}")
            return None
    
    async def _generate_oleg_comment(self, description: str, user_query: Optional[str] = None) -> Optional[str]:
        """
        Генерирует комментарий в стиле Олега.
        
        Args:
            description: Описание изображения от Vision модели
            user_query: Опциональный вопрос пользователя
            
        Returns:
            Комментарий Олега или None при ошибке
        """
        try:
            # Проверяем нужен ли веб-поиск для фактчекинга
            from app.services.web_search_trigger import should_trigger_web_search
            from app.services.ollama_client import _execute_web_search
            
            # Объединяем описание и вопрос для проверки триггеров
            combined_text = f"{description} {user_query or ''}"
            search_results = None
            
            needs_search, _ = should_trigger_web_search(combined_text)
            if needs_search and settings.ollama_web_search_enabled:
                logger.info(f"Vision Step 2: Triggering web search for factcheck")
                try:
                    # Ищем по ключевым словам из описания
                    search_results_text, _ = await _execute_web_search(combined_text[:200])
                    if search_results_text:
                        search_results = search_results_text
                        logger.info(f"Vision Step 2: Got search results ({len(search_results)} chars)")
                except Exception as e:
                    logger.warning(f"Vision Step 2: Web search failed: {e}")
            
            # Формируем промпт с описанием и вопросом пользователя
            query_part = f"Вопрос пользователя: {user_query}" if user_query else "Пользователь просто прислал картинку без вопроса."
            
            user_prompt = self.OLEG_COMMENT_TEMPLATE.format(
                description=description,
                user_query=query_part
            )
            
            # Добавляем результаты поиска если есть
            if search_results:
                user_prompt += f"\n\nАКТУАЛЬНАЯ ИНФА ИЗ ИНТЕРНЕТА (используй для фактчекинга):\n{search_results}"
            
            # Используем fallback модель если основная недоступна
            from app.services.ollama_client import get_active_model
            active_model = await get_active_model("base")
            
            payload = {
                "model": active_model,
                "messages": [
                    {
                        "role": "system",
                        "content": self.OLEG_VISION_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.7,  # Больше креативности для Олега
                    "num_ctx": 4096,
                    "num_predict": 256
                }
            }
            
            logger.info(f"Vision Step 2: Generating Oleg comment with {active_model}")
            
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "").strip()
                
                # Фильтруем thinking-теги
                content = think_filter.filter(content)
                
                if content and content != think_filter.fallback_message:
                    logger.info(f"Vision Step 2: Generated comment ({len(content)} chars)")
                    return content
                
                logger.warning("Vision Step 2: Empty comment from model")
                return None
                
        except httpx.ConnectError:
            logger.error("Vision Step 2: Cannot connect to Ollama server")
            return None
        except httpx.TimeoutException:
            logger.error("Vision Step 2: Timeout waiting for LLM")
            return None
        except Exception as e:
            logger.error(f"Vision Step 2: Error generating comment: {e}")
            return None


# Глобальный экземпляр pipeline для удобства использования
vision_pipeline = VisionPipeline()
