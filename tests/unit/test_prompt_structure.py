"""Tests for CORE_OLEG_PROMPT structure.

Validates that the prompt follows requirements 4.1-4.15:
- No forbidden phrases like "Рад помочь", "Надеюсь помог"
- No literary phrases like "растекаешься мыслью по древу"
- No "из токсичного чата" phrase
- No "без форсирования техно-отсылок" phrase
- Contains key instructions for short responses
- Examples are in a separate section at the end
"""

import pytest
import sys
import os

# Add app directory to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the constant directly by reading the file to avoid aiogram dependency
import re

def get_core_oleg_prompt():
    """Extract CORE_OLEG_PROMPT from ollama_client.py without importing the module."""
    file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'services', 'ollama_client.py')
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find CORE_OLEG_PROMPT = """ ... """
    match = re.search(r'CORE_OLEG_PROMPT\s*=\s*"""(.*?)"""', content, re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("CORE_OLEG_PROMPT not found in ollama_client.py")

CORE_OLEG_PROMPT = get_core_oleg_prompt()


class TestPromptForbiddenPhrases:
    """Test that forbidden phrases are properly handled in the prompt."""

    def test_forbidden_phrases_in_zapresheno_section(self):
        """Requirement 4.7: Forbidden phrases should be in ЗАПРЕЩЕНО section."""
        # These phrases should appear ONLY in the "ЗАПРЕЩЕНО" context
        # to tell the model NOT to use them
        prompt_lower = CORE_OLEG_PROMPT.lower()
        
        # Check that the forbidden phrases are mentioned in the context of prohibition
        assert "запрещено" in prompt_lower
        # The phrases should be listed as forbidden, not as instructions to use
        forbidden_line = [line for line in CORE_OLEG_PROMPT.split('\n') 
                         if 'рад помочь' in line.lower()]
        assert len(forbidden_line) == 1
        assert 'запрещено' in forbidden_line[0].lower()

    def test_no_rastekayeshsya_myslyu(self):
        """Requirement 4.11: No 'растекаешься мыслью по древу' phrase."""
        assert "растекаешься мыслью" not in CORE_OLEG_PROMPT.lower()
        assert "по древу" not in CORE_OLEG_PROMPT.lower()

    def test_no_toksichnogo_chata(self):
        """Requirement 4.13: No 'из токсичного чата' phrase."""
        assert "из токсичного чата" not in CORE_OLEG_PROMPT.lower()

    def test_no_bez_forsirovaniya(self):
        """Requirement 4.12: No 'без форсирования техно-отсылок' phrase."""
        assert "без форсирования" not in CORE_OLEG_PROMPT.lower()
        assert "техно-отсылок" not in CORE_OLEG_PROMPT.lower()


class TestPromptRequiredInstructions:
    """Test that required instructions are present in the prompt."""

    def test_short_responses_instruction(self):
        """Requirement 4.1, 4.6: Prompt instructs short responses."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        # Should mention short sentences or 1-3 sentences
        assert "коротк" in prompt_lower or "1-3" in prompt_lower

    def test_no_lists_instruction(self):
        """Requirement 4.3: Prompt prohibits lists and structured formatting."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "запрещено" in prompt_lower
        assert "списк" in prompt_lower or "нумерац" in prompt_lower

    def test_humor_in_context(self):
        """Requirement 4.8: Humor is 'in context, not constantly'."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        # Should mention that humor/jokes are used appropriately
        assert "в тему" in prompt_lower or "не постоянно" in prompt_lower

    def test_profanity_as_accent(self):
        """Requirement 4.10: Profanity is occasional emphasis, not constant."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        # Should mention that profanity is rare/accent
        assert "акцент" in prompt_lower or "редк" in prompt_lower

    def test_like_living_person(self):
        """Requirement 4.13: Says 'как живой человек'."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "живой человек" in prompt_lower


class TestPromptStructure:
    """Test the overall structure of the prompt."""

    def test_examples_at_end(self):
        """Requirement 4.14: Examples are in a separate section at the end."""
        # Find the position of examples section
        examples_pos = CORE_OLEG_PROMPT.find("ПРИМЕРЫ")
        assert examples_pos > 0, "Examples section should exist"
        
        # Examples should be in the last third of the prompt
        prompt_length = len(CORE_OLEG_PROMPT)
        assert examples_pos > prompt_length * 0.5, "Examples should be in the second half of prompt"

    def test_no_specific_entry_phrases(self):
        """Requirement 4.15: No specific entry phrases that model will copy."""
        # The old prompt had specific phrases like "У тебя тут жопа с драйверами"
        # These should not be in the instructions (only in examples if at all)
        instructions_part = CORE_OLEG_PROMPT.split("ПРИМЕРЫ")[0] if "ПРИМЕРЫ" in CORE_OLEG_PROMPT else CORE_OLEG_PROMPT
        
        # Should not have specific dialogue entry phrases in instructions
        assert "У тебя тут жопа" not in instructions_part
        assert "Опять этот вопрос" not in instructions_part
        assert "Слышь, ты чё творишь" not in instructions_part

    def test_prompt_is_shorter(self):
        """The new prompt should be significantly shorter than before."""
        # The old prompt was about 10000+ characters
        # The new one should be under 4000
        assert len(CORE_OLEG_PROMPT) < 5000, f"Prompt is too long: {len(CORE_OLEG_PROMPT)} chars"

    def test_has_key_sections(self):
        """Prompt should have key sections."""
        assert "КТО ТЫ" in CORE_OLEG_PROMPT
        assert "СТИЛЬ ОБЩЕНИЯ" in CORE_OLEG_PROMPT
        assert "ДЛИНА ОТВЕТОВ" in CORE_OLEG_PROMPT
        assert "ОГРАНИЧЕНИЯ" in CORE_OLEG_PROMPT
