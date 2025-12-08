"""
Profile Generator for visual profile cards.

Generates PNG images with avatar, username, league badge, ELO, and stats.
Uses Pillow for image generation.

Requirements: 12.1, 12.2, 12.3
"""

import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.services.leagues import League


@dataclass
class ProfileData:
    """Data required to generate a profile card."""
    username: str
    avatar_bytes: Optional[bytes]
    elo: int
    league: League
    wins: int
    losses: int
    size_cm: int
    reputation: int
    balance: int
    grow_count: int
    casino_jackpots: int


class ProfileGenerator:
    """
    Generates visual profile card images.
    
    Creates PNG images with:
    - Avatar (or placeholder)
    - Username
    - League badge with styling
    - ELO rating
    - Win/loss stats
    - Other game statistics
    
    Requirements: 12.1, 12.2, 12.3
    """
    
    # Card dimensions
    CARD_WIDTH = 600
    CARD_HEIGHT = 400
    
    # League color schemes
    LEAGUE_COLORS = {
        League.SCRAP: {
            "bg": (45, 45, 50),
            "accent": (139, 119, 101),
            "text": (200, 200, 200),
            "badge_bg": (80, 70, 60),
        },
        League.SILICON: {
            "bg": (35, 45, 55),
            "accent": (100, 149, 237),
            "text": (220, 220, 230),
            "badge_bg": (60, 80, 100),
        },
        League.QUANTUM: {
            "bg": (40, 30, 50),
            "accent": (148, 103, 189),
            "text": (230, 220, 240),
            "badge_bg": (80, 60, 100),
        },
        League.ELITE: {
            "bg": (50, 40, 20),
            "accent": (255, 215, 0),
            "text": (255, 250, 240),
            "badge_bg": (100, 80, 40),
        },
    }

    # Avatar settings
    AVATAR_SIZE = 100
    AVATAR_POSITION = (30, 30)
    
    # Font sizes (using default font since custom fonts may not be available)
    FONT_SIZE_LARGE = 28
    FONT_SIZE_MEDIUM = 20
    FONT_SIZE_SMALL = 16
    
    def __init__(self):
        """Initialize the profile generator."""
        # Use default font (Pillow's built-in)
        try:
            self._font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.FONT_SIZE_LARGE)
            self._font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.FONT_SIZE_MEDIUM)
            self._font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.FONT_SIZE_SMALL)
        except (OSError, IOError):
            # Fallback to default font if system fonts not available
            self._font_large = ImageFont.load_default()
            self._font_medium = ImageFont.load_default()
            self._font_small = ImageFont.load_default()
    
    def generate(self, data: ProfileData) -> bytes:
        """
        Generate a PNG profile card image.
        
        Args:
            data: ProfileData with all required information
            
        Returns:
            PNG image as bytes
        """
        colors = self.LEAGUE_COLORS.get(data.league, self.LEAGUE_COLORS[League.SCRAP])
        
        # Create base image
        image = Image.new("RGB", (self.CARD_WIDTH, self.CARD_HEIGHT), colors["bg"])
        draw = ImageDraw.Draw(image)
        
        # Draw decorative border
        self._draw_border(draw, colors)
        
        # Draw avatar
        self._draw_avatar(image, data.avatar_bytes, colors)
        
        # Draw username
        self._draw_username(draw, data.username, colors)
        
        # Draw league badge
        self._draw_league_badge(draw, data.league, colors)
        
        # Draw ELO rating
        self._draw_elo(draw, data.elo, colors)
        
        # Draw stats
        self._draw_stats(draw, data, colors)
        
        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
    
    def _draw_border(self, draw: ImageDraw.ImageDraw, colors: dict) -> None:
        """Draw decorative border around the card."""
        # Outer border
        draw.rectangle(
            [(0, 0), (self.CARD_WIDTH - 1, self.CARD_HEIGHT - 1)],
            outline=colors["accent"],
            width=3
        )
        # Inner accent line
        draw.rectangle(
            [(5, 5), (self.CARD_WIDTH - 6, self.CARD_HEIGHT - 6)],
            outline=colors["accent"],
            width=1
        )
    
    def _draw_avatar(self, image: Image.Image, avatar_bytes: Optional[bytes], colors: dict) -> None:
        """Draw avatar or placeholder circle."""
        if avatar_bytes:
            try:
                avatar = Image.open(io.BytesIO(avatar_bytes))
                avatar = avatar.resize((self.AVATAR_SIZE, self.AVATAR_SIZE))
                # Create circular mask
                mask = Image.new("L", (self.AVATAR_SIZE, self.AVATAR_SIZE), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([(0, 0), (self.AVATAR_SIZE - 1, self.AVATAR_SIZE - 1)], fill=255)
                # Apply mask and paste
                image.paste(avatar, self.AVATAR_POSITION, mask)
            except Exception:
                self._draw_avatar_placeholder(image, colors)
        else:
            self._draw_avatar_placeholder(image, colors)
    
    def _draw_avatar_placeholder(self, image: Image.Image, colors: dict) -> None:
        """Draw a placeholder circle for missing avatar."""
        draw = ImageDraw.Draw(image)
        x, y = self.AVATAR_POSITION
        draw.ellipse(
            [(x, y), (x + self.AVATAR_SIZE - 1, y + self.AVATAR_SIZE - 1)],
            fill=colors["badge_bg"],
            outline=colors["accent"],
            width=2
        )
        # Draw user icon placeholder
        center_x = x + self.AVATAR_SIZE // 2
        center_y = y + self.AVATAR_SIZE // 2
        # Head
        draw.ellipse(
            [(center_x - 15, center_y - 25), (center_x + 15, center_y - 5)],
            fill=colors["text"]
        )
        # Body
        draw.ellipse(
            [(center_x - 25, center_y + 5), (center_x + 25, center_y + 40)],
            fill=colors["text"]
        )

    def _draw_username(self, draw: ImageDraw.ImageDraw, username: str, colors: dict) -> None:
        """Draw the username."""
        x = self.AVATAR_POSITION[0] + self.AVATAR_SIZE + 20
        y = 35
        draw.text((x, y), username, fill=colors["text"], font=self._font_large)
    
    def _draw_league_badge(self, draw: ImageDraw.ImageDraw, league: League, colors: dict) -> None:
        """Draw the league badge with emoji and name."""
        x = self.AVATAR_POSITION[0] + self.AVATAR_SIZE + 20
        y = 75
        
        # Badge background
        badge_width = 180
        badge_height = 30
        draw.rounded_rectangle(
            [(x, y), (x + badge_width, y + badge_height)],
            radius=5,
            fill=colors["badge_bg"],
            outline=colors["accent"],
            width=1
        )
        
        # League name (without emoji since Pillow can't render it well)
        league_text = league.display_name.split(" ", 1)[-1]  # Remove emoji
        draw.text((x + 10, y + 5), league_text, fill=colors["accent"], font=self._font_medium)
    
    def _draw_elo(self, draw: ImageDraw.ImageDraw, elo: int, colors: dict) -> None:
        """Draw the ELO rating."""
        x = self.AVATAR_POSITION[0] + self.AVATAR_SIZE + 20
        y = 115
        draw.text((x, y), f"ELO: {elo}", fill=colors["text"], font=self._font_medium)
    
    def _draw_stats(self, draw: ImageDraw.ImageDraw, data: ProfileData, colors: dict) -> None:
        """Draw game statistics."""
        # Stats section starts below avatar
        start_y = 160
        left_x = 30
        right_x = 320
        line_height = 35
        
        # Divider line
        draw.line(
            [(20, start_y - 10), (self.CARD_WIDTH - 20, start_y - 10)],
            fill=colors["accent"],
            width=1
        )
        
        # Left column stats
        stats_left = [
            (f"Размер: {data.size_cm} см", "📏"),
            (f"Репутация: {data.reputation}", "🏅"),
            (f"Баланс: {data.balance}", "💰"),
        ]
        
        # Right column stats
        stats_right = [
            (f"Побед: {data.wins}", "⚔️"),
            (f"Поражений: {data.losses}", "💀"),
            (f"Выращиваний: {data.grow_count}", "🌱"),
        ]
        
        # Draw left column
        for i, (text, _) in enumerate(stats_left):
            y = start_y + i * line_height
            draw.text((left_x, y), text, fill=colors["text"], font=self._font_medium)
        
        # Draw right column
        for i, (text, _) in enumerate(stats_right):
            y = start_y + i * line_height
            draw.text((right_x, y), text, fill=colors["text"], font=self._font_medium)
        
        # Win rate at bottom
        total_games = data.wins + data.losses
        if total_games > 0:
            win_rate = (data.wins / total_games) * 100
            win_rate_text = f"Винрейт: {win_rate:.1f}%"
        else:
            win_rate_text = "Винрейт: N/A"
        
        y = start_y + 3 * line_height + 10
        draw.text((left_x, y), win_rate_text, fill=colors["accent"], font=self._font_medium)
        
        # Jackpots
        jackpot_text = f"Джекпотов: {data.casino_jackpots}"
        draw.text((right_x, y), jackpot_text, fill=colors["text"], font=self._font_medium)


# Singleton instance
profile_generator = ProfileGenerator()
