"""
Profile Generator v2 - Modern visual profile cards.

Features:
- Gradient backgrounds based on league
- Circular avatar with border
- Progress bar to next league
- Sparkline for growth history
- Rank title display
- Social info (marriage, guild, duo)
- Achievement badges
- Quest progress
- Interactive buttons in caption
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Optional, List

from PIL import Image, ImageDraw, ImageFont

from app.services.leagues import League

logger = logging.getLogger(__name__)


@dataclass
class ProfileData:
    """Data required to generate a profile card."""
    username: str
    avatar_bytes: Optional[bytes] = None
    elo: int = 1000
    league: League = League.SCRAP
    wins: int = 0
    losses: int = 0
    size_cm: int = 0
    rank_title: str = "Новичок"
    reputation: int = 0
    balance: int = 0
    grow_count: int = 0
    casino_jackpots: int = 0
    # Social
    spouse_name: Optional[str] = None
    guild_name: Optional[str] = None
    duo_partner: Optional[str] = None
    # Progress
    achievements_count: int = 0
    achievements_total: int = 24
    quests_done: int = 0
    quests_total: int = 3
    # Sparkline data (last 7 days growth)
    growth_history: List[int] = field(default_factory=list)
    # Next league threshold
    next_league_elo: int = 1200


class ProfileGenerator:
    """Modern profile card generator with gradients and rich info."""
    
    CARD_WIDTH = 700
    CARD_HEIGHT = 500
    
    # League themes with gradients
    LEAGUE_THEMES = {
        League.SCRAP: {
            "gradient": [(35, 35, 40), (55, 50, 45)],
            "accent": (180, 150, 120),
            "text": (220, 215, 210),
            "highlight": (255, 200, 150),
        },
        League.SILICON: {
            "gradient": [(25, 35, 50), (40, 55, 75)],
            "accent": (100, 180, 255),
            "text": (220, 230, 245),
            "highlight": (150, 200, 255),
        },
        League.QUANTUM: {
            "gradient": [(40, 25, 55), (60, 40, 80)],
            "accent": (180, 120, 255),
            "text": (235, 225, 250),
            "highlight": (200, 150, 255),
        },
        League.ELITE: {
            "gradient": [(45, 35, 15), (70, 55, 25)],
            "accent": (255, 215, 0),
            "text": (255, 250, 235),
            "highlight": (255, 230, 100),
        },
    }
    
    AVATAR_SIZE = 120
    
    def __init__(self):
        """Initialize fonts."""
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts with fallbacks."""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/",
            "/usr/share/fonts/TTF/",
            "/Library/Fonts/",
            "C:/Windows/Fonts/",
            "fonts/",
        ]
        
        font_files = [
            ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"),
            ("NotoSans-Bold.ttf", "NotoSans-Regular.ttf"),
        ]
        
        import os
        for bold, regular in font_files:
            for path in font_paths:
                bold_path = os.path.join(path, bold)
                regular_path = os.path.join(path, regular)
                if os.path.exists(bold_path):
                    try:
                        self._font_title = ImageFont.truetype(bold_path, 32)
                        self._font_large = ImageFont.truetype(bold_path, 24)
                        self._font_medium = ImageFont.truetype(regular_path if os.path.exists(regular_path) else bold_path, 18)
                        self._font_small = ImageFont.truetype(regular_path if os.path.exists(regular_path) else bold_path, 14)
                        return
                    except Exception:
                        continue
        
        # Fallback
        self._font_title = self._font_large = self._font_medium = self._font_small = ImageFont.load_default()
    
    def generate(self, data: ProfileData) -> bytes:
        """Generate profile card image."""
        theme = self.LEAGUE_THEMES.get(data.league, self.LEAGUE_THEMES[League.SCRAP])
        
        # Create image with gradient
        image = self._create_gradient_bg(theme["gradient"])
        draw = ImageDraw.Draw(image)
        
        # Draw sections
        self._draw_header(image, draw, data, theme)
        self._draw_stats_section(draw, data, theme)
        self._draw_social_section(draw, data, theme)
        self._draw_progress_section(draw, data, theme)
        self._draw_sparkline(draw, data, theme)
        self._draw_footer(draw, data, theme)
        
        # Save
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_gradient_bg(self, colors: list) -> Image.Image:
        """Create vertical gradient background."""
        image = Image.new("RGB", (self.CARD_WIDTH, self.CARD_HEIGHT))
        draw = ImageDraw.Draw(image)
        
        c1, c2 = colors
        for y in range(self.CARD_HEIGHT):
            ratio = y / self.CARD_HEIGHT
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(0, y), (self.CARD_WIDTH, y)], fill=(r, g, b))
        
        return image
    
    def _draw_header(self, image: Image.Image, draw: ImageDraw.ImageDraw, 
                     data: ProfileData, theme: dict):
        """Draw avatar, username, rank, league."""
        # Avatar with ring
        avatar_x, avatar_y = 30, 30
        self._draw_avatar(image, draw, data.avatar_bytes, avatar_x, avatar_y, theme)
        
        # Username
        text_x = avatar_x + self.AVATAR_SIZE + 25
        draw.text((text_x, 35), data.username, fill=theme["text"], font=self._font_title)
        
        # Rank title
        draw.text((text_x, 75), data.rank_title, fill=theme["accent"], font=self._font_medium)
        
        # League badge
        league_name = data.league.display_name
        badge_y = 105
        
        # Badge background
        bbox = self._font_medium.getbbox(league_name)
        badge_w = bbox[2] - bbox[0] + 20
        self._draw_rounded_rect(draw, text_x, badge_y, text_x + badge_w, badge_y + 28, 
                                 radius=14, fill=(*theme["accent"], 40), outline=theme["accent"])
        draw.text((text_x + 10, badge_y + 4), league_name, fill=theme["highlight"], font=self._font_medium)
        
        # ELO
        elo_x = text_x + badge_w + 15
        draw.text((elo_x, badge_y + 4), f"ELO: {data.elo}", fill=theme["text"], font=self._font_medium)
        
        # Progress to next league
        if data.next_league_elo > data.elo:
            progress = min(1.0, data.elo / data.next_league_elo)
            bar_x = text_x
            bar_y = 145
            bar_w = 250
            bar_h = 8
            
            # Background
            self._draw_rounded_rect(draw, bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, 
                                     radius=4, fill=(50, 50, 55))
            # Progress
            if progress > 0:
                self._draw_rounded_rect(draw, bar_x, bar_y, bar_x + int(bar_w * progress), bar_y + bar_h,
                                         radius=4, fill=theme["accent"])
            
            # Label
            draw.text((bar_x + bar_w + 10, bar_y - 3), f"{int(progress*100)}%", 
                     fill=theme["text"], font=self._font_small)
    
    def _draw_avatar(self, image: Image.Image, draw: ImageDraw.ImageDraw,
                     avatar_bytes: Optional[bytes], x: int, y: int, theme: dict):
        """Draw circular avatar with accent ring."""
        size = self.AVATAR_SIZE
        ring_width = 4
        
        # Outer ring
        draw.ellipse([x-ring_width, y-ring_width, x+size+ring_width, y+size+ring_width],
                    fill=theme["accent"])
        
        if avatar_bytes:
            try:
                avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
                
                # Circular mask
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
                
                # Create circular avatar
                output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                output.paste(avatar, (0, 0))
                output.putalpha(mask)
                
                image.paste(output, (x, y), output)
                return
            except Exception as e:
                logger.debug(f"Avatar load failed: {e}")
        
        # Placeholder
        draw.ellipse([x, y, x+size, y+size], fill=(60, 60, 65))
        # User icon
        cx, cy = x + size//2, y + size//2
        draw.ellipse([cx-20, cy-30, cx+20, cy-5], fill=theme["text"])  # Head
        draw.ellipse([cx-30, cy+5, cx+30, cy+45], fill=theme["text"])  # Body
    
    def _draw_stats_section(self, draw: ImageDraw.ImageDraw, data: ProfileData, theme: dict):
        """Draw main stats in two columns."""
        start_y = 180
        left_x = 30
        right_x = 370
        line_h = 32
        
        # Divider
        draw.line([(20, start_y - 10), (self.CARD_WIDTH - 20, start_y - 10)], 
                 fill=theme["accent"], width=1)
        
        # Section title
        draw.text((left_x, start_y), "📊 СТАТИСТИКА", fill=theme["accent"], font=self._font_large)
        start_y += 40
        
        # Left column
        stats_left = [
            f"📏 Размер: {data.size_cm} см",
            f"💰 Баланс: {data.balance:,}",
            f"⚔️ Побед: {data.wins}",
            f"🌱 Grow: {data.grow_count}",
        ]
        
        # Right column
        stats_right = [
            f"🏅 Репутация: {data.reputation}",
            f"🎰 Джекпотов: {data.casino_jackpots}",
            f"💀 Поражений: {data.losses}",
            f"📈 Винрейт: {self._calc_winrate(data.wins, data.losses)}",
        ]
        
        for i, text in enumerate(stats_left):
            draw.text((left_x, start_y + i * line_h), text, fill=theme["text"], font=self._font_medium)
        
        for i, text in enumerate(stats_right):
            draw.text((right_x, start_y + i * line_h), text, fill=theme["text"], font=self._font_medium)
    
    def _draw_social_section(self, draw: ImageDraw.ImageDraw, data: ProfileData, theme: dict):
        """Draw social info (marriage, guild, duo)."""
        start_y = 340
        x = 30
        
        social_items = []
        if data.spouse_name:
            social_items.append(f"💍 {data.spouse_name}")
        if data.guild_name:
            social_items.append(f"🏰 {data.guild_name}")
        if data.duo_partner:
            social_items.append(f"👥 {data.duo_partner}")
        
        if social_items:
            draw.line([(20, start_y - 10), (self.CARD_WIDTH - 20, start_y - 10)],
                     fill=theme["accent"], width=1)
            
            # Draw horizontally
            current_x = x
            for item in social_items:
                draw.text((current_x, start_y), item, fill=theme["highlight"], font=self._font_medium)
                bbox = self._font_medium.getbbox(item)
                current_x += bbox[2] - bbox[0] + 30
    
    def _draw_progress_section(self, draw: ImageDraw.ImageDraw, data: ProfileData, theme: dict):
        """Draw achievements and quests progress."""
        y = 380
        x = 30
        
        # Achievements
        ach_text = f"🏆 Достижения: {data.achievements_count}/{data.achievements_total}"
        draw.text((x, y), ach_text, fill=theme["text"], font=self._font_small)
        
        # Mini progress bar for achievements
        bar_x = x + 180
        bar_w = 100
        bar_h = 6
        progress = data.achievements_count / max(1, data.achievements_total)
        
        self._draw_rounded_rect(draw, bar_x, y + 5, bar_x + bar_w, y + 5 + bar_h, 
                                 radius=3, fill=(50, 50, 55))
        if progress > 0:
            self._draw_rounded_rect(draw, bar_x, y + 5, bar_x + int(bar_w * progress), y + 5 + bar_h,
                                     radius=3, fill=theme["accent"])
        
        # Quests
        quest_x = 370
        quest_text = f"📜 Квесты: {data.quests_done}/{data.quests_total}"
        draw.text((quest_x, y), quest_text, fill=theme["text"], font=self._font_small)
        
        # Mini progress bar for quests
        bar_x = quest_x + 130
        progress = data.quests_done / max(1, data.quests_total)
        
        self._draw_rounded_rect(draw, bar_x, y + 5, bar_x + bar_w, y + 5 + bar_h,
                                 radius=3, fill=(50, 50, 55))
        if progress > 0:
            self._draw_rounded_rect(draw, bar_x, y + 5, bar_x + int(bar_w * progress), y + 5 + bar_h,
                                     radius=3, fill=theme["accent"])
    
    def _draw_sparkline(self, draw: ImageDraw.ImageDraw, data: ProfileData, theme: dict):
        """Draw growth sparkline in top right."""
        if not data.growth_history or len(data.growth_history) < 2:
            return
        
        # Sparkline area
        x, y = 520, 30
        w, h = 150, 60
        
        # Background
        self._draw_rounded_rect(draw, x, y, x + w, y + h, radius=8, fill=(30, 30, 35, 180))
        
        # Label
        draw.text((x + 5, y + 3), "📈 Рост", fill=theme["text"], font=self._font_small)
        
        # Normalize data
        values = data.growth_history[-7:]  # Last 7 days
        min_v = min(values)
        max_v = max(values)
        range_v = max_v - min_v if max_v != min_v else 1
        
        # Draw line
        points = []
        padding = 10
        chart_w = w - padding * 2
        chart_h = h - 30
        chart_y = y + 20
        
        for i, v in enumerate(values):
            px = x + padding + (i / (len(values) - 1)) * chart_w
            py = chart_y + chart_h - ((v - min_v) / range_v) * chart_h
            points.append((px, py))
        
        if len(points) >= 2:
            draw.line(points, fill=theme["accent"], width=2)
            # Dots
            for px, py in points:
                draw.ellipse([px-3, py-3, px+3, py+3], fill=theme["highlight"])
    
    def _draw_footer(self, draw: ImageDraw.ImageDraw, data: ProfileData, theme: dict):
        """Draw footer with hints."""
        y = self.CARD_HEIGHT - 30
        text = "/games • /shop • /quests • /achievements"
        
        bbox = self._font_small.getbbox(text)
        text_w = bbox[2] - bbox[0]
        x = (self.CARD_WIDTH - text_w) // 2
        
        draw.text((x, y), text, fill=(*theme["text"][:3], 150) if len(theme["text"]) == 3 else theme["text"], 
                 font=self._font_small)
    
    def _draw_rounded_rect(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, 
                           x2: int, y2: int, radius: int, fill=None, outline=None):
        """Draw rounded rectangle."""
        if fill:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline)
    
    def _calc_winrate(self, wins: int, losses: int) -> str:
        """Calculate win rate percentage."""
        total = wins + losses
        if total == 0:
            return "N/A"
        return f"{(wins / total) * 100:.1f}%"


# Singleton
profile_generator = ProfileGenerator()
