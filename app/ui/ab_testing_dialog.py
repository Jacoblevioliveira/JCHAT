import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextEdit, QPushButton

from app.helpers import is_enabled, get_setting_value
from app.feature_flags import FeatureFlag, feature_settings
from app.constants import MIN_THINK_TIME_MS, THINK_INTERVAL_MS

class ABTestingDialog(QDialog):
    def __init__(self, response_a: str, response_b: str, parent=None):
        super().__init__(parent)
        self.response_a = response_a
        self.response_b = response_b
        self.selected_response: str | None = None
        self.selected_version: str | None = None
        self.selection_latency: int = 0
        self.dialog_start_time = time.time()
        self.identical_content = (response_a == response_b)
        self._typewriter_timer: QTimer | None = None
        self._typewriter_index: int = 0
        self._typewriter_text: str = ""
        self._typewriter_target: QTextEdit | None = None
        self._thinking_timer: QTimer | None = None
        self._thinking_dots: int = 0
        self._thinking_target: QTextEdit | None = None
        self._typewriter_timer_b: QTimer | None = None
        self._typewriter_index_b: int = 0
        self._typewriter_text_b: str = ""
        self._typewriter_target_b: QTextEdit | None = None
        self._thinking_timer_b: QTimer | None = None
        self._thinking_dots_b: int = 0
        self._thinking_target_b: QTextEdit | None = None
        self._setup_ui()
        self._start_demonstrations()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Which presentation do you prefer?" if self.identical_content else "Which response do you prefer?")
        self.setMinimumSize(1000, 750)
        layout = QVBoxLayout(self)
        instructions_text = "Same content, different presentation. Choose which you prefer:" if self.identical_content else "Choose which response you prefer:"
        instructions = QLabel(instructions_text)
        instructions.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)
        
        responses_layout = QHBoxLayout()
        a_container = QFrame()
        a_container.setStyleSheet("QFrame { background: #f8f9fa; border: 2px solid #6c757d; border-radius: 12px; padding: 10px; margin: 5px; }")
        a_layout = QVBoxLayout(a_container)
        a_title = QLabel("Option A")
        a_title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #6c757d; margin-bottom: 5px;")
        a_title.setAlignment(Qt.AlignCenter)
        a_layout.addWidget(a_title)
        self.a_text = QTextEdit()
        self.a_text.setReadOnly(True)
        a_font_size = self._get_a_side_text_size()
        self.a_text.setStyleSheet(f"QTextEdit {{ background: white; border: 1px solid #ccc; border-radius: 8px; padding: 10px; font-size: {a_font_size}pt; min-height: 200px; }}")
        a_layout.addWidget(self.a_text)
        self.a_button = QPushButton("Choose Option A")
        self.a_button.setStyleSheet("QPushButton { background: #6c757d; color: white; border: none; border-radius: 8px; padding: 10px; font-size: 11pt; font-weight: bold; } QPushButton:hover { background: #5a6268; } QPushButton:disabled { background: #cccccc; color: #666666; }")
        self.a_button.clicked.connect(self._select_a)
        self.a_button.setEnabled(False)
        a_layout.addWidget(self.a_button)
        responses_layout.addWidget(a_container)
        
        b_container = QFrame()
        b_container.setStyleSheet("QFrame { background: #f8f9fa; border: 2px solid #6c757d; border-radius: 12px; padding: 10px; margin: 5px; }")
        b_layout = QVBoxLayout(b_container)
        b_title = QLabel("Option B")
        b_title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #6c757d; margin-bottom: 5px;")
        b_title.setAlignment(Qt.AlignCenter)
        b_layout.addWidget(b_title)
        self.b_text = QTextEdit()
        self.b_text.setReadOnly(True)
        b_font_size = self._get_b_side_text_size()
        self.b_text.setStyleSheet(f"QTextEdit {{ background: white; border: 1px solid #ccc; border-radius: 8px; padding: 10px; font-size: {b_font_size}pt; min-height: 200px; }}")
        b_layout.addWidget(self.b_text)
        self.b_button = QPushButton("Choose Option B")
        self.b_button.setStyleSheet("QPushButton { background: #6c757d; color: white; border: none; border-radius: 8px; padding: 10px; font-size: 11pt; font-weight: bold; } QPushButton:hover { background: #5a6268; } QPushButton:disabled { background: #cccccc; color: #666666; }")
        self.b_button.clicked.connect(self._select_b)
        self.b_button.setEnabled(False)
        b_layout.addWidget(self.b_button)
        responses_layout.addWidget(b_container)
        layout.addLayout(responses_layout)
        
        self.status_label = QLabel("Loading responses...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 10pt; color: #666; margin-top: 10px;")
        layout.addWidget(self.status_label)

    def _get_a_side_text_size(self) -> int:
        if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER):
            text_size = get_setting_value('text_size', False)
            if text_size is not None:
                return text_size
        return 11

    def _get_b_side_text_size(self) -> int:
        if feature_settings.get('ab_text_size_changer_b', False):
            text_size = get_setting_value('text_size', True)
            if text_size is not None:
                return text_size
        return 11

    def _start_demonstrations(self) -> None:
        if self.identical_content:
            if is_enabled(FeatureFlag.STREAMING): self._setup_streaming_for_option_a()
            elif is_enabled(FeatureFlag.THINKING): self.a_text.clear(); self._start_thinking_demo()
            elif is_enabled(FeatureFlag.TYPEWRITER): self.a_text.clear(); self._start_typewriter_demo()
            else: self.a_text.setPlainText(self.response_a)
        else:
            if is_enabled(FeatureFlag.TYPEWRITER): self.a_text.clear(); self._start_typewriter_demo()
            elif is_enabled(FeatureFlag.STREAMING): self._setup_streaming_for_option_a()
            elif is_enabled(FeatureFlag.THINKING): self.a_text.clear(); self._start_thinking_demo()
            else: self.a_text.setPlainText(self.response_a)

        if feature_settings.get('ab_streaming_b', False): self._setup_streaming_for_option_b()
        elif feature_settings.get('ab_thinking_b', False): self._start_thinking_demo_for_b()
        elif feature_settings.get('ab_typewriter_b', False): self._start_typewriter_demo_for_b()
        else: self.b_text.setPlainText(self.response_b)
        QTimer.singleShot(500, self._enable_buttons)

    def _setup_streaming_for_option_b(self):
        if not self._simulate_streaming_b():
            self.b_text.setPlainText(self.response_b)

    def _simulate_streaming_b(self):
        paragraphs = self.response_b.split('\n\n')
        if len(paragraphs) == 1:
            paragraphs = self.response_b.split('\n')
        self._simulated_chunks_b = [p + '\n\n' if i < len(paragraphs)-1 else p for i, p in enumerate(paragraphs) if p.strip()]
        self._chunk_index_b = 0
        self._streaming_display_text_b = ""
        self.b_text.clear()
        self._show_next_simulated_chunk_b()
        return True

    def _show_next_simulated_chunk_b(self):
        if self._chunk_index_b < len(self._simulated_chunks_b):
            chunk = self._simulated_chunks_b[self._chunk_index_b]
            self._streaming_display_text_b += chunk
            self.b_text.setPlainText(self._streaming_display_text_b)
            scrollbar = self.b_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            self._chunk_index_b += 1
            if self._chunk_index_b < len(self._simulated_chunks_b):
                QTimer.singleShot(600, self._show_next_simulated_chunk_b)

    def _start_thinking_demo_for_b(self):
        self.b_text.setPlainText("🤔 Thinking")
        self._thinking_dots_b = 0
        self._thinking_target_b = self.b_text
        self._thinking_timer_b = QTimer(self)
        self._thinking_timer_b.timeout.connect(self._update_thinking_b)
        self._thinking_timer_b.start(THINK_INTERVAL_MS)
        QTimer.singleShot(max(MIN_THINK_TIME_MS, 2500), self._finish_thinking_demo_for_b)

    def _update_thinking_b(self):
        self._thinking_dots_b = (self._thinking_dots_b + 1) % 4
        dots = "." * self._thinking_dots_b
        if self._thinking_target_b:
            self._thinking_target_b.setPlainText(f"🤔 Thinking{dots}")

    def _finish_thinking_demo_for_b(self):
        if self._thinking_timer_b:
            self._thinking_timer_b.stop()
            self._thinking_timer_b = None
        if feature_settings.get('ab_typewriter_b', False):
            self._start_typewriter_demo_for_b()
        else:
            self.b_text.setPlainText(self.response_b)

    def _start_typewriter_demo_for_b(self):
        self.b_text.clear()
        self._typewriter_index_b = 0
        self._typewriter_text_b = self.response_b
        self._typewriter_target_b = self.b_text
        typewriter_speed = get_setting_value('typewriter_speed_ms_b', False) or 50
        self._typewriter_timer_b = QTimer(self)
        self._typewriter_timer_b.timeout.connect(self._update_typewriter_b)
        self._typewriter_timer_b.start(typewriter_speed)

    def _update_typewriter_b(self):
        if not self._typewriter_target_b: return
        if self._typewriter_index_b < len(self._typewriter_text_b):
            current_text = self._typewriter_text_b[: self._typewriter_index_b + 1]
            self._typewriter_target_b.setPlainText(current_text)
            self._typewriter_index_b += 1
            scrollbar = self._typewriter_target_b.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            if self._typewriter_timer_b:
                self._typewriter_timer_b.stop()
                self._typewriter_timer_b = None

    def _setup_streaming_for_option_a(self):
        if is_enabled(FeatureFlag.STREAMING):
            self._simulate_streaming()
        else:
            self.a_text.setPlainText(self.response_a)
            self._enable_buttons()

    def _simulate_streaming(self):
        paragraphs = self.response_a.split('\n\n')
        if len(paragraphs) == 1:
            paragraphs = self.response_a.split('\n')
        self._simulated_chunks = [p + '\n\n' if i < len(paragraphs)-1 else p for i, p in enumerate(paragraphs) if p.strip()]
        self._chunk_index = 0
        self._streaming_display_text = ""
        self.a_text.clear()
        self._show_next_simulated_chunk()

    def _show_next_simulated_chunk(self):
        if self._chunk_index < len(self._simulated_chunks):
            chunk = self._simulated_chunks[self._chunk_index]
            self._streaming_display_text += chunk
            self.a_text.setPlainText(self._streaming_display_text)
            scrollbar = self.a_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            self._chunk_index += 1
            if self._chunk_index < len(self._simulated_chunks):
                QTimer.singleShot(800, self._show_next_simulated_chunk)
            else:
                self._finish_streaming()

    def _finish_streaming(self):
        self._enable_buttons()

    def _start_thinking_demo(self) -> None:
        self.status_label.setText("Processing...")
        self.a_text.setPlainText("🤔 Thinking")
        self._thinking_dots = 0
        self._thinking_target = self.a_text
        self._thinking_timer = QTimer(self)
        self._thinking_timer.timeout.connect(self._update_thinking)
        self._thinking_timer.start(THINK_INTERVAL_MS)
        QTimer.singleShot(max(MIN_THINK_TIME_MS, 2000), self._finish_thinking_demo)

    def _update_thinking(self) -> None:
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        if self._thinking_target:
            self._thinking_target.setPlainText(f"🤔 Thinking{dots}")

    def _finish_thinking_demo(self) -> None:
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None
        if is_enabled(FeatureFlag.TYPEWRITER):
            self._start_typewriter_demo()
        else:
            self.a_text.setPlainText(self.response_a)
            self._enable_buttons()

    def _start_typewriter_demo(self) -> None:
        self.status_label.setText("Processing...")
        self.a_text.clear()
        self._typewriter_index = 0
        self._typewriter_text = self.response_a
        self._typewriter_target = self.a_text
        typewriter_speed = get_setting_value('typewriter_speed_ms', False) or 20
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.timeout.connect(self._update_typewriter)
        self._typewriter_timer.start(typewriter_speed)

    def _update_typewriter(self) -> None:
        if not self._typewriter_target: return
        if self._typewriter_index < len(self._typewriter_text):
            current_text = self._typewriter_text[: self._typewriter_index + 1]
            self._typewriter_target.setPlainText(current_text)
            self._typewriter_index += 1
            scrollbar = self._typewriter_target.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            if self._typewriter_timer:
                self._typewriter_timer.stop()
                self._typewriter_timer = None
            self._enable_buttons()

    def _enable_buttons(self) -> None:
        self.status_label.setText("Make your choice!")
        self.a_button.setEnabled(True)
        self.b_button.setEnabled(True)

    def _select_a(self) -> None:
        self._finish_selection('A', self.response_a)

    def _select_b(self) -> None:
        self._finish_selection('B', self.response_b)

    def _finish_selection(self, version: str, response: str) -> None:
        self.selection_latency = int((time.time() - self.dialog_start_time) * 1000)
        self.selected_response = response
        self.selected_version = version
        self._cleanup_timers()
        self.accept()

    def _cleanup_timers(self) -> None:
        if self._typewriter_timer: self._typewriter_timer.stop()
        if self._thinking_timer: self._thinking_timer.stop()
        if self._typewriter_timer_b: self._typewriter_timer_b.stop()
        if self._thinking_timer_b: self._thinking_timer_b.stop()

    def closeEvent(self, event) -> None:
        self._cleanup_timers()
        super().closeEvent(event)