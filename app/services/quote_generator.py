"""
Quote Generator Service for OLEG v6.0 Fortress Update.

Provides enhanced quote rendering with gradient backgrounds, themes,
quote chains, and roast mode with LLM comments.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class QuoteTheme(Enum):
    """Quote theme options."""
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"


@dataclass
class QuoteStyle:
    """Style configuration for quote rendering."""
    theme: QuoteTheme = QuoteTheme.DARK
    gradient: Optional[Tuple[str, str]] = None
    font_family: str = "DejaVuSans"
    avatar_style: str = "circle"


@dataclass
class QuoteImage:
    """Result of quote rendering."""
    image_data: bytes
    format: str  # webp
    width: int
    height: int


@dataclass
class MessageData:
    """Data for a single message in a quote chain."""
    text: str
    username: str
    avatar_url: Optional[str] = None
    timestamp: Optional[str] = None


# Gradient presets for different themes
GRADIENT_PRESETS = {
    "dark": [
        ("#1a1a2e", "#16213e"),  # Deep blue
        ("#0f0f23", "#1a1a3e"),  # Dark purple
        ("#1e1e1e", "#2d2d2d"),  # Charcoal
        ("#0d1117", "#161b22"),  # GitHub dark
        ("#1a1b26", "#24283b"),  # Tokyo night
    ],
    "light": [
        ("#f5f5f5", "#e0e0e0"),  # Light gray
        ("#fff5e6", "#ffe4c4"),  # Warm cream
        ("#e8f4f8", "#d4e9ed"),  # Light blue
        ("#f0fff0", "#e0ffe0"),  # Mint
        ("#fff0f5", "#ffe4e9"),  # Light pink
    ],
}

# Maximum dimensions for Telegram stickers
MAX_STICKER_SIZE = 512
MAX_CHAIN_MESSAGES = 10


class QuoteGeneratorService:
    """
    Service for generating quote images.
    
    Supports:
    - Single message quotes with gradient backgrounds
    - Quote chains (up to 10 messages)
    - Roast mode with LLM-generated comments
    - WebP output optimized for Telegram stickers
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def __init__(self):
        """Initialize the quote generator service."""
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for rendering with Unicode/Cyrillic support."""
        # Font search paths - prioritize project fonts, then system fonts
        font_search_paths = [
            # Project fonts directory
            "fonts/",
            # Linux common paths
            "/usr/share/fonts/truetype/dejavu/",
            "/usr/share/fonts/TTF/",
            # macOS paths
            "/Library/Fonts/",
            "/System/Library/Fonts/",
            # Windows paths
            "C:/Windows/Fonts/",
        ]
        
        # Font candidates with Unicode/Cyrillic support
        font_candidates = [
            ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"),
            ("Arial Unicode.ttf", "Arial Unicode.ttf", "Arial Unicode.ttf"),
            ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf"),
            ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoSans-Italic.ttf"),
            ("FreeSans.ttf", "FreeSansBold.ttf", "FreeSansOblique.ttf"),
        ]
        
        def find_font(font_name: str) -> Optional[str]:
            """Try to find font in search paths."""
            import os
            # Try direct path first
            if os.path.exists(font_name):
                return font_name
            # Search in paths
            for path in font_search_paths:
                full_path = os.path.join(path, font_name)
                if os.path.exists(full_path):
                    return full_path
            return None
        
        fonts_loaded = False
        for regular, bold, italic in font_candidates:
            regular_path = find_font(regular)
            bold_path = find_font(bold)
            italic_path = find_font(italic)
            
            if regular_path:
                try:
                    self.text_font = ImageFont.truetype(regular_path, 18)
                    self.username_font = ImageFont.truetype(bold_path or regular_path, 14)
                    self.comment_font = ImageFont.truetype(italic_path or regular_path, 16)
                    self.timestamp_font = ImageFont.truetype(regular_path, 10)
                    logger.info(f"Loaded fonts from: {regular_path}")
                    fonts_loaded = True
                    break
                except OSError as e:
                    logger.debug(f"Failed to load font {regular}: {e}")
                    continue
        
        if not fonts_loaded:
            logger.warning("No Unicode fonts found, using default (may not support Cyrillic)")
            self.text_font = ImageFont.load_default()
            self.username_font = ImageFont.load_default()
            self.comment_font = ImageFont.load_default()
            self.timestamp_font = ImageFont.load_default()

    def _get_gradient_colors(self, style: QuoteStyle) -> Tuple[str, str]:
        """Get gradient colors based on style."""
        if style.gradient:
            return style.gradient
        
        import random
        theme_key = "dark" if style.theme in (QuoteTheme.DARK, QuoteTheme.AUTO) else "light"
        return random.choice(GRADIENT_PRESETS[theme_key])
    
    def _create_gradient_background(
        self, 
        width: int, 
        height: int, 
        color1: str, 
        color2: str
    ) -> Image.Image:
        """Create a gradient background image."""
        # Parse hex colors
        r1, g1, b1 = self._hex_to_rgb(color1)
        r2, g2, b2 = self._hex_to_rgb(color2)
        
        # Create gradient
        img = Image.new('RGB', (width, height))
        pixels = img.load()
        
        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            for x in range(width):
                pixels[x, y] = (r, g, b)
        
        return img
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _get_text_color(self, style: QuoteStyle) -> Tuple[int, int, int]:
        """Get text color based on theme."""
        if style.theme == QuoteTheme.LIGHT:
            return (33, 33, 33)  # Dark gray for light theme
        return (255, 255, 255)  # White for dark theme
    
    def _get_secondary_color(self, style: QuoteStyle) -> Tuple[int, int, int]:
        """Get secondary text color based on theme."""
        if style.theme == QuoteTheme.LIGHT:
            return (100, 100, 100)  # Gray for light theme
        return (180, 180, 180)  # Light gray for dark theme
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                bbox = font.getbbox(test_line)
                width = bbox[2] - bbox[0]
            except AttributeError:
                # Fallback for older PIL versions
                width = font.getlength(test_line) if hasattr(font, 'getlength') else len(test_line) * 8
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else ['']
    
    def _calculate_text_height(self, lines: List[str], font: ImageFont.FreeTypeFont, line_spacing: int = 4) -> int:
        """Calculate total height needed for wrapped text."""
        if not lines:
            return 0
        
        try:
            bbox = font.getbbox("Ay")
            line_height = bbox[3] - bbox[1]
        except AttributeError:
            line_height = 20  # Fallback
        
        return len(lines) * line_height + (len(lines) - 1) * line_spacing
    
    def _draw_avatar(self, draw: ImageDraw.Draw, x: int, y: int, size: int, username: str, style: QuoteStyle):
        """Draw a placeholder avatar circle with initial."""
        # Generate color from username hash
        import hashlib
        hash_val = int(hashlib.md5(username.encode()).hexdigest()[:6], 16)
        hue = hash_val % 360
        
        # Convert HSL to RGB (simplified)
        r = int(128 + 64 * ((hash_val >> 16) % 2))
        g = int(128 + 64 * ((hash_val >> 8) % 2))
        b = int(128 + 64 * (hash_val % 2))
        
        # Draw circle
        draw.ellipse([x, y, x + size, y + size], fill=(r, g, b))
        
        # Draw initial
        initial = username[0].upper() if username else "?"
        text_color = (255, 255, 255)
        
        # Use already loaded font instead of hardcoded path
        initial_font = self.username_font
        
        try:
            bbox = initial_font.getbbox(initial)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width = size // 3
            text_height = size // 3
        
        text_x = x + (size - text_width) // 2
        text_y = y + (size - text_height) // 2 - 2
        draw.text((text_x, text_y), initial, font=initial_font, fill=text_color)

    async def render_quote(
        self,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        style: Optional[QuoteStyle] = None,
        timestamp: Optional[str] = None
    ) -> QuoteImage:
        """
        Render a single message quote with gradient background.
        
        Requirements: 7.1, 7.2, 7.5
        
        Args:
            text: The quote text
            username: Username of the message author
            avatar_url: Optional URL to user's avatar
            style: Quote style configuration
            timestamp: Optional timestamp string
        
        Returns:
            QuoteImage with rendered image data
        """
        if style is None:
            style = QuoteStyle()
        
        # Configuration
        padding = 20
        avatar_size = 40
        max_text_width = MAX_STICKER_SIZE - padding * 2 - avatar_size - 15
        
        # Wrap text
        lines = self._wrap_text(text, self.text_font, max_text_width)
        text_height = self._calculate_text_height(lines, self.text_font)
        
        # Calculate image dimensions
        content_height = max(avatar_size, text_height + 25)  # 25 for username
        height = min(MAX_STICKER_SIZE, padding * 2 + content_height + (20 if timestamp else 0))
        width = MAX_STICKER_SIZE
        
        # Create gradient background
        color1, color2 = self._get_gradient_colors(style)
        img = self._create_gradient_background(width, height, color1, color2)
        draw = ImageDraw.Draw(img)
        
        # Draw rounded rectangle border
        border_color = (88, 101, 242) if style.theme != QuoteTheme.LIGHT else (66, 133, 244)
        self._draw_rounded_rect(draw, padding - 5, padding - 5, width - padding + 5, height - padding + 5, 10, border_color)
        
        # Draw avatar
        avatar_x = padding
        avatar_y = padding
        self._draw_avatar(draw, avatar_x, avatar_y, avatar_size, username, style)
        
        # Draw username
        text_color = self._get_text_color(style)
        secondary_color = self._get_secondary_color(style)
        username_display = f"@{username}" if username and not username.startswith("@") else username or "Anonymous"
        draw.text(
            (avatar_x + avatar_size + 10, avatar_y),
            username_display,
            font=self.username_font,
            fill=text_color
        )
        
        # Draw message text
        text_y = avatar_y + 22
        try:
            bbox = self.text_font.getbbox("Ay")
            line_height = bbox[3] - bbox[1] + 4
        except AttributeError:
            line_height = 22
        
        for line in lines:
            draw.text(
                (avatar_x + avatar_size + 10, text_y),
                line,
                font=self.text_font,
                fill=text_color
            )
            text_y += line_height
        
        # Draw timestamp if provided
        if timestamp:
            draw.text(
                (width - padding - 60, height - padding - 10),
                timestamp,
                font=self.timestamp_font,
                fill=secondary_color
            )
        
        # Convert to WebP
        output = BytesIO()
        img.save(output, format='WEBP', quality=90)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=width,
            height=height
        )
    
    def _draw_rounded_rect(
        self, 
        draw: ImageDraw.Draw, 
        x1: int, 
        y1: int, 
        x2: int, 
        y2: int, 
        radius: int, 
        color: Tuple[int, int, int]
    ):
        """Draw a rounded rectangle outline."""
        # Draw lines
        draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=color, width=2)
        draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=color, width=2)
        draw.line([(x1, y1 + radius), (x1, y2 - radius)], fill=color, width=2)
        draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=color, width=2)
        
        # Draw corners
        draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=color, width=2)
        draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=color, width=2)
        draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=color, width=2)
        draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=color, width=2)

    async def render_quote_chain(
        self,
        messages: List[MessageData],
        style: Optional[QuoteStyle] = None
    ) -> QuoteImage:
        """
        Render a chain of messages as a single quote image.
        
        Requirements: 7.3, 7.5
        Property 17: Quote chain limit - max 10 messages
        
        Args:
            messages: List of MessageData objects (max 10)
            style: Quote style configuration
        
        Returns:
            QuoteImage with rendered image data
        """
        if style is None:
            style = QuoteStyle()
        
        # Enforce maximum chain limit (Property 17)
        if len(messages) > MAX_CHAIN_MESSAGES:
            messages = messages[:MAX_CHAIN_MESSAGES]
        
        if not messages:
            # Return empty quote if no messages
            return await self.render_quote("(empty)", "System", style=style)
        
        # Configuration
        padding = 15
        avatar_size = 32
        message_spacing = 10
        max_text_width = MAX_STICKER_SIZE - padding * 2 - avatar_size - 15
        
        # Calculate total height needed
        total_height = padding * 2
        message_heights = []
        
        for msg in messages:
            lines = self._wrap_text(msg.text, self.text_font, max_text_width)
            text_height = self._calculate_text_height(lines, self.text_font)
            msg_height = max(avatar_size, text_height + 20)  # 20 for username
            message_heights.append((msg_height, lines))
            total_height += msg_height + message_spacing
        
        total_height -= message_spacing  # Remove last spacing
        
        # Ensure we don't exceed max size (Property 18)
        height = min(MAX_STICKER_SIZE, total_height)
        width = MAX_STICKER_SIZE
        
        # Create gradient background
        color1, color2 = self._get_gradient_colors(style)
        img = self._create_gradient_background(width, height, color1, color2)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border_color = (88, 101, 242) if style.theme != QuoteTheme.LIGHT else (66, 133, 244)
        self._draw_rounded_rect(draw, padding - 5, padding - 5, width - padding + 5, height - padding + 5, 10, border_color)
        
        # Draw each message
        text_color = self._get_text_color(style)
        current_y = padding
        
        try:
            bbox = self.text_font.getbbox("Ay")
            line_height = bbox[3] - bbox[1] + 4
        except AttributeError:
            line_height = 22
        
        for i, msg in enumerate(messages):
            if current_y >= height - padding:
                break  # Stop if we've run out of space
            
            msg_height, lines = message_heights[i]
            
            # Draw avatar
            self._draw_avatar(draw, padding, current_y, avatar_size, msg.username, style)
            
            # Draw username
            username_display = f"@{msg.username}" if msg.username and not msg.username.startswith("@") else msg.username or "Anonymous"
            draw.text(
                (padding + avatar_size + 8, current_y),
                username_display,
                font=self.username_font,
                fill=text_color
            )
            
            # Draw message text
            text_y = current_y + 18
            for line in lines:
                if text_y >= height - padding:
                    break
                draw.text(
                    (padding + avatar_size + 8, text_y),
                    line,
                    font=self.text_font,
                    fill=text_color
                )
                text_y += line_height
            
            current_y += msg_height + message_spacing
        
        # Convert to WebP
        output = BytesIO()
        img.save(output, format='WEBP', quality=90)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=width,
            height=height
        )

    async def render_roast_quote(
        self,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        style: Optional[QuoteStyle] = None
    ) -> QuoteImage:
        """
        Render a quote with an LLM-generated roast comment from Oleg.
        
        Requirements: 7.4, 7.5
        
        Args:
            text: The quote text
            username: Username of the message author
            avatar_url: Optional URL to user's avatar
            style: Quote style configuration
        
        Returns:
            QuoteImage with rendered image data including roast comment
        """
        if style is None:
            style = QuoteStyle()
        
        # Generate roast comment
        comment = await self.generate_roast_comment(text)
        
        # Configuration
        padding = 15
        avatar_size = 36
        max_text_width = MAX_STICKER_SIZE - padding * 2 - avatar_size - 15
        divider_height = 2
        
        # Calculate heights
        quote_lines = self._wrap_text(text, self.text_font, max_text_width)
        quote_text_height = self._calculate_text_height(quote_lines, self.text_font)
        quote_section_height = max(avatar_size, quote_text_height + 20)
        
        comment_lines = self._wrap_text(comment, self.comment_font, max_text_width)
        comment_text_height = self._calculate_text_height(comment_lines, self.comment_font)
        comment_section_height = max(avatar_size, comment_text_height + 20)
        
        total_height = padding * 2 + quote_section_height + divider_height + 10 + comment_section_height
        
        # Ensure we don't exceed max size (Property 18)
        height = min(MAX_STICKER_SIZE, total_height)
        width = MAX_STICKER_SIZE
        
        # Create gradient background
        color1, color2 = self._get_gradient_colors(style)
        img = self._create_gradient_background(width, height, color1, color2)
        draw = ImageDraw.Draw(img)
        
        # Draw main border
        border_color = (88, 101, 242) if style.theme != QuoteTheme.LIGHT else (66, 133, 244)
        self._draw_rounded_rect(draw, padding - 5, padding - 5, width - padding + 5, height - padding + 5, 10, border_color)
        
        text_color = self._get_text_color(style)
        
        # Draw original quote section
        current_y = padding
        
        # Draw avatar
        self._draw_avatar(draw, padding, current_y, avatar_size, username, style)
        
        # Draw username
        username_display = f"@{username}" if username and not username.startswith("@") else username or "Anonymous"
        draw.text(
            (padding + avatar_size + 8, current_y),
            username_display,
            font=self.username_font,
            fill=text_color
        )
        
        # Draw quote text
        try:
            bbox = self.text_font.getbbox("Ay")
            line_height = bbox[3] - bbox[1] + 4
        except AttributeError:
            line_height = 22
        
        text_y = current_y + 18
        for line in quote_lines:
            draw.text(
                (padding + avatar_size + 8, text_y),
                line,
                font=self.text_font,
                fill=text_color
            )
            text_y += line_height
        
        # Draw divider
        divider_y = padding + quote_section_height + 5
        draw.line(
            [(padding + 10, divider_y), (width - padding - 10, divider_y)],
            fill=(240, 71, 71),  # Red divider for roast
            width=divider_height
        )
        
        # Draw Oleg's comment section
        comment_y = divider_y + 10
        
        # Draw Oleg's avatar (special)
        self._draw_oleg_avatar(draw, padding, comment_y, avatar_size)
        
        # Draw "Олег:" label
        draw.text(
            (padding + avatar_size + 8, comment_y),
            "Олег:",
            font=self.username_font,
            fill=(255, 215, 0)  # Gold color for Oleg
        )
        
        # Draw comment text
        try:
            bbox = self.comment_font.getbbox("Ay")
            comment_line_height = bbox[3] - bbox[1] + 4
        except AttributeError:
            comment_line_height = 20
        
        comment_text_y = comment_y + 18
        for line in comment_lines:
            if comment_text_y >= height - padding:
                break
            draw.text(
                (padding + avatar_size + 8, comment_text_y),
                line,
                font=self.comment_font,
                fill=(255, 215, 0)  # Gold color for Oleg's comment
            )
            comment_text_y += comment_line_height
        
        # Convert to WebP
        output = BytesIO()
        img.save(output, format='WEBP', quality=90)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=width,
            height=height
        )
    
    def _draw_oleg_avatar(self, draw: ImageDraw.Draw, x: int, y: int, size: int):
        """Draw Oleg's special avatar."""
        # Red/orange gradient-like circle for Oleg
        draw.ellipse([x, y, x + size, y + size], fill=(220, 53, 69))
        
        # Use already loaded font instead of hardcoded path
        initial_font = self.username_font
        
        try:
            bbox = initial_font.getbbox("O")
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width = size // 3
            text_height = size // 3
        
        text_x = x + (size - text_width) // 2
        text_y = y + (size - text_height) // 2 - 2
        draw.text((text_x, text_y), "O", font=initial_font, fill=(255, 255, 255))

    async def generate_roast_comment(self, text: str) -> str:
        """
        Generate a roast comment from Oleg using LLM.
        
        Requirements: 7.4
        
        Args:
            text: The original quote text to roast
        
        Returns:
            A witty roast comment from Oleg
        """
        try:
            from app.services.ollama_client import _ollama_chat
            
            roast_prompt = (
                f"Ты - Олег, грубоватый, прямолинейный, матерящийся, "
                f"но полезный бот. Дай короткий, едкий комментарий "
                f"к следующему сообщению: '{text}'. "
                f"Твой комментарий должен быть ёмким, с юмором или сарказмом, "
                f"но без оскорблений по признакам. Максимум 1-2 предложения."
            )
            
            system_prompt = (
                "Ты - Олег, грубоватый, прямолинейный, матерящийся, "
                "но полезный бот. Говори коротко, по делу, с иронией и сленгом. "
                "Можешь ругнуться, но без оскорблений по запрещённым признакам. "
                "Контекст — чаты про технику, разгон, Steam Deck, железо. "
                "Помогай чётко, без воды."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": roast_prompt}
            ]
            
            comment = await _ollama_chat(messages, temperature=0.8)
            
            # Truncate if too long
            if len(comment) > 150:
                comment = comment[:147] + "..."
            
            return comment
            
        except Exception as e:
            logger.warning(f"Failed to generate roast comment: {e}")
            # Fallback comments
            import random
            fallbacks = [
                "Ну такое себе, честно говоря.",
                "Это что вообще было?",
                "Классика жанра, чё.",
                "Без комментариев... хотя нет, вот он.",
                "Ладно, записал в архив кринжа.",
            ]
            return random.choice(fallbacks)


    async def queue_quote_task(
        self,
        text: str,
        username: str,
        chat_id: int,
        reply_to: int,
        avatar_url: Optional[str] = None,
        timestamp: Optional[str] = None,
        theme: str = "dark",
        is_chain: bool = False,
        messages: Optional[List[MessageData]] = None,
        is_roast: bool = False,
    ) -> Optional[str]:
        """
        Queue quote rendering task for async processing via Arq worker.
        
        **Validates: Requirements 14.2**
        
        Args:
            text: Quote text
            username: Username of author
            chat_id: Target chat ID
            reply_to: Message ID to reply to
            avatar_url: Optional avatar URL
            timestamp: Optional timestamp
            theme: Quote theme (dark/light/auto)
            is_chain: Whether chain quote
            messages: Messages for chain quote
            is_roast: Whether roast mode
            
        Returns:
            Task ID if queued successfully, None otherwise
        """
        try:
            from app.worker import enqueue_quote_render_task
            from app.config import settings
            
            # Check if worker is enabled
            if not settings.worker_enabled or not settings.redis_enabled:
                logger.debug(f"Worker not enabled, quote task not queued for chat {chat_id}")
                return None
            
            # Convert MessageData to dicts for serialization
            messages_dicts = None
            if messages:
                messages_dicts = [
                    {
                        "text": msg.text,
                        "username": msg.username,
                        "avatar_url": msg.avatar_url,
                        "timestamp": msg.timestamp,
                    }
                    for msg in messages
                ]
            
            job = await enqueue_quote_render_task(
                text=text,
                username=username,
                chat_id=chat_id,
                reply_to=reply_to,
                avatar_url=avatar_url,
                timestamp=timestamp,
                theme=theme,
                is_chain=is_chain,
                messages=messages_dicts,
                is_roast=is_roast,
            )
            
            if job is not None:
                logger.info(f"Quote render task queued for chat {chat_id}: {job.job_id}")
                return job.job_id
            
            return None
            
        except ImportError:
            logger.warning("Arq worker module not available")
            return None
        except Exception as e:
            logger.error(f"Failed to queue quote render task: {e}")
            return None


# Singleton instance
quote_generator_service = QuoteGeneratorService()
