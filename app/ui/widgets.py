import re
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QTextEdit, QApplication
)

class CodeBlock(QWidget):
    def __init__(self, code_text: str, language: str = "", parent=None):
        super().__init__(parent)
        self.code_text = code_text
        self.language = language
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-radius: 6px 6px 0px 0px;
                padding: 12px 16px;
                min-height: 40px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(16)
        
        lang_label_text = self.language.upper() if self.language else "CODE"
        lang_label = QLabel(lang_label_text)
        lang_label.setStyleSheet("""
            color: #6c757d; font-weight: bold; font-size: 12px; 
            padding: 6px 4px; margin: 0px;
        """)
        lang_label.setAlignment(Qt.AlignVCenter)
        
        copy_btn = QPushButton("Copy")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff; color: white;
                border: none; border-radius: 4px; padding: 8px 16px;
                font-size: 12px; font-weight: bold;
                min-width: 70px; min-height: 32px; margin: 0px;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:pressed { background-color: #004494; }
        """)
        copy_btn.clicked.connect(self._copy_code)
        copy_btn.setFixedHeight(36)
        
        header_layout.addWidget(lang_label)
        header_layout.addStretch()
        header_layout.addWidget(copy_btn)
        
        code_area = QTextEdit()
        code_area.setPlainText(self.code_text)
        code_area.setReadOnly(True)
        code_area.setStyleSheet("""
            QTextEdit {
                background-color: white; color: black;
                border: 1px solid #dee2e6; border-top: none;
                border-radius: 0px 0px 6px 6px; padding: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        
        font_metrics = code_area.fontMetrics()
        line_count = self.code_text.count('\n') + 1
        content_height = font_metrics.lineSpacing() * min(line_count, 15) + 24
        code_area.setFixedHeight(content_height)
        
        layout.addWidget(header)
        layout.addWidget(code_area)
    
    def _copy_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code_text)
        
        copy_btn = self.findChild(QPushButton)
        if copy_btn:
            original_text = copy_btn.text()
            copy_btn.setText("Copied!")
            copy_btn.setStyleSheet(copy_btn.styleSheet().replace("#007bff", "#28a745"))
            
            def reset_button():
                copy_btn.setText(original_text)
                copy_btn.setStyleSheet(copy_btn.styleSheet().replace("#28a745", "#007bff"))
            
            QTimer.singleShot(1000, reset_button)

class MessageBubble(QWidget):
    def __init__(self, message: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.message = message
        self._setup_ui()

    def _extract_and_replace_code_blocks(self, text: str) -> tuple[str, list]:
        code_blocks = []
        def replace_code_block(match):
            lang = match.group(1) or ""
            code = match.group(2)
            placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
            code_blocks.append((code, lang))
            return placeholder
        modified_text = re.sub(r'```(\w+)?\s*\n(.*?)\n```', replace_code_block, text, flags=re.DOTALL)
        return modified_text, code_blocks

    def _markdown_to_html(self, text: str) -> str:
        text = re.sub(r'`([^`]+?)`', r'<code style="background-color: #f8f9fa; color: #e83e8c; padding: 2px 4px; border-radius: 3px; font-family: Consolas, Monaco, monospace; font-size: 90%;">\1</code>', text)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
        text = text.replace('\n', '<br>')
        return text

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)

        if self.is_user:
            main_layout.addStretch()

        bubble = QFrame()
        bubble.setMaximumWidth(600)

        if self.is_user:
            bubble.setStyleSheet("""
                background-color: #10a37f; color: white;
                border-radius: 18px; padding: 12px 16px; margin: 4px;
            """)
        else:
            bubble.setStyleSheet("""
                background-color: #f1f3f4; color: #333333;
                border-radius: 18px; padding: 12px 16px; margin: 4px;
                border: 1px solid #e0e0e0;
            """)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(8, 8, 8, 8)

        text_without_code, code_blocks = self._extract_and_replace_code_blocks(self.message)
        html_content = self._markdown_to_html(text_without_code)
        
        parts = html_content.split('__CODE_BLOCK_')
        
        if parts[0].strip():
            message_label = QLabel()
            message_label.setWordWrap(True)
            message_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            message_label.setTextFormat(Qt.RichText)
            message_label.setText(parts[0])
            base_color = "white" if self.is_user else "#333333"
            message_label.setStyleSheet(f"""
                font-size: 20pt; color: {base_color};
                selection-background-color: rgba(0, 123, 255, 0.3);
            """)
            bubble_layout.addWidget(message_label)
        
        for i, part in enumerate(parts[1:], 0):
            if i < len(code_blocks):
                code_text, lang = code_blocks[i]
                code_widget = CodeBlock(code_text, lang)
                bubble_layout.addWidget(code_widget)
            
            remaining_text = part[part.find('__') + 2:] if '__' in part else part
            if remaining_text.strip():
                message_label = QLabel()
                message_label.setWordWrap(True)
                message_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
                message_label.setTextFormat(Qt.RichText)
                message_label.setText(remaining_text)
                base_color = "white" if self.is_user else "#333333"
                message_label.setStyleSheet(f"""
                    font-size: 20pt; color: {base_color};
                    selection-background-color: rgba(0, 123, 255, 0.3);
                """)
                bubble_layout.addWidget(message_label)

        main_layout.addWidget(bubble)

        if not self.is_user:
            main_layout.addStretch()

    def update_font_size(self, font_size: int):
        labels = self.findChildren(QLabel)
        base_color = "white" if self.is_user else "#333333"
        for label in labels:
            if label.text() in ["CODE"] or label.text().isupper():
                continue
            label.setStyleSheet(f"""
                font-size: {font_size}pt;
                color: {base_color};
                selection-background-color: rgba(0, 123, 255, 0.3);
            """)

class ThinkingBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.dots = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_dots)
        # We'll get this constant from the main app later
        self.timer.start(100) # THINK_INTERVAL_MS

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        bubble = QFrame()
        bubble.setMaximumWidth(400)
        bubble.setStyleSheet("""
            background-color: #f1f3f4;
            border-radius: 18px;
            padding: 12px 16px;
            margin: 4px;
            border: 1px solid #e0e0e0;
        """)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(8, 8, 8, 8)
        self.thinking_label = QLabel("GPT is thinking...")
        self.thinking_label.setStyleSheet("color: #666; font-size: 20pt;")
        bubble_layout.addWidget(self.thinking_label)
        main_layout.addWidget(bubble)
        main_layout.addStretch()

    def _update_dots(self) -> None:
        self.dots = (self.dots + 1) % 4
        dots_str = "." * self.dots
        self.thinking_label.setText(f"GPT is thinking{dots_str}")

    def stop_animation(self) -> None:
        self.timer.stop()