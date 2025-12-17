"""
Property-based tests for Web Search Trigger Detection.

Tests correctness properties defined in the design document.
**Feature: oleg-personality-improvements, Property 1: Search keywords trigger web search**
**Feature: anti-hallucination-v1**
**Validates: Requirements 1.3**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import web_search_trigger module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'web_search_trigger.py')
_spec = importlib.util.spec_from_file_location("web_search_trigger", _module_path)
_trigger_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_trigger_module)
# Use the simple version that returns bool for backward compatibility
should_trigger_web_search = _trigger_module.should_trigger_web_search_simple
WEB_SEARCH_TRIGGER_KEYWORDS = _trigger_module.WEB_SEARCH_TRIGGER_KEYWORDS


class TestWebSearchKeywordTrigger:
    """
    **Feature: oleg-personality-improvements, Property 1: Search keywords trigger web search**
    **Validates: Requirements 1.3**
    
    *For any* user message containing keywords ["вышла", "релиз", "новости", "когда выйдет", 
    "цена", "сколько стоит"], the `should_trigger_web_search` function SHALL return True.
    """
    
    @settings(max_examples=100)
    @given(st.sampled_from(WEB_SEARCH_TRIGGER_KEYWORDS))
    def test_keyword_triggers_search(self, keyword: str):
        """
        Property 1a: Any message containing a trigger keyword should trigger web search.
        """
        # Create message with keyword
        message = f"Привет, {keyword} что-нибудь интересное?"
        
        result = should_trigger_web_search(message)
        assert result is True, \
            f"Message with keyword '{keyword}' should trigger web search"
    
    @settings(max_examples=100)
    @given(st.sampled_from(WEB_SEARCH_TRIGGER_KEYWORDS))
    def test_keyword_case_insensitive(self, keyword: str):
        """
        Property 1b: Keyword detection should be case-insensitive.
        """
        # Test uppercase
        message_upper = f"Привет, {keyword.upper()} что-нибудь?"
        result_upper = should_trigger_web_search(message_upper)
        
        # Test mixed case
        message_title = f"Привет, {keyword.title()} что-нибудь?"
        result_title = should_trigger_web_search(message_title)
        
        assert result_upper is True, \
            f"Uppercase keyword '{keyword.upper()}' should trigger search"
        assert result_title is True, \
            f"Title case keyword '{keyword.title()}' should trigger search"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=5, max_size=100).filter(
            lambda t: not any(kw in t.lower() for kw in WEB_SEARCH_TRIGGER_KEYWORDS)
        )
    )
    def test_no_keyword_no_trigger(self, text: str):
        """
        Property 1c: Messages without trigger keywords should not trigger web search.
        """
        # Ensure no keywords present
        assume(not any(kw in text.lower() for kw in WEB_SEARCH_TRIGGER_KEYWORDS))
        
        result = should_trigger_web_search(text)
        assert result is False, \
            f"Message without keywords should not trigger search: '{text[:50]}...'"
    
    @settings(max_examples=100)
    @given(st.sampled_from(WEB_SEARCH_TRIGGER_KEYWORDS), st.text(min_size=0, max_size=50))
    def test_keyword_with_context(self, keyword: str, context: str):
        """
        Property 1d: Keyword should trigger search regardless of surrounding context.
        """
        message = f"{context} {keyword} {context}"
        
        result = should_trigger_web_search(message)
        assert result is True, \
            f"Keyword '{keyword}' with context should trigger search"
    
    def test_empty_string_no_trigger(self):
        """
        Property 1e: Empty string should not trigger web search.
        """
        result = should_trigger_web_search("")
        assert result is False, "Empty string should not trigger search"
    
    def test_none_handling(self):
        """
        Property 1f: None input should not trigger web search (and not crash).
        """
        result = should_trigger_web_search(None)
        assert result is False, "None should not trigger search"


class TestWebSearchReleaseKeywords:
    """
    Tests specifically for release/news related keywords.
    **Validates: Requirements 1.1, 1.3**
    """
    
    @settings(max_examples=50)
    @given(st.sampled_from(["вышла", "вышел", "вышло", "релиз", "выйдет", "когда выйдет"]))
    def test_release_keywords_trigger(self, keyword: str):
        """
        Release-related keywords should always trigger search.
        """
        messages = [
            f"Когда {keyword} новая игра?",
            f"Уже {keyword}?",
            f"Слышал что {keyword} патч",
        ]
        
        for msg in messages:
            result = should_trigger_web_search(msg)
            assert result is True, \
                f"Release keyword '{keyword}' in '{msg}' should trigger search"


class TestWebSearchPriceKeywords:
    """
    Tests specifically for price-related keywords.
    **Validates: Requirements 1.3**
    """
    
    @settings(max_examples=50)
    @given(st.sampled_from(["сколько стоит", "цена", "ценник", "где купить"]))
    def test_price_keywords_trigger(self, keyword: str):
        """
        Price-related keywords should always trigger search.
        """
        messages = [
            f"{keyword} RTX 4090?",
            f"Подскажи {keyword}",
            f"Интересует {keyword} на это",
        ]
        
        for msg in messages:
            result = should_trigger_web_search(msg)
            assert result is True, \
                f"Price keyword '{keyword}' in '{msg}' should trigger search"
