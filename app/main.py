import sys
import io
import logging
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from dotenv import load_dotenv

from app.ui.control_panel import ControlPanel

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

load_dotenv()

if not os.getenv("SERPAPI_KEY"):
    log.warning("SERPAPI_KEY not set; the 'Search Web' button will not fetch results.")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    style_file = Path(__file__).parent / "style.qss"
    if style_file.exists():
        app.setStyleSheet(style_file.read_text())

    panel = ControlPanel()
    panel.showMaximized()

    sys.exit(app.exec())