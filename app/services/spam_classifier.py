"""Spam Classifier Service - Neural Spam Filter.

This module provides spam detection and classification using a combination
of regex patterns, keywords, and scoring algorithms.

**Feature: shield-economy-v65**
**Validates: Requirements 8.1, 8.2, 8.3, 8.4**
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class SpamClassification:
    """Result of spam classification.
    
    Attributes:
        is_spam: Whether the message is classified as spam
        confidence: Confidence score (0.0 - 1.0)
        matched_patterns: List of pattern names that matched
        category: Spam category (selling, crypto, job_offer, collaboration, unknown)
    """
    is_spam: bool
    confidence: float
    matched_patterns: List[str] = field(default_factory=list)
    category: str = "unknown"


# Default spam patterns by category
# Each pattern is a tuple of (pattern_name, regex_pattern, weight)
DEFAULT_SPAM_PATTERNS: Dict[str, List[tuple]] = {
    "selling": [
        # Account selling patterns (Russian)
        ("sell_account_ru", r"прода[юём]\s*(акк|аккаунт|профиль)", 0.8),
        ("buy_account_ru", r"куп(лю|им)\s*(акк|аккаунт|профиль)", 0.7),
        ("account_sale_ru", r"(акк|аккаунт)\s*(на\s*)?прода(жу|ж[ае])", 0.8),
        ("cheap_account_ru", r"дёшев[оа]\s*(акк|аккаунт)", 0.7),
        # Account selling patterns (English)
        ("sell_account_en", r"sell(ing)?\s*(my\s*)?(account|acc)", 0.8),
        ("buy_account_en", r"buy(ing)?\s*(an?\s*)?(account|acc)", 0.7),
        ("account_for_sale", r"account\s*(for\s*)?sale", 0.8),
        # General selling
        ("selling_generic", r"(прода[юём]|sell(ing)?)\s*[!.]+", 0.5),
        ("price_tag", r"(цена|price|стоимость)[:\s]*\d+\s*(руб|₽|\$|usd|usdt)", 0.6),
    ],
    "crypto": [
        # Crypto scam patterns (Russian)
        ("crypto_earn_ru", r"заработ(ок|ай|ать)\s*(на\s*)?(крипт|биткоин|btc|eth)", 0.9),
        ("crypto_invest_ru", r"инвести(ции|руй)\s*(в\s*)?(крипт|биткоин|btc)", 0.8),
        ("crypto_profit_ru", r"(доход|прибыль)\s*\d+%?\s*(в\s*)?(день|месяц|неделю)", 0.9),
        ("crypto_signal_ru", r"(сигнал[ыи]|торгов[ыа]я?\s*бот)", 0.7),
        # Crypto scam patterns (English)
        ("crypto_earn_en", r"earn\s*(money\s*)?(with\s*)?(crypto|bitcoin|btc|eth)", 0.9),
        ("crypto_invest_en", r"invest\s*(in\s*)?(crypto|bitcoin|btc)", 0.8),
        ("crypto_profit_en", r"(profit|income|return)\s*\d+%?\s*(per\s*)?(day|month|week)", 0.9),
        ("crypto_signal_en", r"(trading\s*)?signals?\s*(group|channel)", 0.7),
        # Wallet/address patterns
        ("wallet_address", r"(wallet|кошел[её]к)[:\s]*[a-zA-Z0-9]{30,}", 0.8),
        ("send_crypto", r"(отправ|send|transfer)\s*(btc|eth|usdt|крипт)", 0.7),
    ],
    "job_offer": [
        # Job scam patterns (Russian)
        ("remote_work_ru", r"(удал[её]нн?ая?\s*работа|работа\s*из\s*дома)", 0.5),
        ("easy_money_ru", r"(л[её]гк(ий|ие)\s*деньги|быстр(ый|ые)\s*заработок)", 0.8),
        ("no_exp_ru", r"(без\s*опыта|опыт\s*не\s*требуется)", 0.4),
        ("high_salary_ru", r"(зарплата|доход|оклад)\s*(от\s*)?\d{3,}\s*(тыс|k|\$|руб)", 0.6),
        ("vacancy_spam_ru", r"(вакансия|набор|требуются)\s*(срочно|сейчас)", 0.6),
        # Job scam patterns (English)
        ("remote_work_en", r"(remote\s*work|work\s*from\s*home)", 0.5),
        ("easy_money_en", r"(easy\s*money|quick\s*cash|fast\s*income)", 0.8),
        ("no_exp_en", r"(no\s*experience|experience\s*not\s*required)", 0.4),
        ("high_salary_en", r"(salary|income)\s*(from\s*)?\$?\d{3,}\s*(k|per\s*month)?", 0.6),
    ],
    "collaboration": [
        # Collaboration spam patterns (Russian)
        ("collab_ru", r"(предлага[юе]м?\s*сотрудничество|взаимопиар)", 0.6),
        ("promo_ru", r"(рекламн(ое|ая)\s*предложение|размести(м|ть)\s*рекламу)", 0.7),
        ("partnership_ru", r"(партн[её]рск(ая|ое)|партн[её]рство)", 0.5),
        ("dm_me_ru", r"(пиши(те)?\s*(в\s*)?(лс|личк|дм|pm))", 0.6),
        # Collaboration spam patterns (English)
        ("collab_en", r"(offer(ing)?\s*collaboration|mutual\s*promo)", 0.6),
        ("promo_en", r"(promo(tion)?\s*offer|advertis(e|ing)\s*with\s*us)", 0.7),
        ("partnership_en", r"(partnership\s*offer|become\s*partner)", 0.5),
        ("dm_me_en", r"(dm\s*me|message\s*me|contact\s*(me\s*)?privately)", 0.6),
    ],
}

# Keywords that increase spam probability
SPAM_KEYWORDS: Dict[str, float] = {
    # Russian keywords
    "заработок": 0.3,
    "доход": 0.2,
    "прибыль": 0.3,
    "бесплатно": 0.2,
    "гарантия": 0.2,
    "срочно": 0.2,
    "акция": 0.2,
    "скидка": 0.1,
    "успей": 0.3,
    "только сегодня": 0.4,
    "пассивный доход": 0.5,
    "финансовая свобода": 0.4,
    # English keywords
    "earn": 0.2,
    "profit": 0.3,
    "income": 0.2,
    "free": 0.1,
    "guarantee": 0.2,
    "urgent": 0.2,
    "limited": 0.2,
    "discount": 0.1,
    "hurry": 0.3,
    "today only": 0.4,
    "passive income": 0.5,
    "financial freedom": 0.4,
}

# Spam confidence threshold
SPAM_THRESHOLD = 0.6


class SpamClassifier:
    """
    Spam classifier using regex patterns, keywords, and scoring.
    
    Provides spam detection for messages with configurable patterns
    and categories: selling, crypto, job_offer, collaboration.
    """
    
    def __init__(self):
        """Initialize spam classifier with default patterns."""
        # Copy default patterns to allow modification
        self._patterns: Dict[str, List[tuple]] = {
            category: list(patterns)
            for category, patterns in DEFAULT_SPAM_PATTERNS.items()
        }
        
        # Compile regex patterns for performance
        self._compiled_patterns: Dict[str, List[tuple]] = {}
        self._compile_patterns()
        
        # Keywords for additional scoring
        self._keywords: Dict[str, float] = dict(SPAM_KEYWORDS)
        
        # Spam threshold
        self._threshold = SPAM_THRESHOLD
    
    def _compile_patterns(self) -> None:
        """Compile all regex patterns."""
        self._compiled_patterns = {}
        for category, patterns in self._patterns.items():
            compiled = []
            for pattern_name, regex, weight in patterns:
                try:
                    compiled.append((
                        pattern_name,
                        re.compile(regex, re.IGNORECASE | re.UNICODE),
                        weight
                    ))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern_name}': {e}")
            self._compiled_patterns[category] = compiled
    
    def classify(self, text: str) -> SpamClassification:
        """
        Classify a message as spam or not spam.
        
        Uses a combination of:
        - Regex pattern matching
        - Keyword detection
        - Scoring algorithm
        
        Args:
            text: Message text to classify
            
        Returns:
            SpamClassification with result and confidence
        """
        if not text or not text.strip():
            return SpamClassification(
                is_spam=False,
                confidence=0.0,
                matched_patterns=[],
                category="unknown"
            )
        
        # Normalize text for matching
        normalized_text = text.lower().strip()
        
        # Track matches by category
        category_scores: Dict[str, float] = {}
        all_matched_patterns: List[str] = []
        
        # Check regex patterns
        for category, patterns in self._compiled_patterns.items():
            category_score = 0.0
            for pattern_name, compiled_regex, weight in patterns:
                if compiled_regex.search(normalized_text):
                    category_score += weight
                    all_matched_patterns.append(f"{category}:{pattern_name}")
            
            if category_score > 0:
                category_scores[category] = category_score
        
        # Check keywords
        keyword_score = 0.0
        for keyword, weight in self._keywords.items():
            if keyword.lower() in normalized_text:
                keyword_score += weight
        
        # Calculate total confidence
        # Pattern score is primary, keyword score is secondary
        pattern_score = sum(category_scores.values())
        total_score = min(1.0, pattern_score * 0.7 + keyword_score * 0.3)
        
        # Determine primary category
        primary_category = "unknown"
        if category_scores:
            primary_category = max(category_scores, key=category_scores.get)
        
        # Determine if spam
        is_spam = total_score >= self._threshold
        
        # Log classification for debugging
        if is_spam:
            message_hash = self._hash_message(text)
            logger.info(
                f"Spam detected: hash={message_hash}, "
                f"confidence={total_score:.2f}, "
                f"category={primary_category}, "
                f"patterns={all_matched_patterns}"
            )
        
        return SpamClassification(
            is_spam=is_spam,
            confidence=total_score,
            matched_patterns=all_matched_patterns,
            category=primary_category
        )
    
    def add_pattern(self, category: str, pattern: str, name: Optional[str] = None, weight: float = 0.7) -> None:
        """
        Add a new spam pattern to a category.
        
        Args:
            category: Spam category (selling, crypto, job_offer, collaboration)
            pattern: Regex pattern to add
            name: Optional pattern name (auto-generated if not provided)
            weight: Pattern weight (0.0 - 1.0)
        """
        if category not in self._patterns:
            self._patterns[category] = []
        
        # Generate name if not provided
        if name is None:
            name = f"custom_{category}_{len(self._patterns[category])}"
        
        # Validate regex
        try:
            re.compile(pattern, re.IGNORECASE | re.UNICODE)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            raise ValueError(f"Invalid regex pattern: {e}")
        
        # Add pattern
        self._patterns[category].append((name, pattern, weight))
        
        # Recompile patterns
        self._compile_patterns()
        
        logger.info(f"Added spam pattern '{name}' to category '{category}'")
    
    def remove_pattern(self, category: str, pattern: str) -> bool:
        """
        Remove a spam pattern from a category.
        
        Args:
            category: Spam category
            pattern: Regex pattern to remove
            
        Returns:
            True if pattern was removed, False if not found
        """
        if category not in self._patterns:
            return False
        
        # Find and remove pattern
        original_len = len(self._patterns[category])
        self._patterns[category] = [
            (name, p, weight)
            for name, p, weight in self._patterns[category]
            if p != pattern
        ]
        
        if len(self._patterns[category]) < original_len:
            # Recompile patterns
            self._compile_patterns()
            logger.info(f"Removed spam pattern from category '{category}'")
            return True
        
        return False
    
    def get_patterns(self, category: Optional[str] = None) -> Dict[str, List[tuple]]:
        """
        Get current spam patterns.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            Dictionary of category -> patterns
        """
        if category:
            return {category: self._patterns.get(category, [])}
        return dict(self._patterns)
    
    def set_threshold(self, threshold: float) -> None:
        """
        Set spam detection threshold.
        
        Args:
            threshold: New threshold (0.0 - 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._threshold = threshold
        logger.info(f"Spam threshold set to {threshold}")
    
    def get_threshold(self) -> float:
        """Get current spam detection threshold."""
        return self._threshold
    
    @staticmethod
    def _hash_message(text: str) -> str:
        """
        Create a hash of message content for logging.
        
        Args:
            text: Message text
            
        Returns:
            SHA256 hash (first 16 characters)
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def get_message_hash(self, text: str) -> str:
        """
        Get hash of message content (public method for logging).
        
        Args:
            text: Message text
            
        Returns:
            SHA256 hash (first 16 characters)
        """
        return self._hash_message(text)


# Global spam classifier instance
spam_classifier = SpamClassifier()
