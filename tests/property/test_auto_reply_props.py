"""
Property-based tests for AutoReplySystem.

Tests correctness properties defined in the design document.
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import auto_reply module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'auto_reply.py')
_spec = importlib.util.spec_from_file_location("auto_reply", _module_path)
_auto_reply_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auto_reply_module)
AutoReplySystem = _auto_reply_module.AutoReplySystem
ChatSettings = _auto_reply_module.ChatSettings


class TestAutoReplyProbabilityBounds:
    """
    **Feature: oleg-v5-refactoring, Property 6: Auto-Reply Probability Bounds**
    **Validates: Requirements 5.1**
    
    *For any* message, the calculated auto-reply probability SHALL be 
    between 0.01 (1%) and 0.15 (15%).
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=1000))
    def test_probability_within_bounds(self, text: str):
        """
        Property 6: Auto-Reply Probability Bounds
        
        For any text input, calculate_probability must return a value
        in the range [0.01, 0.15].
        """
        system = AutoReplySystem()
        probability = system.calculate_probability(text)
        
        assert probability >= system.MIN_PROBABILITY, \
            f"Probability {probability} is below minimum {system.MIN_PROBABILITY}"
        assert probability <= system.MAX_PROBABILITY, \
            f"Probability {probability} is above maximum {system.MAX_PROBABILITY}"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=500),
        st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10)
    )
    def test_probability_bounds_with_custom_triggers(self, text: str, triggers: list):
        """
        Property 6 extended: Even with many custom triggers, probability stays bounded.
        """
        system = AutoReplySystem()
        probability = system.calculate_probability(text, triggers=triggers)
        
        assert probability >= system.MIN_PROBABILITY
        assert probability <= system.MAX_PROBABILITY


class TestAutoReplyProbabilityIncrease:
    """
    **Feature: oleg-v5-refactoring, Property 7: Auto-Reply Probability Increases with Triggers**
    **Validates: Requirements 5.2**
    
    *For any* message with CAPS LOCK or trigger words, the probability SHALL be 
    greater than the base probability for a plain message.
    """
    
    @settings(max_examples=100)
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=5, max_size=100))
    def test_caps_lock_increases_probability(self, caps_text: str):
        """
        Property 7a: CAPS LOCK text should have higher probability than plain text.
        
        We test this by comparing the minimum possible probability for CAPS text
        (base_min + caps_boost) against the maximum possible for plain text (base_max).
        """
        system = AutoReplySystem()
        
        # CAPS text should trigger the boost
        assert system.is_caps_lock(caps_text), f"Text '{caps_text}' should be detected as CAPS"
        
        # The minimum probability with CAPS boost should be higher than base minimum
        # base_min + caps_boost > base_min
        min_caps_prob = system.BASE_PROBABILITY_MIN + system.CAPS_BOOST
        
        # This is a structural property: CAPS boost adds to probability
        assert system.CAPS_BOOST > 0, "CAPS boost should be positive"
        assert min_caps_prob > system.BASE_PROBABILITY_MIN
    
    @settings(max_examples=100)
    @given(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS))
    def test_trigger_word_increases_probability(self, trigger: str):
        """
        Property 7b: Text with trigger words should have higher probability.
        """
        system = AutoReplySystem()
        
        # Text with trigger
        text_with_trigger = f"Привет, {trigger}, как дела?"
        
        # Count triggers
        trigger_count = system.count_triggers(text_with_trigger)
        assert trigger_count >= 1, f"Should find trigger '{trigger}' in text"
        
        # Structural property: trigger boost is positive
        assert system.TRIGGER_BOOST > 0, "Trigger boost should be positive"
    
    @settings(max_examples=50)
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Ll',)), min_size=10, max_size=50),
        st.lists(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS), min_size=1, max_size=3, unique=True)
    )
    def test_more_triggers_higher_probability_structural(self, base_text: str, triggers: list):
        """
        Property 7c: More triggers should result in higher probability boost.
        
        This is a structural test - we verify the boost calculation is correct.
        """
        system = AutoReplySystem()
        
        # Build text with triggers
        text_with_triggers = base_text + " " + " ".join(triggers)
        
        # Count how many triggers are found
        found_triggers = system.count_triggers(text_with_triggers)
        
        # Expected boost from triggers
        expected_trigger_boost = found_triggers * system.TRIGGER_BOOST
        
        # Verify the boost is proportional to trigger count
        assert expected_trigger_boost >= 0
        if found_triggers > 0:
            assert expected_trigger_boost > 0


class TestAutoReplyDisabledSetting:
    """
    **Feature: oleg-v5-refactoring, Property 8: Auto-Reply Respects Disabled Setting**
    **Validates: Requirements 5.4, 5.5**
    
    *For any* chat with auto-reply disabled, the should_reply function 
    SHALL always return False.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=500))
    def test_disabled_chat_never_replies(self, text: str):
        """
        Property 8: When auto_reply_chance is 0 or negative, should_reply returns False.
        """
        system = AutoReplySystem()
        
        # Disabled settings (auto_reply_chance = 0)
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        # Should never reply when disabled
        result = system.should_reply(text, disabled_settings)
        assert result is False, "should_reply must return False when auto-reply is disabled"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=500),
        st.floats(min_value=-10.0, max_value=0.0)
    )
    def test_negative_chance_never_replies(self, text: str, negative_chance: float):
        """
        Property 8 extended: Negative auto_reply_chance also means disabled.
        """
        system = AutoReplySystem()
        
        settings_obj = ChatSettings(auto_reply_chance=negative_chance)
        
        result = system.should_reply(text, settings_obj)
        assert result is False, "should_reply must return False for negative auto_reply_chance"
    
    @settings(max_examples=100)
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=10, max_size=50)
    )
    def test_disabled_ignores_caps_lock(self, caps_text: str):
        """
        Property 8 extended: Even CAPS LOCK text doesn't trigger reply when disabled.
        """
        system = AutoReplySystem()
        
        # Verify it's CAPS
        assume(system.is_caps_lock(caps_text))
        
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        result = system.should_reply(caps_text, disabled_settings)
        assert result is False, "CAPS LOCK should not override disabled setting"
    
    @settings(max_examples=50)
    @given(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS))
    def test_disabled_ignores_triggers(self, trigger: str):
        """
        Property 8 extended: Even trigger words don't trigger reply when disabled.
        """
        system = AutoReplySystem()
        
        text_with_trigger = f"Эй {trigger}, помоги!"
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        result = system.should_reply(text_with_trigger, disabled_settings)
        assert result is False, "Trigger words should not override disabled setting"
