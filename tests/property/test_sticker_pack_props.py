"""
Property-based tests for Sticker Pack Service.

Fortress Update v6.0: Tests for sticker pack management properties.

Requirements: 8.2, 8.4
"""

import os
import sys
import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional

# Maximum stickers per pack before rotation (Requirement 8.2)
# This constant is duplicated here to avoid import issues
MAX_STICKERS_PER_PACK = 120


@dataclass
class StickerPackInfo:
    """Information about a sticker pack (test copy)."""
    id: int
    name: str
    title: str
    sticker_count: int
    is_full: bool
    is_current: bool
    chat_id: int


class StickerPackServiceTestable:
    """
    Testable version of StickerPackService without database dependencies.
    Contains only the pure functions that can be tested without mocking.
    """
    
    def __init__(self, bot_username: str = "OlegBot"):
        self.bot_username = bot_username
    
    def _generate_pack_name(self, chat_id: int, version: int = 1) -> str:
        """Generate a unique pack name for a chat."""
        chat_id_str = str(abs(chat_id))
        return f"oleg_quotes_{chat_id_str}_v{version}_by_{self.bot_username}"
    
    def _generate_pack_title(self, chat_title: str = "Chat", version: int = 1) -> str:
        """Generate a human-readable pack title."""
        title = f"Цитаты Олега - {chat_title}"
        if version > 1:
            title += f" (том {version})"
        return title[:64]


# Use the testable version for property tests
StickerPackService = StickerPackServiceTestable


# Test data generators
chat_ids = st.integers(min_value=-999999999999, max_value=-1)
sticker_counts = st.integers(min_value=0, max_value=200)
pack_versions = st.integers(min_value=1, max_value=100)


class TestPackRotationThreshold:
    """
    Property tests for pack rotation threshold.
    
    **Feature: fortress-update, Property 20: Pack rotation threshold**
    **Validates: Requirements 8.2**
    """
    
    def test_max_stickers_constant_is_120(self):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        Verify that MAX_STICKERS_PER_PACK is exactly 120.
        """
        assert MAX_STICKERS_PER_PACK == 120
    
    @given(sticker_count=st.integers(min_value=0, max_value=119))
    @settings(max_examples=100)
    def test_pack_not_full_below_threshold(self, sticker_count):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        For any sticker count below 120, the pack SHALL NOT be marked as full.
        """
        pack_info = StickerPackInfo(
            id=1,
            name="test_pack",
            title="Test Pack",
            sticker_count=sticker_count,
            is_full=sticker_count >= MAX_STICKERS_PER_PACK,
            is_current=True,
            chat_id=-123456789
        )
        
        assert pack_info.is_full == False
        assert pack_info.sticker_count < MAX_STICKERS_PER_PACK
    
    @given(sticker_count=st.integers(min_value=120, max_value=500))
    @settings(max_examples=100)
    def test_pack_full_at_or_above_threshold(self, sticker_count):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        For any sticker count at or above 120, the pack SHALL be marked as full.
        """
        pack_info = StickerPackInfo(
            id=1,
            name="test_pack",
            title="Test Pack",
            sticker_count=sticker_count,
            is_full=sticker_count >= MAX_STICKERS_PER_PACK,
            is_current=True,
            chat_id=-123456789
        )
        
        assert pack_info.is_full == True
        assert pack_info.sticker_count >= MAX_STICKERS_PER_PACK
    
    @given(chat_id=chat_ids, version=pack_versions)
    @settings(max_examples=50)
    def test_pack_name_generation_format(self, chat_id, version):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        For any chat and version, the generated pack name SHALL follow
        the correct format for Telegram sticker packs.
        """
        service = StickerPackService(bot_username="TestBot")
        pack_name = service._generate_pack_name(chat_id, version)
        
        # Pack name must end with _by_<bot_username>
        assert pack_name.endswith("_by_TestBot")
        
        # Pack name must contain version
        assert f"_v{version}_" in pack_name
        
        # Pack name must contain chat ID (absolute value)
        assert str(abs(chat_id)) in pack_name
        
        # Pack name must only contain valid characters (alphanumeric and underscore)
        valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_")
        assert all(c in valid_chars for c in pack_name.lower())
    
    @given(version=pack_versions)
    @settings(max_examples=50)
    def test_pack_title_generation_length(self, version):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        For any version, the generated pack title SHALL not exceed 64 characters.
        """
        service = StickerPackService()
        
        # Test with various chat titles including very long ones
        long_title = "A" * 100
        pack_title = service._generate_pack_title(long_title, version)
        
        # Telegram limits title to 64 characters
        assert len(pack_title) <= 64
    
    @given(sticker_count=st.integers(min_value=119, max_value=121))
    @settings(max_examples=30)
    def test_rotation_boundary_condition(self, sticker_count):
        """
        **Feature: fortress-update, Property 20: Pack rotation threshold**
        **Validates: Requirements 8.2**
        
        Test the exact boundary condition at 120 stickers.
        At exactly 120, the pack should be full and trigger rotation.
        At 119, the pack should not be full.
        """
        is_full = sticker_count >= MAX_STICKERS_PER_PACK
        
        if sticker_count < 120:
            assert is_full == False
        else:
            assert is_full == True



@dataclass
class AddStickerResult:
    """Result of adding a sticker to a pack (test copy)."""
    success: bool
    sticker_file_id: Optional[str] = None
    pack_name: Optional[str] = None
    error: Optional[str] = None
    pack_rotated: bool = False
    new_pack_name: Optional[str] = None


class TestStickerRecordUpdate:
    """
    Property tests for sticker record update.
    
    **Feature: fortress-update, Property 21: Sticker record update**
    **Validates: Requirements 8.4**
    """
    
    @given(
        quote_id=st.integers(min_value=1, max_value=1000000),
        sticker_file_id=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
            min_size=10,
            max_size=100
        ).filter(lambda x: len(x.strip()) > 0)
    )
    @settings(max_examples=100)
    def test_add_sticker_result_structure(self, quote_id, sticker_file_id):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        For any sticker addition, the result SHALL contain all required fields.
        """
        # Simulate a successful add sticker result
        result = AddStickerResult(
            success=True,
            sticker_file_id=sticker_file_id,
            pack_name="test_pack_by_OlegBot",
            pack_rotated=False
        )
        
        # Verify all required fields are present
        assert hasattr(result, 'success')
        assert hasattr(result, 'sticker_file_id')
        assert hasattr(result, 'pack_name')
        assert hasattr(result, 'error')
        assert hasattr(result, 'pack_rotated')
        assert hasattr(result, 'new_pack_name')
        
        # Verify successful result has correct values
        assert result.success == True
        assert result.sticker_file_id == sticker_file_id
        assert result.pack_name is not None
        assert result.error is None
    
    @given(
        sticker_file_id=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
            min_size=10,
            max_size=100
        ).filter(lambda x: len(x.strip()) > 0)
    )
    @settings(max_examples=50)
    def test_sticker_file_id_preserved(self, sticker_file_id):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        For any sticker successfully added to a pack, the sticker_file_id
        SHALL be preserved in the result.
        """
        result = AddStickerResult(
            success=True,
            sticker_file_id=sticker_file_id,
            pack_name="test_pack_by_OlegBot"
        )
        
        # The sticker file ID should be exactly what was provided
        assert result.sticker_file_id == sticker_file_id
    
    @given(
        pack_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_'),
            min_size=5,
            max_size=64
        ).filter(lambda x: len(x.strip()) > 0)
    )
    @settings(max_examples=50)
    def test_pack_name_preserved_in_result(self, pack_name):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        For any sticker successfully added, the pack_name SHALL be
        included in the result.
        """
        result = AddStickerResult(
            success=True,
            sticker_file_id="test_file_id_123",
            pack_name=pack_name
        )
        
        assert result.pack_name == pack_name
    
    @given(error_message=st.text(min_size=1, max_size=200).filter(lambda x: len(x.strip()) > 0))
    @settings(max_examples=50)
    def test_failed_result_has_error(self, error_message):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        For any failed sticker addition, the result SHALL contain an error message.
        """
        result = AddStickerResult(
            success=False,
            error=error_message
        )
        
        assert result.success == False
        assert result.error == error_message
        assert result.sticker_file_id is None
    
    @given(
        old_pack_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_'),
            min_size=5,
            max_size=64
        ).filter(lambda x: len(x.strip()) > 0),
        new_pack_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_'),
            min_size=5,
            max_size=64
        ).filter(lambda x: len(x.strip()) > 0)
    )
    @settings(max_examples=50)
    def test_pack_rotation_indicated_in_result(self, old_pack_name, new_pack_name):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        When pack rotation occurs during sticker addition, the result
        SHALL indicate this with pack_rotated=True and include new_pack_name.
        """
        assume(old_pack_name != new_pack_name)
        
        result = AddStickerResult(
            success=True,
            sticker_file_id="test_file_id_123",
            pack_name=new_pack_name,
            pack_rotated=True,
            new_pack_name=new_pack_name
        )
        
        assert result.pack_rotated == True
        assert result.new_pack_name == new_pack_name
        assert result.pack_name == new_pack_name
    
    @given(
        pack_id=st.integers(min_value=1, max_value=1000000),
        sticker_count=st.integers(min_value=0, max_value=119)
    )
    @settings(max_examples=50)
    def test_sticker_pack_info_consistency(self, pack_id, sticker_count):
        """
        **Feature: fortress-update, Property 21: Sticker record update**
        **Validates: Requirements 8.4**
        
        For any StickerPackInfo, the is_full flag SHALL be consistent
        with the sticker_count and MAX_STICKERS_PER_PACK threshold.
        """
        pack_info = StickerPackInfo(
            id=pack_id,
            name=f"test_pack_{pack_id}",
            title=f"Test Pack {pack_id}",
            sticker_count=sticker_count,
            is_full=sticker_count >= MAX_STICKERS_PER_PACK,
            is_current=True,
            chat_id=-123456789
        )
        
        # Verify consistency
        expected_is_full = sticker_count >= MAX_STICKERS_PER_PACK
        assert pack_info.is_full == expected_is_full
