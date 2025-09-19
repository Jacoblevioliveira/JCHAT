import time
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox

from ..data_logger import data_logger

class ConsentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Consent Form")
        self.resize(720, 600)

        layout = QVBoxLayout(self)
        self.view = QTextBrowser()
        try:
            consent_path = Path(__file__).parent.parent.parent / "consent.html"
            self.view.setHtml(consent_path.read_text(encoding="utf-8"))
        except Exception:
            self.view.setHtml("<h2>Consent Form</h2><p>(consent.html not found)</p>")
        layout.addWidget(self.view)

        buttons = QDialogButtonBox()
        agree = buttons.addButton("I Agree", QDialogButtonBox.AcceptRole)
        disagree = buttons.addButton("I Do Not Agree", QDialogButtonBox.RejectRole)
        agree.clicked.connect(self._accept_and_log)
        disagree.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_and_log(self) -> None:
        try:
            setattr(data_logger.session, "consented", True)
            setattr(data_logger.session, "consent_timestamp", time.time())
            setattr(data_logger.session, "consent_version", "v1")
        except Exception:
            pass
        self.accept()

class DebriefDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debrief")
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        self.view = QTextBrowser()
        try:
            debrief_path = Path(__file__).parent.parent.parent / "debrief.html"
            self.view.setHtml(debrief_path.read_text(encoding="utf-8"))
        except Exception:
            self.view.setHtml("<h2>Debrief</h2><p>(debrief.html not found)</p>")
        layout.addWidget(self.view)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("Close")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)

    def showEvent(self, event):
        try:
            setattr(data_logger.session, "debrief_shown", True)
            setattr(data_logger.session, "debrief_timestamp", time.time())
        except Exception:
            pass
        super().showEvent(event)