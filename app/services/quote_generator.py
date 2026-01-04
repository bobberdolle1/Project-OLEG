"""
Quote Generator Service for OLEG v6.0 Fortress Update.

Telegram-style message bubbles with high quality rendering.
Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import logging
import random
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
    theme: QuoteTheme = QuoteTheme.LIGHT  # RC8: Changed default to LIGHT theme
    gradient: Optional[Tuple[str, str]] = None
    font_family: str = "DejaVuSans"
    avatar_style: str = "circle"


@dataclass
class QuoteImage:
    """Result of quote rendering."""
    image_data: bytes
    format: str
    width: int
    height: int


@dataclass
class MessageData:
    """Data for a single message in a quote chain."""
    text: str
    username: str
    avatar_url: Optional[str] = None
    timestamp: Optional[str] = None


# Telegram-style colors
TELEGRAM_COLORS = {
    "bubble_dark": (33, 33, 33),           # Dark bubble background
    "bubble_light": (239, 255, 219),       # Light green bubble (outgoing)
    "bubble_incoming": (255, 255, 255),    # White bubble (incoming)
    "background_dark": (17, 17, 17),       # Dark mode background
    "background_light": (240, 242, 245),   # RC8: Lighter, more pleasant background
    "text_dark": (255, 255, 255),          # White text
    "text_light": (0, 0, 0),               # Black text
    "username_colors": [                    # Telegram username colors
        (220, 79, 79),    # Red
        (245, 166, 35),   # Orange
        (142, 85, 233),   # Purple
        (78, 167, 46),    # Green
        (66, 133, 244),   # Blue
        (233, 30, 99),    # Pink
        (0, 188, 212),    # Cyan
        (255, 152, 0),    # Amber
    ],
    "time_dark": (170, 170, 170),          # Gray time text
    "time_light": (100, 100, 100),
    "reply_line": (88, 101, 242),          # Blue reply line
}

# Increased size for better quality
MAX_IMAGE_WIDTH = 800
MAX_IMAGE_HEIGHT = 1200
MAX_CHAIN_MESSAGES = 10


class QuoteGeneratorService:
    """
    Service for generating Telegram-style quote images.
    High quality rendering with message bubbles.
    """
    
    def __init__(self):
        """Initialize the quote generator service."""
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for rendering with Unicode/Cyrillic support."""
        font_search_paths = [
            "fonts/",
            "/usr/share/fonts/truetype/dejavu/",
            "/usr/share/fonts/TTF/",
            "/Library/Fonts/",
            "/System/Library/Fonts/",
            "C:/Windows/Fonts/",
        ]
        
        font_candidates = [
            ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"),
            ("Arial Unicode.ttf", "Arial Unicode.ttf", "Arial Unicode.ttf"),
            ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoSans-Italic.ttf"),
        ]
        
        def find_font(font_name: str) -> Optional[str]:
            import os
            if os.path.exists(font_name):
                return font_name
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
                    # Larger fonts for better quality
                    self.text_font = ImageFont.truetype(regular_path, 28)
                    self.text_font_small = ImageFont.truetype(regular_path, 22)
                    self.username_font = ImageFont.truetype(bold_path or regular_path, 26)
                    self.time_font = ImageFont.truetype(regular_path, 18)
                    self.comment_font = ImageFont.truetype(italic_path or regular_path, 24)
                    logger.info(f"Loaded fonts from: {regular_path}")
                    fonts_loaded = True
                    break
                except OSError as e:
                    logger.debug(f"Failed to load font {regular}: {e}")
                    continue
        
        if not fonts_loaded:
            logger.warning("No Unicode fonts found, using default")
            self.text_font = ImageFont.load_default()
            self.text_font_small = ImageFont.load_default()
            self.username_font = ImageFont.load_default()
            self.time_font = ImageFont.load_default()
            self.comment_font = ImageFont.load_default()

    def _get_username_color(self, username: str) -> Tuple[int, int, int]:
        """Get consistent color for username based on hash."""
        import hashlib
        hash_val = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        return TELEGRAM_COLORS["username_colors"][hash_val % len(TELEGRAM_COLORS["username_colors"])]
    
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
                width = len(test_line) * 12
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                # Handle very long words
                if font.getbbox(word)[2] - font.getbbox(word)[0] > max_width:
                    # Split long word
                    while word:
                        for i in range(len(word), 0, -1):
                            part = word[:i]
                            if font.getbbox(part)[2] - font.getbbox(part)[0] <= max_width:
                                lines.append(part)
                                word = word[i:]
                                break
                        else:
                            lines.append(word[:1])
                            word = word[1:]
                    current_line = []
                else:
                    current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else ['']
    
    def _get_text_height(self, lines: List[str], font: ImageFont.FreeTypeFont, spacing: int = 6) -> int:
        """Calculate total height for text lines."""
        if not lines:
            return 0
        try:
            bbox = font.getbbox("Ayg")
            line_height = bbox[3] - bbox[1]
        except AttributeError:
            line_height = 28
        return len(lines) * line_height + (len(lines) - 1) * spacing
    
    def _draw_rounded_rect_filled(
        self, 
        draw: ImageDraw.Draw, 
        coords: Tuple[int, int, int, int],
        radius: int, 
        fill: Tuple[int, int, int]
    ):
        """Draw a filled rounded rectangle."""
        x1, y1, x2, y2 = coords
        
        # Draw main rectangles
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        
        # Draw corners
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
    
    def _draw_bubble_tail(self, draw: ImageDraw.Draw, x: int, y: int, fill: Tuple[int, int, int], left: bool = True):
        """Draw message bubble tail."""
        if left:
            points = [(x, y), (x - 12, y + 8), (x, y + 16)]
        else:
            points = [(x, y), (x + 12, y + 8), (x, y + 16)]
        draw.polygon(points, fill=fill)

    def _draw_avatar(self, img: Image.Image, x: int, y: int, size: int, username: str, avatar_data: Optional[bytes] = None):
        """Draw avatar - real or placeholder."""
        if avatar_data:
            try:
                avatar_img = Image.open(BytesIO(avatar_data))
                avatar_img = avatar_img.convert('RGBA')
                avatar_img = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
                
                # Create circular mask
                mask = Image.new('L', (size, size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([0, 0, size, size], fill=255)
                avatar_img.putalpha(mask)
                
                img.paste(avatar_img, (x, y), avatar_img)
                return
            except Exception as e:
                logger.debug(f"Failed to load avatar: {e}")
        
        # Draw placeholder
        draw = ImageDraw.Draw(img)
        color = self._get_username_color(username)
        draw.ellipse([x, y, x + size, y + size], fill=color)
        
        # Draw initial
        initial = username[0].upper() if username else "?"
        try:
            bbox = self.username_font.getbbox(initial)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except:
            text_w, text_h = size // 3, size // 3
        
        text_x = x + (size - text_w) // 2
        text_y = y + (size - text_h) // 2 - 4
        draw.text((text_x, text_y), initial, font=self.username_font, fill=(255, 255, 255))

    async def render_quote(
        self,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        style: Optional[QuoteStyle] = None,
        timestamp: Optional[str] = None,
        avatar_data: Optional[bytes] = None,
        custom_title: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> QuoteImage:
        """
        Render a Telegram-style message bubble quote.
        """
        if style is None:
            style = QuoteStyle()
        
        is_dark = style.theme != QuoteTheme.LIGHT
        
        # Colors
        bg_color = TELEGRAM_COLORS["background_dark"] if is_dark else TELEGRAM_COLORS["background_light"]
        bubble_color = TELEGRAM_COLORS["bubble_dark"] if is_dark else TELEGRAM_COLORS["bubble_incoming"]
        text_color = TELEGRAM_COLORS["text_dark"] if is_dark else TELEGRAM_COLORS["text_light"]
        time_color = TELEGRAM_COLORS["time_dark"] if is_dark else TELEGRAM_COLORS["time_light"]
        username_color = self._get_username_color(username)
        
        # Layout constants
        padding = 30
        avatar_size = 64
        bubble_padding = 20
        bubble_radius = 18
        max_bubble_width = MAX_IMAGE_WIDTH - padding * 2 - avatar_size - 30
        max_text_width = max_bubble_width - bubble_padding * 2
        
        # Calculate text dimensions
        lines = self._wrap_text(text, self.text_font, max_text_width)
        text_height = self._get_text_height(lines, self.text_font)
        
        # Calculate bubble dimensions
        display_name = full_name or username or "Anonymous"
        try:
            name_width = self.username_font.getbbox(display_name)[2]
            name_height = self.username_font.getbbox(display_name)[3]
        except:
            name_width, name_height = len(display_name) * 14, 26
        
        # Time text
        time_text = timestamp or "12:00"
        try:
            time_width = self.time_font.getbbox(time_text)[2]
        except:
            time_width = len(time_text) * 10
        
        # Calculate actual text width
        max_line_width = 0
        for line in lines:
            try:
                line_width = self.text_font.getbbox(line)[2]
            except:
                line_width = len(line) * 14
            max_line_width = max(max_line_width, line_width)
        
        bubble_content_width = max(name_width, max_line_width, 200)
        bubble_width = min(bubble_content_width + bubble_padding * 2, max_bubble_width)
        bubble_height = name_height + 10 + text_height + 10 + 24  # name + gap + text + gap + time
        
        # Image dimensions
        img_width = min(MAX_IMAGE_WIDTH, padding * 2 + avatar_size + 20 + bubble_width + 20)
        img_height = min(MAX_IMAGE_HEIGHT, padding * 2 + max(avatar_size, bubble_height))
        
        # Create image
        img = Image.new('RGB', (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw avatar
        avatar_x = padding
        avatar_y = padding
        self._draw_avatar(img, avatar_x, avatar_y, avatar_size, username, avatar_data)
        
        # Draw bubble
        bubble_x = avatar_x + avatar_size + 16
        bubble_y = padding
        
        self._draw_rounded_rect_filled(
            draw,
            (bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height),
            bubble_radius,
            bubble_color
        )
        
        # Draw bubble tail
        self._draw_bubble_tail(draw, bubble_x, bubble_y + 20, bubble_color, left=True)
        
        # Draw username
        name_x = bubble_x + bubble_padding
        name_y = bubble_y + bubble_padding - 5
        draw.text((name_x, name_y), display_name, font=self.username_font, fill=username_color)
        
        # Draw custom title if exists
        if custom_title:
            title_x = name_x + name_width + 10
            draw.text((title_x, name_y + 4), f"• {custom_title}", font=self.time_font, fill=time_color)
        
        # Draw text
        text_x = bubble_x + bubble_padding
        text_y = name_y + name_height + 8
        
        try:
            line_height = self.text_font.getbbox("Ayg")[3] + 6
        except:
            line_height = 34
        
        for line in lines:
            draw.text((text_x, text_y), line, font=self.text_font, fill=text_color)
            text_y += line_height
        
        # Draw time
        time_x = bubble_x + bubble_width - bubble_padding - time_width
        time_y = bubble_y + bubble_height - 28
        draw.text((time_x, time_y), time_text, font=self.time_font, fill=time_color)
        
        # Save as high quality WebP
        output = BytesIO()
        img.save(output, format='WEBP', quality=95, method=6)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=img_width,
            height=img_height
        )

    async def render_quote_chain(
        self,
        messages: List[MessageData],
        style: Optional[QuoteStyle] = None
    ) -> QuoteImage:
        """
        Render a chain of Telegram-style message bubbles.
        """
        if style is None:
            style = QuoteStyle()
        
        if len(messages) > MAX_CHAIN_MESSAGES:
            messages = messages[:MAX_CHAIN_MESSAGES]
        
        if not messages:
            return await self.render_quote("(empty)", "System", style=style)
        
        is_dark = style.theme != QuoteTheme.LIGHT
        
        # Colors
        bg_color = TELEGRAM_COLORS["background_dark"] if is_dark else TELEGRAM_COLORS["background_light"]
        bubble_color = TELEGRAM_COLORS["bubble_dark"] if is_dark else TELEGRAM_COLORS["bubble_incoming"]
        text_color = TELEGRAM_COLORS["text_dark"] if is_dark else TELEGRAM_COLORS["text_light"]
        time_color = TELEGRAM_COLORS["time_dark"] if is_dark else TELEGRAM_COLORS["time_light"]
        
        # Layout
        padding = 25
        avatar_size = 48
        bubble_padding = 16
        bubble_radius = 14
        message_gap = 12
        max_bubble_width = MAX_IMAGE_WIDTH - padding * 2 - avatar_size - 30
        max_text_width = max_bubble_width - bubble_padding * 2
        
        # Calculate dimensions for each message
        message_data = []
        total_height = padding * 2
        
        for msg in messages:
            lines = self._wrap_text(msg.text, self.text_font_small, max_text_width)
            text_height = self._get_text_height(lines, self.text_font_small, spacing=4)
            
            try:
                name_height = self.username_font.getbbox(msg.username)[3]
            except:
                name_height = 24
            
            bubble_height = name_height + 6 + text_height + 6 + 20
            message_data.append({
                'msg': msg,
                'lines': lines,
                'bubble_height': bubble_height,
                'text_height': text_height,
                'name_height': name_height,
            })
            total_height += bubble_height + message_gap
        
        total_height -= message_gap
        
        # Image dimensions
        img_width = MAX_IMAGE_WIDTH
        img_height = min(MAX_IMAGE_HEIGHT, total_height)
        
        # Create image
        img = Image.new('RGB', (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        current_y = padding
        
        for data in message_data:
            if current_y >= img_height - padding:
                break
            
            msg = data['msg']
            lines = data['lines']
            bubble_height = data['bubble_height']
            name_height = data['name_height']
            
            username_color = self._get_username_color(msg.username)
            
            # Draw avatar
            avatar_x = padding
            self._draw_avatar(img, avatar_x, current_y, avatar_size, msg.username)
            
            # Draw bubble
            bubble_x = avatar_x + avatar_size + 12
            bubble_width = max_bubble_width
            
            self._draw_rounded_rect_filled(
                draw,
                (bubble_x, current_y, bubble_x + bubble_width, current_y + bubble_height),
                bubble_radius,
                bubble_color
            )
            
            # Draw username
            name_x = bubble_x + bubble_padding
            name_y = current_y + bubble_padding - 4
            draw.text((name_x, name_y), msg.username, font=self.username_font, fill=username_color)
            
            # Draw text
            text_x = bubble_x + bubble_padding
            text_y = name_y + name_height + 4
            
            try:
                line_height = self.text_font_small.getbbox("Ayg")[3] + 4
            except:
                line_height = 26
            
            for line in lines:
                if text_y >= img_height - padding:
                    break
                draw.text((text_x, text_y), line, font=self.text_font_small, fill=text_color)
                text_y += line_height
            
            # Draw time
            time_text = msg.timestamp or "12:00"
            try:
                time_width = self.time_font.getbbox(time_text)[2]
            except:
                time_width = 40
            time_x = bubble_x + bubble_width - bubble_padding - time_width
            time_y = current_y + bubble_height - 22
            draw.text((time_x, time_y), time_text, font=self.time_font, fill=time_color)
            
            current_y += bubble_height + message_gap
        
        # Save
        output = BytesIO()
        img.save(output, format='WEBP', quality=95, method=6)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=img_width,
            height=img_height
        )

    async def render_roast_quote(
        self,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        style: Optional[QuoteStyle] = None
    ) -> QuoteImage:
        """
        Render a quote with Oleg's roast comment - two message bubbles.
        """
        if style is None:
            style = QuoteStyle()
        
        # Generate roast comment
        comment = await self.generate_roast_comment(text)
        
        is_dark = style.theme != QuoteTheme.LIGHT
        
        # Colors
        bg_color = TELEGRAM_COLORS["background_dark"] if is_dark else TELEGRAM_COLORS["background_light"]
        bubble_color = TELEGRAM_COLORS["bubble_dark"] if is_dark else TELEGRAM_COLORS["bubble_incoming"]
        oleg_bubble_color = (45, 45, 45) if is_dark else (255, 243, 224)  # Slightly different for Oleg
        text_color = TELEGRAM_COLORS["text_dark"] if is_dark else TELEGRAM_COLORS["text_light"]
        time_color = TELEGRAM_COLORS["time_dark"] if is_dark else TELEGRAM_COLORS["time_light"]
        oleg_color = (255, 193, 7)  # Gold for Oleg
        
        # Layout
        padding = 25
        avatar_size = 56
        bubble_padding = 18
        bubble_radius = 16
        message_gap = 16
        max_bubble_width = MAX_IMAGE_WIDTH - padding * 2 - avatar_size - 30
        max_text_width = max_bubble_width - bubble_padding * 2
        
        # Calculate original message dimensions
        lines1 = self._wrap_text(text, self.text_font, max_text_width)
        text_height1 = self._get_text_height(lines1, self.text_font)
        try:
            name_height = self.username_font.getbbox(username)[3]
        except:
            name_height = 26
        bubble_height1 = name_height + 8 + text_height1 + 8 + 24
        
        # Calculate Oleg's comment dimensions
        lines2 = self._wrap_text(comment, self.comment_font, max_text_width)
        text_height2 = self._get_text_height(lines2, self.comment_font)
        bubble_height2 = name_height + 8 + text_height2 + 8 + 24
        
        # Image dimensions
        img_width = MAX_IMAGE_WIDTH
        img_height = min(MAX_IMAGE_HEIGHT, padding * 2 + bubble_height1 + message_gap + bubble_height2)
        
        # Create image
        img = Image.new('RGB', (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        username_color = self._get_username_color(username)
        
        # Draw first message (original)
        current_y = padding
        avatar_x = padding
        self._draw_avatar(img, avatar_x, current_y, avatar_size, username)
        
        bubble_x = avatar_x + avatar_size + 12
        self._draw_rounded_rect_filled(
            draw,
            (bubble_x, current_y, bubble_x + max_bubble_width, current_y + bubble_height1),
            bubble_radius,
            bubble_color
        )
        self._draw_bubble_tail(draw, bubble_x, current_y + 20, bubble_color, left=True)
        
        # Username
        name_x = bubble_x + bubble_padding
        name_y = current_y + bubble_padding - 4
        draw.text((name_x, name_y), username, font=self.username_font, fill=username_color)
        
        # Text
        text_y = name_y + name_height + 6
        try:
            line_height = self.text_font.getbbox("Ayg")[3] + 6
        except:
            line_height = 34
        for line in lines1:
            draw.text((name_x, text_y), line, font=self.text_font, fill=text_color)
            text_y += line_height
        
        # Time
        draw.text(
            (bubble_x + max_bubble_width - bubble_padding - 50, current_y + bubble_height1 - 26),
            "12:00",
            font=self.time_font,
            fill=time_color
        )
        
        # Draw Oleg's response
        current_y += bubble_height1 + message_gap
        
        # Oleg avatar (red circle with O)
        oleg_avatar_x = img_width - padding - avatar_size
        draw.ellipse(
            [oleg_avatar_x, current_y, oleg_avatar_x + avatar_size, current_y + avatar_size],
            fill=(220, 53, 69)
        )
        try:
            o_bbox = self.username_font.getbbox("O")
            o_w, o_h = o_bbox[2] - o_bbox[0], o_bbox[3] - o_bbox[1]
        except:
            o_w, o_h = 20, 20
        draw.text(
            (oleg_avatar_x + (avatar_size - o_w) // 2, current_y + (avatar_size - o_h) // 2 - 4),
            "O",
            font=self.username_font,
            fill=(255, 255, 255)
        )
        
        # Oleg's bubble (right side)
        oleg_bubble_x = oleg_avatar_x - 12 - max_bubble_width
        self._draw_rounded_rect_filled(
            draw,
            (oleg_bubble_x, current_y, oleg_bubble_x + max_bubble_width, current_y + bubble_height2),
            bubble_radius,
            oleg_bubble_color
        )
        self._draw_bubble_tail(draw, oleg_bubble_x + max_bubble_width, current_y + 20, oleg_bubble_color, left=False)
        
        # Oleg name
        name_x = oleg_bubble_x + bubble_padding
        name_y = current_y + bubble_padding - 4
        draw.text((name_x, name_y), "Олег 🔥", font=self.username_font, fill=oleg_color)
        
        # Oleg's comment
        text_y = name_y + name_height + 6
        try:
            line_height = self.comment_font.getbbox("Ayg")[3] + 6
        except:
            line_height = 30
        for line in lines2:
            draw.text((name_x, text_y), line, font=self.comment_font, fill=oleg_color)
            text_y += line_height
        
        # Time
        draw.text(
            (oleg_bubble_x + max_bubble_width - bubble_padding - 50, current_y + bubble_height2 - 26),
            "12:01",
            font=self.time_font,
            fill=time_color
        )
        
        # Save
        output = BytesIO()
        img.save(output, format='WEBP', quality=95, method=6)
        output.seek(0)
        
        return QuoteImage(
            image_data=output.getvalue(),
            format='webp',
            width=img_width,
            height=img_height
        )

    async def generate_roast_comment(self, text: str) -> str:
        """Generate a roast comment from Oleg using LLM."""
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
                "Можешь ругнуться, но без оскорблений по запрещённым признакам."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": roast_prompt}
            ]
            
            comment = await _ollama_chat(messages, temperature=0.8)
            
            if len(comment) > 200:
                comment = comment[:197] + "..."
            
            return comment
            
        except Exception as e:
            logger.warning(f"Failed to generate roast comment: {e}")
            fallbacks = [
                "Ну такое себе, честно говоря.",
                "Это что вообще было?",
                "Классика жанра, чё.",
                "Без комментариев... хотя нет, вот он.",
                "Ладно, записал в архив кринжа.",
                "Охуенно сказано, запишу.",
                "Мудрость веков, блять.",
            ]
            return random.choice(fallbacks)

    async def queue_render_task(
        self,
        chat_id: int,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        timestamp: Optional[str] = None,
        theme: str = "dark",
        is_chain: bool = False,
        messages: Optional[List[dict]] = None,
        is_roast: bool = False,
    ):
        """Queue quote rendering task to worker (if available)."""
        try:
            from app.worker import enqueue_quote_render_task
            from app.config import settings
            
            if not settings.worker_enabled or not settings.redis_enabled:
                logger.debug(f"Worker not enabled, quote task not queued for chat {chat_id}")
                return None
            
            messages_data = None
            if is_chain and messages:
                messages_data = [
                    {
                        "text": m.text if hasattr(m, 'text') else m.get("text", ""),
                        "username": m.username if hasattr(m, 'username') else m.get("username", ""),
                        "timestamp": m.timestamp if hasattr(m, 'timestamp') else m.get("timestamp"),
                    }
                    for m in messages
                ]
            
            job = await enqueue_quote_render_task(
                text=text,
                username=username,
                chat_id=chat_id,
                reply_to=None,
                avatar_url=avatar_url,
                timestamp=timestamp,
                theme=theme,
                is_chain=is_chain,
                messages=messages_data,
                is_roast=is_roast,
            )
            return job
        except Exception as e:
            logger.error(f"Failed to queue quote render task: {e}")
            return None


# Global service instance
quote_generator_service = QuoteGeneratorService()
