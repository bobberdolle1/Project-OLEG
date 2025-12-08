"""
Sparkline Generator for growth history visualization.

Generates mini chart images showing growth/decline history.
Uses Pillow for image generation.

Requirements: 7.1 - Generate sparkline image for growth history
"""

import io
from typing import List, Optional
from dataclasses import dataclass

from PIL import Image, ImageDraw


@dataclass
class SparklineData:
    """Data point for sparkline chart."""
    date: str
    size: int
    change: int


class SparklineGenerator:
    """
    Generates sparkline images for growth history visualization.
    
    Creates mini chart images showing growth/decline over time.
    Requirements: 7.1
    """
    
    # Chart dimensions
    WIDTH = 200
    HEIGHT = 60
    PADDING = 5
    
    # Colors
    BG_COLOR = (45, 45, 50)
    LINE_COLOR = (100, 200, 100)  # Green for growth
    DECLINE_COLOR = (200, 100, 100)  # Red for decline
    POINT_COLOR = (255, 255, 255)
    GRID_COLOR = (60, 60, 65)
    
    def __init__(self):
        """Initialize the sparkline generator."""
        pass
    
    def generate(self, history: Optional[List[dict]]) -> Optional[bytes]:
        """
        Generate a sparkline PNG image from growth history.
        
        Args:
            history: List of growth history entries with date, size, change
                    Example: [{"date": "2025-12-01", "size": 50, "change": 5}, ...]
            
        Returns:
            PNG image as bytes, or None if insufficient data
        """
        if not history or len(history) < 2:
            return None
        
        # Extract sizes for plotting
        sizes = [entry.get("size", 0) for entry in history]
        changes = [entry.get("change", 0) for entry in history]
        
        if not sizes:
            return None
        
        # Create image
        image = Image.new("RGBA", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Calculate chart area
        chart_left = self.PADDING
        chart_right = self.WIDTH - self.PADDING
        chart_top = self.PADDING
        chart_bottom = self.HEIGHT - self.PADDING
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        # Draw subtle grid lines
        for i in range(3):
            y = chart_top + (chart_height * i) // 2
            draw.line([(chart_left, y), (chart_right, y)], fill=self.GRID_COLOR, width=1)
        
        # Calculate min/max for scaling
        min_size = min(sizes)
        max_size = max(sizes)
        size_range = max_size - min_size
        
        # Avoid division by zero
        if size_range == 0:
            size_range = 1
        
        # Calculate points
        points = []
        num_points = len(sizes)
        for i, size in enumerate(sizes):
            x = chart_left + (i * chart_width) // (num_points - 1) if num_points > 1 else chart_left + chart_width // 2
            # Normalize size to chart height (inverted because y increases downward)
            normalized = (size - min_size) / size_range
            y = chart_bottom - int(normalized * chart_height)
            points.append((x, y))
        
        # Determine overall trend for line color
        overall_change = sum(changes)
        line_color = self.LINE_COLOR if overall_change >= 0 else self.DECLINE_COLOR
        
        # Draw the line
        if len(points) >= 2:
            draw.line(points, fill=line_color, width=2)
        
        # Draw points
        point_radius = 3
        for i, (x, y) in enumerate(points):
            # Color point based on individual change
            change = changes[i] if i < len(changes) else 0
            point_color = self.LINE_COLOR if change >= 0 else self.DECLINE_COLOR
            draw.ellipse(
                [(x - point_radius, y - point_radius), 
                 (x + point_radius, y + point_radius)],
                fill=point_color,
                outline=self.POINT_COLOR
            )
        
        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
    
    def generate_with_labels(self, history: Optional[List[dict]]) -> Optional[bytes]:
        """
        Generate a sparkline with min/max labels.
        
        Args:
            history: List of growth history entries
            
        Returns:
            PNG image as bytes with labels, or None if insufficient data
        """
        if not history or len(history) < 2:
            return None
        
        # Use larger dimensions for labeled version
        width = 250
        height = 80
        padding = 10
        label_space = 30
        
        sizes = [entry.get("size", 0) for entry in history]
        changes = [entry.get("change", 0) for entry in history]
        
        if not sizes:
            return None
        
        # Create image
        image = Image.new("RGBA", (width, height), self.BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Calculate chart area (leave space for labels on left)
        chart_left = padding + label_space
        chart_right = width - padding
        chart_top = padding
        chart_bottom = height - padding
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        # Calculate min/max
        min_size = min(sizes)
        max_size = max(sizes)
        size_range = max_size - min_size if max_size != min_size else 1
        
        # Draw min/max labels
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
        except Exception:
            font = None
        
        # Max label at top
        draw.text((padding, chart_top), str(max_size), fill=(150, 150, 150), font=font)
        # Min label at bottom
        draw.text((padding, chart_bottom - 10), str(min_size), fill=(150, 150, 150), font=font)
        
        # Calculate points
        points = []
        num_points = len(sizes)
        for i, size in enumerate(sizes):
            x = chart_left + (i * chart_width) // (num_points - 1) if num_points > 1 else chart_left + chart_width // 2
            normalized = (size - min_size) / size_range
            y = chart_bottom - int(normalized * chart_height)
            points.append((x, y))
        
        # Determine line color
        overall_change = sum(changes)
        line_color = self.LINE_COLOR if overall_change >= 0 else self.DECLINE_COLOR
        
        # Draw line
        if len(points) >= 2:
            draw.line(points, fill=line_color, width=2)
        
        # Draw points
        point_radius = 3
        for i, (x, y) in enumerate(points):
            change = changes[i] if i < len(changes) else 0
            point_color = self.LINE_COLOR if change >= 0 else self.DECLINE_COLOR
            draw.ellipse(
                [(x - point_radius, y - point_radius), 
                 (x + point_radius, y + point_radius)],
                fill=point_color,
                outline=self.POINT_COLOR
            )
        
        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
sparkline_generator = SparklineGenerator()
