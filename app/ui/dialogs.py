import time
from PySide6.QtCore import Qt, QRegularExpression, QTimer
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox

from .. import constants
from ..data_logger import data_logger

class SonaIdDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter SONA ID")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        title = QLabel("Enter Your SONA ID")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:16pt;font-weight:bold;margin-bottom:8px;")
        layout.addWidget(title)

        prompt = QLabel("Please enter your 6-digit SONA ID:")
        layout.addWidget(prompt)

        self.input = QLineEdit()
        self.input.setMaxLength(6)
        rx = QRegularExpression(r"^\d{0,6}$")
        self.input.setValidator(QRegularExpressionValidator(rx, self.input))
        self.input.setPlaceholderText("e.g., 123456")
        layout.addWidget(self.input)

        self.error = QLabel("")
        self.error.setStyleSheet("color:#b10d2c;font-weight:bold;")
        layout.addWidget(self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Begin")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.input.setFocus()

    def _accept_if_valid(self) -> None:
        text = self.input.text().strip()
        if len(text) != 6 or not text.isdigit():
            self.error.setText("SONA ID must be exactly 6 digits.")
            return
        
        constants.SONA_ID = text
        try:
            setattr(data_logger.session, "sona_id", constants.SONA_ID)
            setattr(data_logger.session, "sona_timestamp", time.time())
        except Exception:
            pass
        self.accept()

class TransitionDialog(QDialog):
    def __init__(self, message, duration_ms=3000, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setStyleSheet("background-color: #2d3748; border-radius: 15px;")
        layout = QVBoxLayout(self)
        self.label = QLabel(message, self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: white; font-size: 22pt; font-weight: bold; padding: 40px;")
        layout.addWidget(self.label)
        QTimer.singleShot(duration_ms, self.accept)