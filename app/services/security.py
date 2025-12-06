"""Security service for input sanitization, rate limiting, and access control.

This module provides comprehensive security features including:
- Input sanitization (SQL injection, XSS, command injection)
- HMAC-signed callback data
- Rate limiting with Redis support
- File validation
- Error message sanitization
- Access control verification

**Feature: fortress-update**
**Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.6, 17.7, 17.9, 17.10, 17.12**
"""

import hashlib
import hmac
import html
import logging
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Security configuration
HMAC_SECRET_KEY = os.environ.get("SECURITY_HMAC_KEY", "default-secret-key-change-in-production")
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_BLOCK_SECONDS = 300  # 5 minutes
ABUSE_PATTERN_THRESHOLD = 5  # Failed attempts before blacklist


# Allowed file types for uploads
ALLOWED_FILE_TYPES: Set[str] = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/webm",
    "audio/ogg", "audio/mpeg", "audio/mp3",
    "application/pdf",
    "text/plain",
}

# Dangerous file extensions
DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
    ".vbs", ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh",
    ".ps1", ".psm1", ".psd1", ".sh", ".bash", ".zsh",
    ".php", ".asp", ".aspx", ".jsp", ".cgi", ".pl", ".py",
}


class SecurityCheckResult(Enum):
    """Result of a security check."""
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class SecurityCheck:
    """Result of a security validation."""
    passed: bool
    reason: Optional[str] = None
    should_blacklist: bool = False


@dataclass
class FileInfo:
    """Information about an uploaded file."""
    file_id: str
    file_size: int
    mime_type: Optional[str]
    file_name: Optional[str]



class SecurityService:
    """
    Comprehensive security service for the bot.
    
    Provides input sanitization, callback signing, rate limiting,
    file validation, and access control.
    """
    
    def __init__(self, hmac_key: Optional[str] = None):
        """
        Initialize security service.
        
        Args:
            hmac_key: Secret key for HMAC signing. Uses env var if not provided.
        """
        self._hmac_key = (hmac_key or HMAC_SECRET_KEY).encode('utf-8')
        
        # In-memory rate limiting (fallback when Redis unavailable)
        self._rate_limits: Dict[int, deque] = defaultdict(deque)
        self._blocked_users: Dict[int, float] = {}  # user_id -> unblock_time
        
        # Abuse pattern tracking
        self._abuse_attempts: Dict[int, List[float]] = defaultdict(list)
        
        # Blacklist (in-memory, should be persisted to DB in production)
        self._blacklist: Dict[int, Tuple[str, float]] = {}  # user_id -> (reason, expires_at)
        
        # Redis client (optional)
        self._redis_client = None
    
    def set_redis_client(self, redis_client) -> None:
        """Set Redis client for distributed rate limiting."""
        self._redis_client = redis_client
        logger.info("SecurityService configured to use Redis")
    
    # =========================================================================
    # Input Sanitization (Requirements 17.1)
    # =========================================================================
    
    def sanitize_input(self, text: str) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Removes/escapes:
        - SQL injection patterns
        - XSS (HTML/JavaScript) content
        - Command injection sequences
        
        Args:
            text: Raw user input
            
        Returns:
            Sanitized text safe for processing
        """
        if not text:
            return ""
        
        # Step 1: HTML escape to prevent XSS
        sanitized = html.escape(text)
        
        # Step 2: Remove SQL injection patterns
        sanitized = self._sanitize_sql_injection(sanitized)
        
        # Step 3: Remove command injection patterns
        sanitized = self._sanitize_command_injection(sanitized)
        
        return sanitized
    
    def _sanitize_sql_injection(self, text: str) -> str:
        """Remove common SQL injection patterns."""
        # SQL keywords that could be dangerous
        sql_patterns = [
            r"(\b)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)(\b)",
            r"--",  # SQL comment
            r";",   # Statement terminator
            r"'",   # Single quote (escape instead of remove)
            r"\\x00",  # Null byte
        ]
        
        result = text
        for pattern in sql_patterns:
            if pattern == "'":
                # Escape single quotes instead of removing
                result = result.replace("'", "''")
            elif pattern in ("--", ";"):
                result = result.replace(pattern, "")
            else:
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        return result
    
    def _sanitize_command_injection(self, text: str) -> str:
        """Remove command injection patterns."""
        # Shell metacharacters and command separators
        dangerous_chars = [
            "|",   # Pipe
            "&",   # Background/AND
            "`",   # Command substitution
            "$(",  # Command substitution
            "$()", # Command substitution
            "&&",  # AND
            "||",  # OR
            "\n",  # Newline (command separator)
            "\r",  # Carriage return
        ]
        
        result = text
        for char in dangerous_chars:
            result = result.replace(char, "")
        
        return result
    
    # =========================================================================
    # Callback Data Signing (Requirements 17.3, 17.12)
    # =========================================================================
    
    def sign_callback_data(self, data: str, user_id: int) -> str:
        """
        Sign callback data with HMAC to prevent tampering.
        
        Args:
            data: Callback data to sign
            user_id: User ID to bind the signature to
            
        Returns:
            Signed callback data in format "data:signature"
        """
        message = f"{data}:{user_id}".encode('utf-8')
        signature = hmac.new(self._hmac_key, message, hashlib.sha256).hexdigest()[:16]
        return f"{data}:{signature}"
    
    def verify_callback_signature(self, signed_data: str, user_id: int) -> bool:
        """
        Verify HMAC signature on callback data.
        
        Args:
            signed_data: Signed callback data in format "data:signature"
            user_id: User ID to verify against
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not signed_data or ":" not in signed_data:
            return False
        
        try:
            # Split into data and signature
            parts = signed_data.rsplit(":", 1)
            if len(parts) != 2:
                return False
            
            data, provided_signature = parts
            
            # Recalculate expected signature
            message = f"{data}:{user_id}".encode('utf-8')
            expected_signature = hmac.new(self._hmac_key, message, hashlib.sha256).hexdigest()[:16]
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(provided_signature, expected_signature)
        except Exception as e:
            logger.warning(f"Callback signature verification failed: {e}")
            return False
    
    def validate_callback_data(self, data: str, user_id: int) -> SecurityCheck:
        """
        Validate callback data format and signature.
        
        Args:
            data: Callback data to validate
            user_id: User ID making the request
            
        Returns:
            SecurityCheck with validation result
        """
        if not data:
            return SecurityCheck(passed=False, reason="Empty callback data")
        
        # Check for expected format
        if ":" not in data:
            return SecurityCheck(passed=False, reason="Invalid callback data format")
        
        # Verify signature
        if not self.verify_callback_signature(data, user_id):
            # Track failed attempt for abuse detection
            self._track_abuse_attempt(user_id)
            return SecurityCheck(
                passed=False,
                reason="Invalid callback signature",
                should_blacklist=self._should_blacklist_for_abuse(user_id)
            )
        
        return SecurityCheck(passed=True)
    
    def _track_abuse_attempt(self, user_id: int) -> None:
        """Track failed authentication/validation attempts."""
        now = time.time()
        # Keep only attempts from last hour
        self._abuse_attempts[user_id] = [
            t for t in self._abuse_attempts[user_id]
            if now - t < 3600
        ]
        self._abuse_attempts[user_id].append(now)
    
    def _should_blacklist_for_abuse(self, user_id: int) -> bool:
        """Check if user should be blacklisted for abuse pattern."""
        return len(self._abuse_attempts.get(user_id, [])) >= ABUSE_PATTERN_THRESHOLD


    # =========================================================================
    # Rate Limiting (Requirements 17.2, 17.7)
    # =========================================================================
    
    async def check_rate_limit(self, user_id: int) -> SecurityCheck:
        """
        Check if user has exceeded rate limit.
        
        Enforces 30 messages per minute limit.
        Users exceeding limit are blocked for 5 minutes.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            SecurityCheck with rate limit status
        """
        # Check if user is currently blocked
        if user_id in self._blocked_users:
            unblock_time = self._blocked_users[user_id]
            if time.time() < unblock_time:
                remaining = int(unblock_time - time.time())
                return SecurityCheck(
                    passed=False,
                    reason=f"Rate limited. Try again in {remaining} seconds."
                )
            else:
                # Unblock user
                del self._blocked_users[user_id]
        
        # Check if user is blacklisted
        if self.is_blacklisted(user_id):
            return SecurityCheck(
                passed=False,
                reason="User is blacklisted",
                should_blacklist=False
            )
        
        # Try Redis first
        if self._redis_client and hasattr(self._redis_client, 'is_available') and self._redis_client.is_available:
            return await self._check_rate_limit_redis(user_id)
        
        # Fallback to in-memory
        return self._check_rate_limit_memory(user_id)
    
    async def _check_rate_limit_redis(self, user_id: int) -> SecurityCheck:
        """Redis-based rate limiting."""
        key = f"security:rate_limit:{user_id}"
        
        try:
            count = await self._redis_client.get(key)
            
            if count is None:
                await self._redis_client.set(key, "1", ex=RATE_LIMIT_WINDOW_SECONDS)
                return SecurityCheck(passed=True)
            
            count = int(count)
            
            if count >= RATE_LIMIT_MESSAGES:
                # Block user
                self._blocked_users[user_id] = time.time() + RATE_LIMIT_BLOCK_SECONDS
                return SecurityCheck(
                    passed=False,
                    reason=f"Rate limit exceeded. Blocked for {RATE_LIMIT_BLOCK_SECONDS // 60} minutes."
                )
            
            await self._redis_client.incr(key)
            return SecurityCheck(passed=True)
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return self._check_rate_limit_memory(user_id)
    
    def _check_rate_limit_memory(self, user_id: int) -> SecurityCheck:
        """In-memory rate limiting (fallback)."""
        now = time.time()
        user_requests = self._rate_limits[user_id]
        
        # Remove old requests outside the window
        while user_requests and user_requests[0] < now - RATE_LIMIT_WINDOW_SECONDS:
            user_requests.popleft()
        
        # Check if user exceeded limit
        if len(user_requests) >= RATE_LIMIT_MESSAGES:
            # Block user
            self._blocked_users[user_id] = now + RATE_LIMIT_BLOCK_SECONDS
            return SecurityCheck(
                passed=False,
                reason=f"Rate limit exceeded. Blocked for {RATE_LIMIT_BLOCK_SECONDS // 60} minutes."
            )
        
        # Add current request
        user_requests.append(now)
        return SecurityCheck(passed=True)
    
    async def detect_abuse_pattern(self, user_id: int) -> bool:
        """
        Detect if user is exhibiting abuse patterns.
        
        Checks for:
        - Repeated failed auth attempts
        - Mass command spam
        - Suspicious activity patterns
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if abuse pattern detected
        """
        return self._should_blacklist_for_abuse(user_id)
    
    async def blacklist_user(
        self,
        user_id: int,
        reason: str,
        duration_hours: int = 24
    ) -> None:
        """
        Add user to security blacklist.
        
        Args:
            user_id: Telegram user ID
            reason: Reason for blacklisting
            duration_hours: How long to blacklist (default 24 hours)
        """
        expires_at = time.time() + (duration_hours * 3600)
        self._blacklist[user_id] = (reason, expires_at)
        logger.warning(f"User {user_id} blacklisted for {duration_hours}h: {reason}")
    
    def is_blacklisted(self, user_id: int) -> bool:
        """Check if user is currently blacklisted."""
        if user_id not in self._blacklist:
            return False
        
        reason, expires_at = self._blacklist[user_id]
        if time.time() >= expires_at:
            # Blacklist expired
            del self._blacklist[user_id]
            return False
        
        return True
    
    # =========================================================================
    # File Validation (Requirements 17.4)
    # =========================================================================
    
    async def validate_file(self, file_info: FileInfo) -> SecurityCheck:
        """
        Validate uploaded file for security.
        
        Checks:
        - File size (max 20MB)
        - Dangerous extensions (checked first - most severe)
        - File type (allowed MIME types)
        
        Args:
            file_info: Information about the uploaded file
            
        Returns:
            SecurityCheck with validation result
        """
        # Check file size first
        if file_info.file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            return SecurityCheck(
                passed=False,
                reason=f"File too large. Maximum size is {max_mb}MB."
            )
        
        # Check file extension BEFORE MIME type (dangerous extensions are more severe)
        if file_info.file_name:
            ext = self._get_file_extension(file_info.file_name)
            if ext.lower() in DANGEROUS_EXTENSIONS:
                return SecurityCheck(
                    passed=False,
                    reason=f"File extension '{ext}' is not allowed.",
                    should_blacklist=True  # Attempting to upload dangerous files
                )
        
        # Check MIME type
        if file_info.mime_type and file_info.mime_type not in ALLOWED_FILE_TYPES:
            return SecurityCheck(
                passed=False,
                reason=f"File type '{file_info.mime_type}' is not allowed."
            )
        
        return SecurityCheck(passed=True)
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if not filename or "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1]


    # =========================================================================
    # Error Message Sanitization (Requirements 17.9)
    # =========================================================================
    
    def sanitize_error_message(self, error: Exception) -> str:
        """
        Create a safe error message for users.
        
        Removes internal details like:
        - Stack traces
        - File paths
        - Internal variable names
        - Database details
        
        Args:
            error: The exception that occurred
            
        Returns:
            Generic, safe error message for users
        """
        # Map of error types to user-friendly messages
        error_messages = {
            "rate_limited": "Слишком много сообщений. Подожди несколько минут.",
            "permission_denied": "У тебя нет прав на это действие.",
            "service_unavailable": "Сервис временно недоступен. Попробуй позже.",
            "invalid_input": "Неверный формат команды. Используй /help для справки.",
            "internal_error": "Что-то пошло не так. Попробуй ещё раз.",
            "file_too_large": "Файл слишком большой.",
            "not_found": "Не найдено.",
        }
        
        # Log the actual error internally
        logger.error(f"Internal error: {type(error).__name__}: {error}")
        
        # Return generic message - never expose internal details
        return error_messages.get("internal_error", "Что-то пошло не так. Попробуй ещё раз.")
    
    def create_safe_error_response(self, error_type: str) -> str:
        """
        Create a safe error response by type.
        
        Args:
            error_type: Type of error (rate_limited, permission_denied, etc.)
            
        Returns:
            User-friendly error message
        """
        error_messages = {
            "rate_limited": "Слишком много сообщений. Подожди несколько минут.",
            "permission_denied": "У тебя нет прав на это действие.",
            "service_unavailable": "Сервис временно недоступен. Попробуй позже.",
            "invalid_input": "Неверный формат команды. Используй /help для справки.",
            "internal_error": "Что-то пошло не так. Попробуй ещё раз.",
            "file_too_large": "Файл слишком большой.",
            "not_found": "Не найдено.",
            "blacklisted": "Доступ заблокирован.",
        }
        
        return error_messages.get(error_type, error_messages["internal_error"])
    
    @staticmethod
    def is_safe_error_message(message: str) -> bool:
        """
        Check if an error message is safe to show to users.
        
        Detects if message contains internal details like:
        - Stack traces
        - File paths
        - Internal variable names
        
        Args:
            message: Error message to check
            
        Returns:
            True if message is safe, False if it contains internal details
        """
        # Patterns that indicate internal details
        unsafe_patterns = [
            r"Traceback",
            r"File \".*\"",
            r"line \d+",
            r"\.py",
            r"\.pyc",
            r"/home/",
            r"/usr/",
            r"/var/",
            r"C:\\",
            r"D:\\",
            r"Exception:",
            r"Error:",
            r"at 0x[0-9a-fA-F]+",
            r"__\w+__",  # Dunder attributes
            r"self\.",
            r"cls\.",
            r"<module>",
            r"<class '",
            r"NoneType",
            r"AttributeError",
            r"TypeError",
            r"ValueError",
            r"KeyError",
            r"IndexError",
            r"RuntimeError",
            r"ImportError",
            r"ModuleNotFoundError",
            r"ConnectionError",
            r"TimeoutError",
            r"OSError",
            r"IOError",
            r"PermissionError",
            r"FileNotFoundError",
            r"psycopg",
            r"sqlalchemy",
            r"asyncpg",
            r"redis\.",
            r"aiohttp",
            r"aiogram",
        ]
        
        for pattern in unsafe_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False
        
        return True
    
    # =========================================================================
    # Access Control (Requirements 17.6, 17.10)
    # =========================================================================
    
    async def verify_admin_realtime(
        self,
        user_id: int,
        chat_id: int,
        bot: Any = None
    ) -> bool:
        """
        Verify user's admin status in real-time from Telegram API.
        
        Does NOT rely on cached database values.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bot: Telegram bot instance
            
        Returns:
            True if user is admin/owner, False otherwise
        """
        if bot is None:
            logger.warning("Bot instance not provided for admin verification")
            return False
        
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in ("administrator", "creator")
        except Exception as e:
            logger.error(f"Failed to verify admin status: {e}")
            return False
    
    async def check_private_data_access(
        self,
        requester_id: int,
        target_user_id: int
    ) -> SecurityCheck:
        """
        Check if requester can access target user's private data.
        
        Users can only access their own private data.
        
        Args:
            requester_id: ID of user making the request
            target_user_id: ID of user whose data is being accessed
            
        Returns:
            SecurityCheck with access decision
        """
        if requester_id != target_user_id:
            # Log potential security incident
            logger.warning(
                f"Access denied: User {requester_id} attempted to access "
                f"private data of user {target_user_id}"
            )
            return SecurityCheck(
                passed=False,
                reason="Access denied to private data",
                should_blacklist=False  # Don't blacklist for single attempt
            )
        
        return SecurityCheck(passed=True)


# Global security service instance
security_service = SecurityService()
