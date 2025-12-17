"""
Web Search Service — улучшенный веб-поиск с несколькими провайдерами.

Поддерживает:
- Brave Search API (рекомендуется, бесплатный tier 2000 запросов/месяц)
- DuckDuckGo HTML (fallback, без API ключа)

**Feature: anti-hallucination-v1**
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Результат поиска."""
    title: str
    snippet: str
    url: str
    source: str  # brave, duckduckgo
    freshness: Optional[str] = None  # дата публикации если есть


@dataclass
class SearchResponse:
    """Ответ поискового сервиса."""
    results: list[SearchResult]
    query: str
    provider: str
    cached: bool = False
    error: Optional[str] = None


class WebSearchService:
    """
    Сервис веб-поиска с поддержкой нескольких провайдеров.
    
    Приоритет:
    1. Brave Search API (если есть ключ)
    2. DuckDuckGo HTML (fallback)
    """
    
    def __init__(self):
        self.brave_api_key = getattr(settings, 'brave_search_api_key', None)
        self._cache: dict[str, tuple[SearchResponse, float]] = {}
        self._cache_ttl = 300  # 5 минут
    
    async def search(
        self, 
        query: str, 
        max_results: int = 10,
        freshness: str = "month"  # day, week, month, year
    ) -> SearchResponse:
        """
        Выполняет веб-поиск.
        
        Args:
            query: Поисковый запрос
            max_results: Максимум результатов
            freshness: Фильтр по свежести (для Brave)
            
        Returns:
            SearchResponse с результатами
        """
        # Проверяем кэш
        cache_key = f"{query}:{max_results}:{freshness}"
        if cache_key in self._cache:
            response, timestamp = self._cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < self._cache_ttl:
                logger.debug(f"[SEARCH] Cache hit for: {query[:30]}...")
                response.cached = True
                return response
        
        # Пробуем Brave если есть ключ
        if self.brave_api_key:
            response = await self._search_brave(query, max_results, freshness)
            if response.results:
                self._cache[cache_key] = (response, datetime.now().timestamp())
                return response
            logger.warning(f"[SEARCH] Brave failed, falling back to DuckDuckGo")
        
        # Fallback на DuckDuckGo
        response = await self._search_duckduckgo(query, max_results)
        if response.results:
            self._cache[cache_key] = (response, datetime.now().timestamp())
        
        return response
    
    async def _search_brave(
        self, 
        query: str, 
        max_results: int,
        freshness: str
    ) -> SearchResponse:
        """Поиск через Brave Search API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={
                        "q": query,
                        "count": max_results,
                        "freshness": freshness,
                        "text_decorations": False,
                    },
                    headers={
                        "X-Subscription-Token": self.brave_api_key,
                        "Accept": "application/json",
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get("web", {}).get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("description", ""),
                        url=item.get("url", ""),
                        source="brave",
                        freshness=item.get("age"),
                    ))
                
                logger.info(f"[BRAVE] Found {len(results)} results for: {query[:30]}...")
                return SearchResponse(
                    results=results,
                    query=query,
                    provider="brave"
                )
                
        except Exception as e:
            logger.warning(f"[BRAVE] Search error: {e}")
            return SearchResponse(
                results=[],
                query=query,
                provider="brave",
                error=str(e)
            )
    
    async def _search_duckduckgo(
        self, 
        query: str, 
        max_results: int
    ) -> SearchResponse:
        """Поиск через DuckDuckGo HTML (без API)."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()
                
                html = response.text
                results = []
                
                # Парсим результаты
                snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
                titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', html)
                urls = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
                
                for i, (title, snippet) in enumerate(zip(titles[:max_results], snippets[:max_results])):
                    title = title.replace("&amp;", "&").replace("&quot;", '"').strip()
                    snippet = snippet.replace("&amp;", "&").replace("&quot;", '"').strip()
                    url = urls[i] if i < len(urls) else ""
                    
                    if title and snippet:
                        results.append(SearchResult(
                            title=title,
                            snippet=snippet,
                            url=url,
                            source="duckduckgo"
                        ))
                
                logger.info(f"[DDG] Found {len(results)} results for: {query[:30]}...")
                return SearchResponse(
                    results=results,
                    query=query,
                    provider="duckduckgo"
                )
                
        except Exception as e:
            logger.warning(f"[DDG] Search error: {e}")
            return SearchResponse(
                results=[],
                query=query,
                provider="duckduckgo",
                error=str(e)
            )
    
    async def search_with_variations(
        self, 
        query: str, 
        max_results: int = 10
    ) -> SearchResponse:
        """
        Поиск с вариациями запроса для лучшего покрытия.
        
        Генерирует несколько вариантов запроса и объединяет результаты.
        """
        variations = self._generate_variations(query)
        all_results: list[SearchResult] = []
        seen_titles: set[str] = set()
        
        # Выполняем поиски параллельно
        tasks = [self.search(q, max_results=7) for q in variations[:3]]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for response in responses:
            if isinstance(response, Exception):
                continue
            for result in response.results:
                title_key = result.title.lower()[:50]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_results.append(result)
        
        return SearchResponse(
            results=all_results[:max_results],
            query=query,
            provider="multi"
        )
    
    def _generate_variations(self, query: str) -> list[str]:
        """Генерирует вариации поискового запроса."""
        variations = [query]
        query_lower = query.lower()
        
        # Добавляем год для актуальности
        current_year = str(datetime.now().year)
        if current_year not in query:
            variations.append(f"{query} {current_year}")
        
        # Технические переводы
        tech_terms = {
            "видеокарта": "GPU",
            "процессор": "CPU",
            "характеристики": "specs",
            "сравнение": "vs comparison",
            "обзор": "review",
        }
        
        for ru, en in tech_terms.items():
            if ru in query_lower:
                variations.append(f"{query} {en}")
                break
        
        return variations[:4]
    
    def format_for_prompt(self, response: SearchResponse) -> str:
        """
        Форматирует результаты поиска для включения в промпт LLM.
        
        Args:
            response: Ответ поискового сервиса
            
        Returns:
            Отформатированная строка
        """
        if not response.results:
            return "Поиск не дал результатов."
        
        lines = [f"Результаты поиска по запросу \"{response.query}\":"]
        
        for i, result in enumerate(response.results, 1):
            freshness_info = f" [{result.freshness}]" if result.freshness else ""
            lines.append(f"{i}. {result.title}{freshness_info}")
            lines.append(f"   {result.snippet}")
        
        return "\n".join(lines)


# Глобальный экземпляр
web_search = WebSearchService()
