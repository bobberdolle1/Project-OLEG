"""
Unit tests for Web Search Trigger v2 (anti-hallucination).

**Feature: anti-hallucination-v1**
"""

import pytest
from app.services.web_search_trigger import (
    should_trigger_web_search,
    should_trigger_web_search_simple,
    HIGH_PRIORITY_TRIGGERS,
)


class TestWebSearchTrigger:
    """Tests for web search trigger detection."""
    
    def test_triggers_on_price_question(self):
        """Should trigger on price questions."""
        result, reason = should_trigger_web_search("сколько стоит RTX 4070?")
        assert result is True
        assert "keyword" in reason or "model_pattern" in reason
    
    def test_triggers_on_specs_question(self):
        """Should trigger on specs questions."""
        result, reason = should_trigger_web_search("какие характеристики у RX 7800 XT?")
        assert result is True
    
    def test_triggers_on_comparison(self):
        """Should trigger on comparison questions."""
        result, reason = should_trigger_web_search("что лучше RTX 4070 или RX 7800 XT?")
        assert result is True
    
    def test_triggers_on_release_question(self):
        """Should trigger on release questions."""
        result, reason = should_trigger_web_search("когда выйдет RTX 5090?")
        assert result is True
    
    def test_triggers_on_gpu_model_number(self):
        """Should trigger on GPU model numbers."""
        result, reason = should_trigger_web_search("расскажи про 4070 Ti Super")
        assert result is True
        assert "model_pattern" in reason
    
    def test_triggers_on_cpu_model(self):
        """Should trigger on CPU model numbers."""
        result, reason = should_trigger_web_search("какой i7-13700K лучше?")
        assert result is True
    
    def test_triggers_on_architecture(self):
        """Should trigger on architecture mentions."""
        result, reason = should_trigger_web_search("что такое RDNA 3?")
        assert result is True
    
    def test_not_triggers_on_bot_question(self):
        """Should NOT trigger on questions about the bot."""
        result, reason = should_trigger_web_search("какие твои характеристики?")
        assert result is False
        assert reason == "question_about_bot"
    
    def test_not_triggers_on_simple_message(self):
        """Should NOT trigger on simple messages."""
        result, reason = should_trigger_web_search("привет, как дела?")
        assert result is False
    
    def test_simple_version_returns_bool(self):
        """Simple version should return just bool."""
        result = should_trigger_web_search_simple("сколько стоит RTX 4070?")
        assert isinstance(result, bool)
        assert result is True


class TestHighPriorityTriggers:
    """Tests for high priority trigger patterns."""
    
    def test_vram_question(self):
        """Should trigger on VRAM questions."""
        result, reason = should_trigger_web_search("сколько vram у RTX 4070?")
        assert result is True
        assert "high_priority" in reason
    
    def test_architecture_question(self):
        """Should trigger on architecture questions."""
        result, reason = should_trigger_web_search("какая архитектура у RTX 4090?")
        assert result is True
    
    def test_comparison_vs(self):
        """Should trigger on 'vs' comparisons."""
        result, reason = should_trigger_web_search("RTX 4070 vs RX 7800 XT")
        assert result is True
    
    def test_existence_question(self):
        """Should trigger on existence questions."""
        result, reason = should_trigger_web_search("существует ли RTX 5090?")
        assert result is True


class TestNewGenModels:
    """Tests for new generation model detection (RTX 50, RX 9000)."""
    
    @pytest.mark.parametrize("query", [
        "характеристики RTX 5090",
        "цена RTX 5080",
        "обзор RTX 5070",
        "RX 9070 XT vs RTX 5070",
        "когда выйдет RX 9070",
    ])
    def test_triggers_on_new_gen_models(self, query):
        """Should trigger search for new generation models."""
        result, _ = should_trigger_web_search(query)
        assert result is True


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_string(self):
        """Should handle empty string."""
        result, reason = should_trigger_web_search("")
        assert result is False
    
    def test_none_like_behavior(self):
        """Should handle None-like input."""
        result, reason = should_trigger_web_search("")
        assert result is False
        assert reason == ""
    
    def test_case_insensitive(self):
        """Should be case insensitive."""
        result1, _ = should_trigger_web_search("RTX 4070")
        result2, _ = should_trigger_web_search("rtx 4070")
        result3, _ = should_trigger_web_search("Rtx 4070")
        
        assert result1 == result2 == result3
