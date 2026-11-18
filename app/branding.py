"""The app's version and logo, shared by the overlay and the setup wizard."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

VERSION = "3.3.5a"


def create_logo_pixmap() -> QPixmap:
    """Create a large 'W' logo."""
    pixmap = QPixmap(80, 80)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(30, 30, 30, 220))
    painter.setPen(QColor(255, 210, 0))
    painter.drawRoundedRect(2, 2, 76, 76, 8, 8)
    painter.setFont(QFont("Arial", 44, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "W")
    painter.end()
    return pixmap
