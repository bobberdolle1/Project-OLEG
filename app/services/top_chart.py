"""
Top 10 Chart Generator for multi-player growth visualization.

Generates comprehensive charts showing all top 10 players' growth history
with different colors for each player.

Requirements: 7.1 - Generate multi-line chart for top 10 players
"""

import io
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

import logging

logger = logging.getLogger(__name__)


class TopChartGenerator:
    """
    Generates multi-line charts for top 10 players visualization.
    
    Creates comprehensive charts showing growth history of all top players
    with distinct colors for each player.
    """
    
    # Chart dimensions
    WIDTH = 800
    HEIGHT = 500
    PADDING = 40
    LEGEND_WIDTH = 150
    
    # Colors for top 10 players (vibrant and distinct)
    PLAYER_COLORS = [
        (255, 215, 0),    # Gold - 1st place
        (192, 192, 192),  # Silver - 2nd place
        (205, 127, 50),   # Bronze - 3rd place
        (255, 99, 71),    # Tomato red
        (50, 205, 50),    # Lime green
        (30, 144, 255),   # Dodger blue
        (255, 20, 147),   # Deep pink
        (138, 43, 226),   # Blue violet
        (255, 140, 0),    # Dark orange
        (0, 255, 255),    # Cyan
    ]
    
    # Background and grid colors
    BG_COLOR = (30, 30, 35)
    GRID_COLOR = (50, 50, 55)
    TEXT_COLOR = (200, 200, 200)
    AXIS_COLOR = (150, 150, 150)
    
    def __init__(self):
        """Initialize the chart generator."""
        pass
    
    def generate_top10_chart(self, top10_players: List) -> Optional[bytes]:
        """
        Generate a multi-line chart showing growth history for all top 10 players.
        
        Args:
            top10_players: List of GameStat objects (top 10 by size)
            
        Returns:
            PNG image as bytes, or None if insufficient data
        """
        if not top10_players:
            return None
        
        # Filter players with sufficient history
        players_with_history = [
            p for p in top10_players 
            if p.grow_history and len(p.grow_history) >= 2
        ]
        
        if not players_with_history:
            logger.info("No players with sufficient growth history")
            return None
        
        # Create image
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", 12)
            font_small = ImageFont.truetype("arial.ttf", 10)
            font_title = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()
            font_small = font
            font_title = font
        
        # Calculate chart area
        chart_left = self.PADDING + 50  # Space for Y-axis labels
        chart_right = self.WIDTH - self.PADDING - self.LEGEND_WIDTH
        chart_top = self.PADDING + 30  # Space for title
        chart_bottom = self.HEIGHT - self.PADDING - 30  # Space for X-axis labels
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        # Draw title
        title = "📈 ГРАФИК РОСТА ТОП-10 ИГРОКОВ"
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.WIDTH - self.LEGEND_WIDTH - title_width) // 2, 10),
            title,
            fill=(255, 255, 255),
            font=font_title
        )
        
        # Find global min/max for Y-axis scaling
        all_sizes = []
        max_history_length = 0
        for player in players_with_history:
            sizes = [entry.get("size", 0) for entry in player.grow_history]
            all_sizes.extend(sizes)
            max_history_length = max(max_history_length, len(player.grow_history))
        
        if not all_sizes:
            return None
        
        min_size = min(all_sizes)
        max_size = max(all_sizes)
        size_range = max_size - min_size if max_size != min_size else 1
        
        # Draw grid lines (horizontal)
        num_grid_lines = 5
        for i in range(num_grid_lines + 1):
            y = chart_top + (chart_height * i) // num_grid_lines
            draw.line([(chart_left, y), (chart_right, y)], fill=self.GRID_COLOR, width=1)
            
            # Y-axis label
            size_value = max_size - (size_range * i) // num_grid_lines
            label = f"{size_value}"
            draw.text((self.PADDING, y - 6), label, fill=self.TEXT_COLOR, font=font_small)
        
        # Draw vertical grid lines
        num_vertical_lines = min(7, max_history_length)
        for i in range(num_vertical_lines):
            x = chart_left + (chart_width * i) // (num_vertical_lines - 1) if num_vertical_lines > 1 else chart_left
            draw.line([(x, chart_top), (x, chart_bottom)], fill=self.GRID_COLOR, width=1)
        
        # Draw axes
        draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=self.AXIS_COLOR, width=2)
        draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=self.AXIS_COLOR, width=2)
        
        # Draw Y-axis label
        y_label = "Размер (см)"
        draw.text((5, chart_top + chart_height // 2 - 20), y_label, fill=self.TEXT_COLOR, font=font)
        
        # Draw X-axis label
        x_label = "История (дни)"
        x_label_bbox = draw.textbbox((0, 0), x_label, font=font)
        x_label_width = x_label_bbox[2] - x_label_bbox[0]
        draw.text(
            (chart_left + (chart_width - x_label_width) // 2, chart_bottom + 15),
            x_label,
            fill=self.TEXT_COLOR,
            font=font
        )
        
        # Draw each player's line
        legend_y = chart_top
        for idx, player in enumerate(players_with_history[:10]):  # Limit to 10
            color = self.PLAYER_COLORS[idx % len(self.PLAYER_COLORS)]
            
            # Extract history data
            history = player.grow_history
            sizes = [entry.get("size", 0) for entry in history]
            
            if len(sizes) < 2:
                continue
            
            # Calculate points
            points = []
            num_points = len(sizes)
            for i, size in enumerate(sizes):
                x = chart_left + (i * chart_width) // (num_points - 1) if num_points > 1 else chart_left
                normalized = (size - min_size) / size_range
                y = chart_bottom - int(normalized * chart_height)
                points.append((x, y))
            
            # Draw line
            if len(points) >= 2:
                draw.line(points, fill=color, width=2)
            
            # Draw points
            point_radius = 3
            for x, y in points:
                draw.ellipse(
                    [(x - point_radius, y - point_radius), 
                     (x + point_radius, y + point_radius)],
                    fill=color,
                    outline=(255, 255, 255)
                )
            
            # Draw legend entry
            legend_x = chart_right + 10
            legend_entry_y = legend_y + (idx * 25)
            
            # Color box
            draw.rectangle(
                [(legend_x, legend_entry_y), (legend_x + 15, legend_entry_y + 10)],
                fill=color,
                outline=(255, 255, 255)
            )
            
            # Player name (truncate if too long)
            name = player.username or str(player.tg_user_id)
            if len(name) > 12:
                name = name[:12] + "..."
            
            # Medal for top 3
            medal = ""
            rank = idx + 1
            if rank == 1:
                medal = "🥇 "
            elif rank == 2:
                medal = "🥈 "
            elif rank == 3:
                medal = "🥉 "
            else:
                medal = f"{rank}. "
            
            legend_text = f"{medal}{name}"
            draw.text(
                (legend_x + 20, legend_entry_y - 2),
                legend_text,
                fill=self.TEXT_COLOR,
                font=font_small
            )
            
            # Current size
            size_text = f"{player.size_cm}см"
            draw.text(
                (legend_x + 20, legend_entry_y + 10),
                size_text,
                fill=color,
                font=font_small
            )
        
        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
top_chart_generator = TopChartGenerator()
