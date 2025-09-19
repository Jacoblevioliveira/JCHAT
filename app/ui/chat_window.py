import time
import json
import logging
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLineEdit, 
    QPushButton, QFrame, QDialog, QMenuBar, QLabel
)

from ..data_logger import data_logger, log_message, log_ab_trial, export_data, log_survey_responses
from ..feature_flags import FeatureFlag, enabled_features, feature_settings, get_scripted_convo
from app.app_helpers import is_enabled
from ..api_helpers import ChatThread
from ..constants import APP_TITLE
from .widgets import MessageBubble, ThinkingBubble
from .ab_testing_dialog import ABTestingDialog
from .survey_dialog import SurveyDialog
from .ConsentDebrief import DebriefDialog

log = logging.getLogger(__name__)

class ChatWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.experiment_plan = None
        self.current_block_index = -1
        self.messages_in_current_block = 0
        self.history: list[dict] = []
        self.count: int = 0
        self.assistant_message_count: int = 0
        self.blocking: bool = False
        self._web_cache: list[dict] = []
        self._must_slow_turn: bool = False
        self._earliest_display_ts: float | None = None
        self.erase_timer: QTimer | None = None
        self.erase_count = 0
        self.auto_end_timer: QTimer | None = None
        self.session_start_time = time.time()
        self._typebuf: str = ""
        self._typeidx: int = 0
        self._typetimer: QTimer | None = None
        self._current_typing_bubble: QWidget | None = None
        self._typing_label = None
        self._current_thinking_bubble: ThinkingBubble | None = None
        ab_thresh = get_setting_value('ab_test_message_threshold', False)
        if ab_thresh is None or ab_thresh < 1:
            ab_thresh = 5
        self.ab_test_threshold = int(ab_thresh)
        self.ab_test_results: list[dict] = []
        self.ab_responses: dict[str, str] | None = None
        self._last_ab_choice: str | None = None
        self.script_index: int = 0
        self._threads: set[QThread] = set()
        self._build_ui()
        self._setup_auto_end_timer()
        self._setup_erase_history_timer()
        self._apply_text_size()
        if is_enabled(FeatureFlag.DYNAMIC_FEATURE_CHANGING):
            self._initialize_blueprint_mode()

    def _setup_erase_history_timer(self) -> None:
        if is_enabled(FeatureFlag.ERASE_HISTORY):
            initial_delay = get_setting_value('erase_history_delay_s', False) or 60
            self.erase_timer = QTimer(self)
            self.erase_timer.timeout.connect(self._handle_erase_timeout)
            self.erase_timer.setSingleShot(True)
            self.erase_timer.start(initial_delay * 1000)

    def _handle_erase_timeout(self) -> None:
        self.clear_data()
        self.erase_count += 1
        repeat_enabled = get_setting_value('erase_history_repeat', False) or False
        if repeat_enabled:
            interval = get_setting_value('erase_history_interval_s', False) or 120
            self.erase_timer = QTimer(self)
            self.erase_timer.timeout.connect(self._handle_erase_timeout)
            self.erase_timer.setSingleShot(True)
            self.erase_timer.start(interval * 1000)

    def _initialize_blueprint_mode(self):
        filename = feature_settings.get('blueprint_filename', 'experiment_blueprint.json')
        blueprint_path = Path(__file__).parent.parent.parent / "data" / "blueprints" / filename
        if not blueprint_path.exists():
            log.error(f"Blueprint file not found: {filename}. Cannot start experiment.")
            self.add_system_message(f"ERROR: Blueprint file '{filename}' not found.")
            return
        try:
            with open(blueprint_path, 'r', encoding='utf-8') as f:
                self.experiment_plan = json.load(f)
            self._start_next_block()
        except Exception as e:
            log.error(f"Failed to load or parse blueprint {filename}: {e}")

    def _start_next_block(self):
        if not self.experiment_plan: return
        self.current_block_index += 1
        if self.current_block_index >= len(self.experiment_plan):
            self.add_system_message("Experiment blueprint complete.")
            self._end_chat()
            return
        current_block = self.experiment_plan[self.current_block_index]
        self.messages_in_current_block = 0
        self._apply_block_config(current_block)

    def _slowdown_permanent_active(self, now_s: float) -> bool:
        if not is_enabled(FeatureFlag.SLOWDOWN):
            return False
        perm_enabled = get_setting_value('slowdown_permanent_after_enabled', False) or False
        if not perm_enabled:
            return False
        threshold_s = get_setting_value('slowdown_permanent_after_s', False) or 600
        elapsed = now_s - self.session_start_time
        return elapsed >= threshold_s

    def _in_slow_window(self, send_ts: float) -> bool:
        if not is_enabled(FeatureFlag.SLOWDOWN):
            return False
        normal_cycle_length = get_setting_value('slowdown_period_s', False) or 100
        slow_window_length = get_setting_value('slowdown_window_s', False) or 20
        normal_cycle_length = max(1, int(normal_cycle_length))
        slow_window_length = max(0, int(slow_window_length))
        if slow_window_length <= 0:
            return False
        elapsed = send_ts - self.session_start_time
        total_period = normal_cycle_length + slow_window_length
        position_in_total_period = elapsed % total_period
        return position_in_total_period >= normal_cycle_length

    def _apply_block_config(self, block_data: dict):
        log.info(f"Applying config for block: {block_data.get('name')}")
        for flag in FeatureFlag:
            enabled_features[flag] = False
        active_features = block_data.get("features", {})
        for feature_name, is_active in active_features.items():
            try:
                flag = FeatureFlag[feature_name]
                enabled_features[flag] = is_active
            except KeyError:
                log.warning(f"Blueprint contains unknown feature: {feature_name}")
        block_settings = block_data.get("settings", {})
        feature_settings.update(block_settings)
        self._apply_text_size()
        self._setup_erase_history_timer()
        block_name = block_data.get("name", "Chat")
        self.setWindowTitle(block_name)
        log.info(f"Chat title changed to: {block_name}")

    def _prepare_turn_slowdown(self, send_ts: float) -> None:
        if not is_enabled(FeatureFlag.SLOWDOWN):
            self._must_slow_turn = False
            self._earliest_display_ts = None
            return
        perm_active = self._slowdown_permanent_active(send_ts)
        cyclic_active = self._in_slow_window(send_ts)
        must = perm_active or cyclic_active
        self._must_slow_turn = must
        if must:
            min_delay = get_setting_value('slowdown_min_delay_s', False) or 4
            self._earliest_display_ts = send_ts + float(min_delay)
        else:
            self._earliest_display_ts = None

    def _maybe_delay_then(self, fn) -> None:
        if self._must_slow_turn and self._earliest_display_ts is not None:
            now = time.time()
            remaining = max(0.0, self._earliest_display_ts - now)
            if remaining > 0:
                QTimer.singleShot(int(remaining * 1000), fn)
                return
        fn()

    def _setup_auto_end_timer(self) -> None:
        if is_enabled(FeatureFlag.AUTO_END_AFTER_T_MIN):
            minutes = get_setting_value('auto_end_minutes', False) or 5
            self.auto_end_timer = QTimer(self)
            self.auto_end_timer.timeout.connect(lambda: self._auto_end_chat("time limit"))
            self.auto_end_timer.setSingleShot(True)
            self.auto_end_timer.start(minutes * 60 * 1000)

    def _apply_text_size(self) -> None:
        if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER):
            font_size = get_setting_value('text_size', False) or 20
            self.custom_font_size = font_size
            self._apply_font_size_to_messages()

    def _apply_font_size_to_messages(self, font_size: int = None):
        if font_size is None:
            font_size = getattr(self, 'custom_font_size', 20)
        for i in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, MessageBubble):
                    widget.update_font_size(font_size)
                else:
                    labels = widget.findChildren(QLabel)
                    for label in labels:
                        if "thinking" in label.text().lower():
                            label.setStyleSheet(f"color: #666; font-size: {font_size}pt;")
                        elif label.styleSheet() and "italic" in label.styleSheet():
                            system_font_size = font_size if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER) and hasattr(self, 'custom_font_size') else max(11, int(font_size * 0.75))
                            label.setStyleSheet(f"color: #666; font-style: italic; font-size: {system_font_size}pt; padding: 8px; background-color: rgba(0,0,0,0.05); border-radius: 12px;")

    def _auto_end_chat(self, reason: str) -> None:
        self.add_system_message(f"Chat ended automatically: {reason} reached.")
        QTimer.singleShot(2000, self._end_chat)

    def _check_auto_end_conditions(self) -> bool:
        if is_enabled(FeatureFlag.AUTO_END_AFTER_N_MSGS):
            max_messages = get_setting_value('auto_end_messages', False) or 10
            if self.assistant_message_count >= max_messages:
                self._auto_end_chat("message limit")
                return True
        return False

    def _should_hide_end_button(self) -> bool:
        return (is_enabled(FeatureFlag.AUTO_END_AFTER_N_MSGS) or is_enabled(FeatureFlag.AUTO_END_AFTER_T_MIN))

    def _build_ui(self) -> None:
        if is_enabled(FeatureFlag.CUSTOM_CHAT_TITLE):
            title = feature_settings.get('custom_chat_title', APP_TITLE)
            self.setWindowTitle(title)
        else:
            self.setWindowTitle(APP_TITLE)

        self.resize(800, 600)
        main_layout = QVBoxLayout(self)

        self.menu_bar = QMenuBar()
        actions_menu = self.menu_bar.addMenu("Researcher Actions")
        change_title_action = actions_menu.addAction("Change Chat Title...")
        change_title_action.triggered.connect(self._prompt_for_new_title)
        transition_action = actions_menu.addAction("Show Test Transition")
        transition_action.triggered.connect(self._show_test_transition)
        main_layout.addWidget(self.menu_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("QScrollArea { background: white; border: none; border-radius: 8px; }")

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 10, 0, 10)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        main_layout.addWidget(self.scroll_area, 1)

        self._build_input(main_layout)

    def _build_input(self, parent: QVBoxLayout) -> None:
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit(placeholderText="Type your message...")
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton()
        icon = QIcon.fromTheme("send")
        if icon.isNull():
            self.send_button.setText("Send")
        else:
            self.send_button.setIcon(icon)
        self.send_button.setFixedWidth(60)
        input_layout.addWidget(self.send_button)

        self.search_button = QPushButton("Search Web")
        self.search_button.setFixedWidth(100)
        self.search_button.clicked.connect(self.send_with_web_search)
        self.search_button.setVisible(is_enabled(FeatureFlag.WEB_SEARCH))
        input_layout.addWidget(self.search_button)

        self.end_button = QPushButton("End & Save")
        self.end_button.setFixedWidth(110)
        self.end_button.clicked.connect(self._end_chat)
        self.end_button.setVisible(not self._should_hide_end_button())
        input_layout.addWidget(self.end_button)

        parent.addLayout(input_layout)
        self.send_button.clicked.connect(self.send_message)
        self.input_field.returnPressed.connect(self.send_message)

    def add_message(self, message: str, is_user: bool = True) -> None:
        bubble = MessageBubble(message, is_user)
        if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER) and hasattr(self, 'custom_font_size'):
            bubble.update_font_size(self.custom_font_size)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)
        
    def add_system_message(self, message: str) -> None:
        system_widget = QWidget()
        system_layout = QHBoxLayout(system_widget)
        system_layout.setContentsMargins(10, 5, 10, 5)
        system_label = QLabel(message)
        system_label.setAlignment(Qt.AlignCenter)
        system_label.setStyleSheet(
            "color: #666; font-style: italic; font-size: 11pt; padding: 8px;"
            "background-color: rgba(0,0,0,0.05); border-radius: 12px;"
        )
        system_layout.addStretch()
        system_layout.addWidget(system_label)
        system_layout.addStretch()
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, system_widget)
        QTimer.singleShot(10, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def change_chat_title(self, new_title: str) -> None:
        self.setWindowTitle(new_title)
        log.info(f"Chat title changed to: {new_title}")
        self.add_system_message(f"AI assistant has been changed to: {new_title}")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.input_field.setFocus()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        h = self.height()
        input_font_size = max(12, int(h * 0.02))
        self.input_field.setStyleSheet(f"font-size:{input_font_size}pt;")
        if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER) and hasattr(self, 'custom_font_size'):
            message_font_size = self.custom_font_size
        else:
            message_font_size = max(20, int(h * 0.025))
        self._apply_font_size_to_messages(message_font_size)

    def clear_data(self) -> None:
        while self.messages_layout.count() > 1:
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.history.clear()
        self.add_system_message("Chat history erased.")

    def _start_and_track(self, thread: QThread) -> None:
        self._threads.add(thread)
        def _on_finished():
            self._threads.discard(thread)
        thread.finished.connect(_on_finished)
        thread.start()

    def send_message(self) -> None:
        txt = self.input_field.text().strip()
        if not txt:
            return

        log_message("user", txt)
        self.add_message(txt, is_user=True)
        self.history.append({"role": "user", "content": txt})
        
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        if hasattr(self, "search_button") and self.search_button is not None:
            self.search_button.setEnabled(False)

        sent_ts = time.time()
        if is_enabled(FeatureFlag.DELAY_BEFORE_SEND):
            delay_seconds = get_setting_value('delay_seconds', False) or 2
            QTimer.singleShot(delay_seconds * 1000, lambda ts=sent_ts: self._send_after_delay(txt, ts))
        else:
            self._send_after_delay(txt, sent_ts)

    def _send_after_delay(self, txt: str, sent_ts: float) -> None:
        self._prepare_turn_slowdown(sent_ts)
        
        if is_enabled(FeatureFlag.SCRIPTED_RESPONSES):
            script_list = get_scripted_convo()
            if self.script_index < len(script_list):
                current_step = script_list[self.script_index]
                self.script_index += 1
                step_type = current_step.get("type", "normal")
                
                if step_type == "normal":
                    reply = current_step.get("response", "SCRIPT ERROR: Missing 'response' key")
                    if is_enabled(FeatureFlag.THINKING):
                        self._start_thinking()
                    QTimer.singleShot(1000, lambda: self._on_response(reply))
                    return
                elif step_type == "ab_test":
                    reply_a = current_step.get("response_a", "SCRIPT ERROR: Missing 'response_a'")
                    reply_b = current_step.get("response_b", "SCRIPT ERROR: Missing 'response_b'")
                    if is_enabled(FeatureFlag.THINKING):
                        self._start_thinking()
                    self._handle_scripted_ab_turn(reply_a, reply_b)
                    return

        is_ab_turn = is_enabled(FeatureFlag.AB_TESTING) and (self.count + 1) % self.ab_test_threshold == 0

        if is_ab_turn and is_enabled(FeatureFlag.AB_UI_ALT):
            if is_enabled(FeatureFlag.THINKING) and not self._current_thinking_bubble:
                self._start_thinking()
            self._start_ab_ui_alt_workflow(txt)
            return
        elif is_ab_turn and is_enabled(FeatureFlag.AB_UI_TEST):
            if is_enabled(FeatureFlag.THINKING) and not self._current_thinking_bubble:
                self._start_thinking()
            self.ui_thread = ChatThread(self.history, txt, use_features=True)
            self.ui_thread.result_ready.connect(self._on_ui_ab_response)
            self.ui_thread.error.connect(self._on_error)
            self._start_and_track(self.ui_thread)
            return
        elif is_ab_turn:
            if is_enabled(FeatureFlag.THINKING) and not self._current_thinking_bubble:
                self._start_thinking()

            self.ab_responses = {'A': None, 'B': None}
            self.ab_responses_ready = 0

            option_b_features = {flag: False for flag in FeatureFlag} 
            content_feature_mappings = [
                ('ab_lie_b', FeatureFlag.LIE), ('ab_rude_tone_b', FeatureFlag.RUDE_TONE),
                ('ab_kind_tone_b', FeatureFlag.KIND_TONE), ('ab_advice_only_b', FeatureFlag.ADVICE_ONLY),
                ('ab_no_memory_b', FeatureFlag.NO_MEMORY), ('ab_persona_b', FeatureFlag.PERSONA),
                ('ab_mirror_b', FeatureFlag.MIRROR), ('ab_anti_mirror_b', FeatureFlag.ANTI_MIRROR),
                ('ab_grammar_errors_b', FeatureFlag.GRAMMAR_ERRORS), ('ab_positive_feedback_b', FeatureFlag.POSITIVE_FEEDBACK),
                ('ab_critical_feedback_b', FeatureFlag.CRITICAL_FEEDBACK), ('ab_neutral_feedback_b', FeatureFlag.NEUTRAL_FEEDBACK),
                ('ab_hedging_b', FeatureFlag.HEDGING_LANGUAGE)
            ]
            for setting_key, flag in content_feature_mappings:
                if feature_settings.get(setting_key, False):
                    option_b_features[flag] = True
                    if flag == FeatureFlag.RUDE_TONE: option_b_features[FeatureFlag.KIND_TONE] = False
                    elif flag == FeatureFlag.KIND_TONE: option_b_features[FeatureFlag.RUDE_TONE] = False
                    elif flag == FeatureFlag.MIRROR: option_b_features[FeatureFlag.ANTI_MIRROR] = False
                    elif flag == FeatureFlag.ANTI_MIRROR: option_b_features[FeatureFlag.MIRROR] = False
                    elif flag in [FeatureFlag.POSITIVE_FEEDBACK, FeatureFlag.CRITICAL_FEEDBACK, FeatureFlag.NEUTRAL_FEEDBACK]:
                        for feedback_flag in [FeatureFlag.POSITIVE_FEEDBACK, FeatureFlag.CRITICAL_FEEDBACK, FeatureFlag.NEUTRAL_FEEDBACK]:
                            if feedback_flag != flag:
                                option_b_features[feedback_flag] = False
            
            ui_feature_mappings = [
                ('ab_streaming_b', FeatureFlag.STREAMING), ('ab_text_size_changer_b', FeatureFlag.TEXT_SIZE_CHANGER),
                ('ab_typewriter_b', FeatureFlag.TYPEWRITER), ('ab_thinking_b', FeatureFlag.THINKING)
            ]
            for setting_key, flag in ui_feature_mappings:
                if feature_settings.get(setting_key, False):
                    option_b_features[flag] = True

            self.thread_a = ChatThread(self.history, txt, feature_set=enabled_features, is_option_b=False)
            self.thread_b = ChatThread(self.history, txt, feature_set=option_b_features, is_option_b=True)
            self.thread_a.result_ready.connect(lambda reply: self._on_ab_response(reply, 'A'))
            self.thread_b.result_ready.connect(lambda reply: self._on_ab_response(reply, 'B'))
            self.thread_a.error.connect(self._on_error)
            self.thread_b.error.connect(self._on_error)
            self._start_and_track(self.thread_a)
            self._start_and_track(self.thread_b)
            return

        if is_enabled(FeatureFlag.THINKING) and not self._current_thinking_bubble:
            self._start_thinking()
        self.thread = ChatThread(self.history, txt, use_features=True)
        self.thread.result_ready.connect(self._on_response)
        self.thread.error.connect(self._on_error)
        self.thread.chunk_ready.connect(self._on_chunk_ready)
        self._start_and_track(self.thread)

    def _start_thinking(self) -> None:
        self._current_thinking_bubble = ThinkingBubble()
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self._current_thinking_bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)

    def _on_chunk_ready(self, chunk: str) -> None:
        if not hasattr(self, '_chunk_buffer'):
            self._chunk_buffer = ""
        self._chunk_buffer += chunk
        if '\n' in self._chunk_buffer:
            self._release_buffered_chunk()

    def _release_buffered_chunk(self) -> None:
        if not hasattr(self, '_chunk_buffer') or not self._chunk_buffer.strip():
            return
        if not hasattr(self, '_current_streaming_bubble') or self._current_streaming_bubble is None:
            self._create_streaming_bubble()
        if not hasattr(self, '_streaming_text'):
            self._streaming_text = ""
        self._streaming_text += self._chunk_buffer
        if hasattr(self, '_streaming_label') and self._streaming_label:
            self._streaming_label.setText(self._streaming_text)
        self._chunk_buffer = ""
        self._scroll_to_bottom()
        
    def _create_streaming_bubble(self) -> None:
        self._current_streaming_bubble = QWidget()
        bubble_layout = QHBoxLayout(self._current_streaming_bubble)
        bubble_layout.setContentsMargins(10, 5, 10, 5)
        
        bubble = QFrame()
        bubble.setMaximumWidth(600)
        bubble.setStyleSheet("""
            background-color: #f1f3f4; color: #333333; border-radius: 18px;
            padding: 12px 16px; margin: 4px; border: 1px solid #e0e0e0;
        """)
        
        bubble_inner_layout = QVBoxLayout(bubble)
        bubble_inner_layout.setContentsMargins(8, 8, 8, 8)
        
        self._streaming_label = QLabel("")
        self._streaming_label.setWordWrap(True)
        self._streaming_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self._streaming_label.setStyleSheet("font-size: 20pt; color: #333333;")
        
        bubble_inner_layout.addWidget(self._streaming_label)
        bubble_layout.addWidget(bubble)
        bubble_layout.addStretch()
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self._current_streaming_bubble)
        self._streaming_text = ""

    def _on_response(self, reply: str) -> None:
        def proceed():
            if self._current_thinking_bubble:
                self._current_thinking_bubble.stop_animation()
                self.messages_layout.removeWidget(self._current_thinking_bubble)
                self._current_thinking_bubble.deleteLater()
                self._current_thinking_bubble = None
            self._display_response(reply)
        self._maybe_delay_then(proceed)

    def _on_ab_response(self, reply: str, version: str) -> None:
        self.ab_responses[version] = reply
        self.ab_responses_ready += 1
        
        if self.ab_responses_ready == 2:
            def proceed():
                if self._current_thinking_bubble:
                    self._current_thinking_bubble.stop_animation()
                    self.messages_layout.removeWidget(self._current_thinking_bubble)
                    self._current_thinking_bubble.deleteLater()
                    self._current_thinking_bubble = None
                self._show_ab_dialog(self.ab_responses['A'], self.ab_responses['B'])
            self._maybe_delay_then(proceed)

    def _show_ab_dialog(self, content_a: str, content_b: str) -> None:
        dialog = ABTestingDialog(response_a=content_a, response_b=content_b, parent=self)
        
        if dialog.exec() == QDialog.Accepted:
            sel = dialog.selected_version or 'A'
            test_type = "ui_test" if content_a == content_b else "content_test"

            original_message = ""
            for msg in reversed(self.history):
                if msg.get("role") == "user":
                    original_message = msg.get("content", "")
                    break

            log_ab_trial(
                message_content=original_message,
                option_a=content_a,
                option_b=content_b,
                selected=sel,
                latency_ms=dialog.selection_latency,
                test_type=test_type
            )

            self._last_ab_choice = sel
            self.add_system_message(f"You selected Option {sel}")

            if sel == 'A':
                self._display_response(dialog.selected_response or content_a)
            else:
                self.add_message(dialog.selected_response or content_b, is_user=False)
                self._finish_response(dialog.selected_response or content_b)
        else:
            self._display_response(content_a)
        
    def _display_response(self, reply: str, is_option_b: bool = False) -> None:
        if is_enabled(FeatureFlag.STREAMING) and hasattr(self, '_current_streaming_bubble') and self._current_streaming_bubble is not None:
            self._current_streaming_bubble = None
            self._finish_response(reply)
            return
        
        if is_enabled(FeatureFlag.TYPEWRITER):
            if '```' in reply:
                self.add_message(reply, is_user=False)
                self._finish_response(reply)
            else:
                self._typebuf = reply
                self._typeidx = 0
                
                self._current_typing_bubble = QWidget()
                bubble_layout = QHBoxLayout(self._current_typing_bubble)
                bubble_layout.setContentsMargins(10, 5, 10, 5)
                
                bubble = QFrame()
                bubble.setMaximumWidth(600)
                bubble.setStyleSheet("""
                    background-color: #f1f3f4; color: #333333; border-radius: 18px;
                    padding: 12px 16px; margin: 4px; border: 1px solid #e0e0e0;
                """)
                
                bubble_inner_layout = QVBoxLayout(bubble)
                bubble_inner_layout.setContentsMargins(8, 8, 8, 8)
                
                self._typing_label = QLabel("")
                self._typing_label.setWordWrap(True)
                self._typing_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
                self._typing_label.setTextFormat(Qt.RichText)
                self._typing_label.setStyleSheet("font-size: 20pt; color: #333333;")
                
                bubble_inner_layout.addWidget(self._typing_label)
                bubble_layout.addWidget(bubble)
                bubble_layout.addStretch()
                
                self.messages_layout.insertWidget(self.messages_layout.count() - 1, self._current_typing_bubble)
                
                typewriter_speed = get_setting_value('typewriter_speed_ms', is_option_b) or 20
                
                self._typetimer = QTimer(self)
                self._typetimer.timeout.connect(self._type_step)
                self._typetimer.start(typewriter_speed)
        else:
            self.add_message(reply, is_user=False)
            self._finish_response(reply)

    def _type_step(self) -> None:
        if self._typeidx < len(self._typebuf):
            current_text = self._typebuf[: self._typeidx + 1]
            
            if self._typing_label:
                temp_bubble = MessageBubble("", is_user=False)
                html_content = temp_bubble._markdown_to_html(current_text)
                self._typing_label.setText(html_content)
            
            self._typeidx += 1
            self._scroll_to_bottom()
        else:
            if self._typetimer:
                self._typetimer.stop()
                self._typetimer = None
            
            if self._current_typing_bubble:
                self.messages_layout.removeWidget(self._current_typing_bubble)
                self._current_typing_bubble.deleteLater()
                self._current_typing_bubble = None
                self._typing_label = None
            
            self.add_message(self._typebuf, is_user=False)
            self._finish_response(self._typebuf)

    def _show_survey(self):
        filename = feature_settings.get('survey_filename', 'survey.json')
        survey_path = Path(__file__).parent.parent.parent / "data" / "blueprints" / filename

        if not survey_path.exists():
            log.warning(f"Survey file not found: {filename}. Skipping survey.")
            return

        try:
            with open(survey_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            
            dialog = SurveyDialog(questions, self)
            if dialog.exec() == QDialog.Accepted and dialog.results:
                log_survey_responses(self.count, dialog.results)

        except Exception as e:
            log.error(f"Failed to load or process survey {filename}: {e}")

    def _finish_response(self, reply: str) -> None:
        ab_choice = self._last_ab_choice
        is_ab_message = bool(ab_choice)
        log_message("assistant", reply, had_ab_test=is_ab_message, ab_selection=ab_choice)
        
        self._last_ab_choice = None
        self.ab_responses = None
        
        self.history.append({"role": "assistant", "content": reply})
        self.count += 1
        self.assistant_message_count += 1

        if self.experiment_plan:
            self.messages_in_current_block += 1
            current_block = self.experiment_plan[self.current_block_index]
            duration = current_block.get("duration_messages", 10)
            
            if self.messages_in_current_block >= duration:
                self._start_next_block()
            
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
            self.send_button.setEnabled(True)
            if hasattr(self, "search_button") and self.search_button is not None:
                self.search_button.setEnabled(True)
            return

        if is_enabled(FeatureFlag.INTER_TRIAL_SURVEY):
            trigger_count = feature_settings.get('survey_trigger_count', 5)
            if self.assistant_message_count > 0 and self.assistant_message_count % trigger_count == 0:
                QTimer.singleShot(1000, self._show_survey)

        self._must_slow_turn = False
        self._earliest_display_ts = None

        if self._check_auto_end_conditions():
            return

        if is_enabled(FeatureFlag.BLOCK_MSGS):
            message_threshold = get_setting_value('block_message_count', False) or 5
            repeat_blocking = get_setting_value('block_repeat', False)
            if repeat_blocking is None: repeat_blocking = True

            if repeat_blocking:
                if self.count > 0 and self.count % message_threshold == 0:
                    self._start_block(); return
            else:
                if self.count == message_threshold:
                    self._start_block(); return

        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.send_button.setEnabled(True)
        if hasattr(self, "search_button") and self.search_button is not None:
            self.search_button.setEnabled(True)
    
    def _start_block(self) -> None:
        block_duration = get_setting_value('block_duration_s', False) or 15
        self.blocking = True
        self.add_system_message(f"Blocking for {block_duration}s...")
        self.remaining = block_duration
        
        self.block_timer = QTimer(self)
        self.block_timer.timeout.connect(self._update_countdown)
        self.block_timer.start(1000)
        
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)

    def _update_countdown(self) -> None:
        if self.remaining > 0:
            self.add_system_message(f"{self.remaining}s...")
            self.remaining -= 1
        else:
            self.block_timer.stop()
            self.add_system_message("You may type now.")
            self.blocking = False
            
            self.input_field.setEnabled(True)
            self.send_button.setEnabled(True)
            if hasattr(self, "search_button") and self.search_button is not None:
                self.search_button.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        if self._current_thinking_bubble:
            self._current_thinking_bubble.stop_animation()
            self.messages_layout.removeWidget(self._current_thinking_bubble)
            self._current_thinking_bubble.deleteLater()
            self._current_thinking_bubble = None
        
        self.add_system_message(f"ERROR: {msg}")
        
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        if hasattr(self, "search_button") and self.search_button is not None:
            self.search_button.setEnabled(True)

    def _on_ui_ab_response(self, reply: str) -> None:
        def proceed():
            if self._current_thinking_bubble:
                self._current_thinking_bubble.stop_animation()
                self.messages_layout.removeWidget(self._current_thinking_bubble)
                self._current_thinking_bubble.deleteLater()
                self._current_thinking_bubble = None
            
            dialog = ABTestingDialog(response_a=reply, response_b=reply, parent=self)
            if dialog.exec() == QDialog.Accepted:
                sel = dialog.selected_version or 'A'
                test_type = "ui_test"
                original_message = ""
                for msg in reversed(self.history):
                    if msg.get("role") == "user":
                        original_message = msg.get("content", "")
                        break
                log_ab_trial(
                    message_content=original_message,
                    option_a=reply, option_b=reply, selected=sel,
                    latency_ms=dialog.selection_latency, test_type=test_type
                )
                self._last_ab_choice = sel
                self.add_system_message(f"You selected Option {sel}")
                self.add_message(reply, is_user=False)
                self._finish_response(reply)
            else:
                self.add_message(reply, is_user=False)
                self._finish_response(reply)
        
        self._maybe_delay_then(proceed)

    def _start_ab_ui_alt_workflow(self, prompt: str) -> None:
        self.thread_a = ChatThread(self.history, prompt, use_features=True)
        self.thread_a.result_ready.connect(self._on_base_response_for_alt_ui)
        self.thread_a.error.connect(self._on_error)
        self._start_and_track(self.thread_a)

    def _on_base_response_for_alt_ui(self, base_reply: str) -> None:
        rephrase_prompt = (
            "Please paraphrase the following text. Maintain the core information, "
            "tone, and approximate length, but use different wording and sentence structure. "
            "Do not add any commentary before or after the rephrased text. Just provide the rephrased text directly."
            f"\n\nORIGINAL TEXT:\n---\n{base_reply}"
        )
        self.thread_b = ChatThread(history=[], prompt=rephrase_prompt, use_features=False)
        self.thread_b.result_ready.connect(
            lambda rephrased_reply: self._on_rephrased_response_for_alt_ui(base_reply, rephrased_reply)
        )
        self.thread_b.error.connect(self._on_error)
        self._start_and_track(self.thread_b)

    def _on_rephrased_response_for_alt_ui(self, base_reply: str, rephrased_reply: str) -> None:
        def proceed():
            if self._current_thinking_bubble:
                self._current_thinking_bubble.stop_animation()
                self.messages_layout.removeWidget(self._current_thinking_bubble)
                self._current_thinking_bubble.deleteLater()
                self._current_thinking_bubble = None
            self._show_ab_dialog(base_reply, rephrased_reply)
        self._maybe_delay_then(proceed)

    def _handle_scripted_ab_turn(self, reply_a: str, reply_b: str):
        def proceed():
            if self._current_thinking_bubble:
                self._current_thinking_bubble.stop_animation()
                self.messages_layout.removeWidget(self._current_thinking_bubble)
                self._current_thinking_bubble.deleteLater()
                self._current_thinking_bubble = None
            self._show_ab_dialog(reply_a, reply_b)
        self._maybe_delay_then(proceed)

    def send_with_web_search(self) -> None:
        txt = self.input_field.text().strip()
        if not txt:
            return

        log_message("user", txt)
        self.add_message(txt, is_user=True)
        self.history.append({"role": "user", "content": txt})
        
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.search_button.setEnabled(False)

        sent_ts = time.time()
        if is_enabled(FeatureFlag.DELAY_BEFORE_SEND):
            delay_seconds = get_setting_value('delay_seconds', False) or 2
            self.add_system_message(f"Processing web search... ({delay_seconds}s delay)")
            QTimer.singleShot(delay_seconds * 1000, lambda ts=sent_ts: self._web_search_after_delay(txt, ts))
        else:
            self._web_search_after_delay(txt, sent_ts)

    def _web_search_after_delay(self, txt: str, sent_ts: float) -> None:
        self._prepare_turn_slowdown(sent_ts)
        if is_enabled(FeatureFlag.THINKING):
            self._start_thinking()

        web_thread = ChatThread(self.history, txt, use_features=True, force_web_search=True)
        web_thread.result_ready.connect(self._on_response)
        web_thread.error.connect(self._on_error)
        self._start_and_track(web_thread)

    def _end_chat(self) -> None:
        try:
            data_logger.mark_session_end()
        except Exception:
            pass
        try:
            export_data()
            self.add_system_message("Data exported. Thank you for participating.")
        except Exception as e:
            self.add_system_message(f"Export error: {e}")

        dlg = DebriefDialog(self)
        dlg.exec()

        for thr in list(self._threads):
            try:
                if thr.isRunning():
                    thr.quit()
                    thr.wait(2000)
            except Exception:
                pass
        self.close()

    def closeEvent(self, event) -> None:
        self._cleanup_timers()
        super().closeEvent(event)

    def _cleanup_timers(self) -> None:
        if hasattr(self, '_typetimer') and self._typetimer:
            self._typetimer.stop()
            self._typetimer = None
        if hasattr(self, 'auto_end_timer') and self.auto_end_timer:
            self.auto_end_timer.stop()
            self.auto_end_timer = None
        if hasattr(self, 'block_timer') and self.block_timer:
            self.block_timer.stop()
            self.block_timer = None
        if hasattr(self, '_current_thinking_bubble') and self._current_thinking_bubble:
            self._current_thinking_bubble.stop_animation()
            self._current_thinking_bubble = None
        if hasattr(self, 'erase_timer') and self.erase_timer:
            self.erase_timer.stop()
            self.erase_timer = None