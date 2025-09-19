from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen
from PySide6.QtWidgets import QLabel

class CustomTooltip(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QLabel {
                color: white;
                padding: 12px 16px;
                font-size: 11pt;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        self.setWordWrap(True)
        self.setMaximumWidth(400)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect, 8, 8)
        
        background_color = QColor(45, 55, 72, 240)
        painter.fillPath(path, background_color)
        
        pen = QPen(QColor(255, 255, 255, 77), 1)
        painter.setPen(pen)
        painter.drawPath(path)
        
        painter.end()
        super().paintEvent(event)

current_tooltip = None