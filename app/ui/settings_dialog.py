from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QScrollArea, QWidget, QGridLayout, QLabel,
    QDialogButtonBox, QFrame, QSlider, QCheckBox, QLineEdit, QMessageBox,
    QSizePolicy, QHBoxLayout, QListWidget, QPushButton, QComboBox, QFileDialog
)

from app.helpers import is_enabled
from app.feature_flags import FeatureFlag, feature_settings
from app.ui.ui_components import create_modern_slider, create_modern_checkbox
from app.ui.script_editor import ScriptEditorDialog
from app.ui.survey_builder import SurveyBuilderDialog
from app.ui.experiment_designer import ExperimentDesignerDialog

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feature Settings")
        self.resize(600, 700)
        self.ab_setting_widgets = {}
        
        self._setup_ui()
        self._load_all_settings()

        if hasattr(self, 'script_status_label'):
            self._verify_script_file(show_success_popup=False)
        if hasattr(self, 'survey_filename_input'):
            self._verify_survey_file(show_success_popup=False)
        if hasattr(self, 'blueprint_filename_input'):
            self._verify_blueprint_file(show_success_popup=False)

    def _load_all_settings(self):
        if hasattr(self, 'text_size_spin'): self.text_size_spin.setValue(feature_settings.get('text_size', 20))
        if hasattr(self, 'delay_spin'): self.delay_spin.setValue(feature_settings.get('delay_seconds', 2))
        if hasattr(self, 'messages_spin'): self.messages_spin.setValue(feature_settings.get('auto_end_messages', 10))
        if hasattr(self, 'minutes_spin'): self.minutes_spin.setValue(feature_settings.get('auto_end_minutes', 5))
        if hasattr(self, 'blueprint_filename_input'): self.blueprint_filename_input.setText(feature_settings.get('blueprint_filename', 'experiment_blueprint.json'))
        if hasattr(self, 'sd_period'): self.sd_period.setValue(feature_settings.get('slowdown_period_s', 100))
        if hasattr(self, 'sd_window'): self.sd_window.setValue(feature_settings.get('slowdown_window_s', 20))
        if hasattr(self, 'sd_min'): self.sd_min.setValue(feature_settings.get('slowdown_min_delay_s', 4))
        if hasattr(self, 'sd_perm_en'): self.sd_perm_en.setChecked(feature_settings.get('slowdown_permanent_after_enabled', False))
        if hasattr(self, 'sd_perm_s'): self.sd_perm_s.setValue(feature_settings.get('slowdown_permanent_after_s', 600))
        if hasattr(self, 'erase_delay'): self.erase_delay.setValue(feature_settings.get('erase_history_delay_s', 60))
        if hasattr(self, 'erase_repeat'): self.erase_repeat.setChecked(feature_settings.get('erase_history_repeat', False))
        if hasattr(self, 'erase_interval'): self.erase_interval.setValue(feature_settings.get('erase_history_interval_s', 120))
        if hasattr(self, 'block_msg_count'): self.block_msg_count.setValue(feature_settings.get('block_message_count', 5))
        if hasattr(self, 'block_duration'): self.block_duration.setValue(feature_settings.get('block_duration_s', 15))
        if hasattr(self, 'block_repeat'): self.block_repeat.setChecked(feature_settings.get('block_repeat', True))
        if hasattr(self, 'typewriter_speed'): self.typewriter_speed.setValue(feature_settings.get('typewriter_speed_ms', 20))
        if hasattr(self, 'ab_threshold_spin'): self.ab_threshold_spin.setValue(feature_settings.get('ab_test_message_threshold', 5))
        if hasattr(self, 'chat_title_input'): self.chat_title_input.setText(feature_settings.get('custom_chat_title', 'ChatGPT'))
        if hasattr(self, 'survey_trigger_spin'): self.survey_trigger_spin.setValue(feature_settings.get('survey_trigger_count', 5))
        if hasattr(self, 'survey_filename_input'): self.survey_filename_input.setText(feature_settings.get('survey_filename', 'survey.json'))
        if hasattr(self, 'mc_trigger_spin'):
            self.mc_trigger_spin.setValue(feature_settings.get('mc_trigger_count', 5))
        if hasattr(self, 'mc_changes_list'):
            self.mc_changes_list.clear()
            changes = feature_settings.get('mc_changes', [])
            for change in changes:
                state = "Enable" if change.get("enabled") else "Disable"
                feature_name = change.get("feature")
                self.mc_changes_list.addItem(f"{state} {feature_name}")
        self._load_ab_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("⚙️ Feature Configuration")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold; margin-bottom: 20px; color: #2c3e50; padding: 15px; border-radius: 10px; background-color: #f8f9fa; border: 2px solid #e9ecef;")
        layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; border-radius: 12px; background: white; } QScrollBar:vertical { background: #f1f3f4; width: 12px; border-radius: 6px; margin: 0; } QScrollBar::handle:vertical { background: #c1c8e4; border-radius: 6px; min-height: 20px; } QScrollBar::handle:vertical:hover { background: #5b73c4; }")
        scroll_widget = QWidget()
        grid = QGridLayout(scroll_widget)
        grid.setSpacing(15)
        row = self._add_all_modern_sections(grid, 0)
        scroll.setWidget(scroll_widget)
        if row > 0:
            layout.addWidget(scroll)
        else:
            no_settings_label = QLabel("No configurable settings for selected features.")
            no_settings_label.setAlignment(Qt.AlignCenter)
            no_settings_label.setStyleSheet("color: #666; font-style: italic; font-size: 14pt; padding: 40px;")
            layout.addWidget(no_settings_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet("QPushButton { background: #667eea; color: white; border: none; border-radius: 8px; padding: 12px 24px; font-weight: bold; min-width: 80px; font-size: 12pt; } QPushButton:hover { background: #5a67d8; } QPushButton:pressed { background: #4c51bf; }")
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_ab_settings(self):
        ab_settings_map = {
            'text_size_b': ('text_size_b', 24), 'delay_seconds_b': ('delay_seconds_b', 3),
            'auto_end_messages_b': ('auto_end_messages_b', 15), 'auto_end_minutes_b': ('auto_end_minutes_b', 8),
            'typewriter_speed_ms_b': ('typewriter_speed_ms_b', 50), 'slowdown_period_s_b': ('slowdown_period_s_b', 150),
            'slowdown_window_s_b': ('slowdown_window_s_b', 30), 'slowdown_min_delay_s_b': ('slowdown_min_delay_s_b', 6),
            'slowdown_permanent_after_enabled_b': ('slowdown_permanent_after_enabled_b', True),
            'slowdown_permanent_after_s_b': ('slowdown_permanent_after_s_b', 900), 'erase_history_delay_s_b': ('erase_history_delay_s_b', 90),
            'erase_history_repeat_b': ('erase_history_repeat_b', True), 'erase_history_interval_s_b': ('erase_history_interval_s_b', 180),
            'block_message_count_b': ('block_message_count_b', 8), 'block_duration_s_b': ('block_duration_s_b', 25),
            'block_repeat_b': ('block_repeat_b', False),
        }
        for widget_key, (setting_key, default_val) in ab_settings_map.items():
            if widget_key in self.ab_setting_widgets:
                widget = self.ab_setting_widgets[widget_key]
                value = feature_settings.get(setting_key, default_val)
                if isinstance(widget, QSlider):
                    widget.setValue(value)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(value)

    def _add_all_modern_sections(self, grid, row):
        if is_enabled(FeatureFlag.SLOWDOWN): row = self._add_modern_slowdown_section(grid, row)
        if is_enabled(FeatureFlag.TYPEWRITER): row = self._add_modern_typewriter_section(grid, row)
        if is_enabled(FeatureFlag.ERASE_HISTORY): row = self._add_modern_erase_section(grid, row)
        if is_enabled(FeatureFlag.BLOCK_MSGS): row = self._add_modern_block_section(grid, row)
        row = self._add_modern_basic_settings(grid, row)
        if is_enabled(FeatureFlag.INTER_TRIAL_SURVEY): row = self._add_modern_survey_section(grid, row)
        if is_enabled(FeatureFlag.DYNAMIC_FEATURE_CHANGING): row = self._add_modern_blueprint_section(grid, row)
        if is_enabled(FeatureFlag.AB_TESTING): row = self._add_modern_ab_section(grid, row)
        if is_enabled(FeatureFlag.SCRIPTED_RESPONSES): row = self._add_modern_scripted_section(grid, row)
        return row

    def _add_modern_slowdown_section(self, grid, row):
        title = self._create_modern_section_title("⏱️ Slowdown Configuration", "#e74c3c")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        period_label = QLabel("Cycle Period:")
        period_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        period_container, self.sd_period = create_modern_slider(5, 3600, 100, "s")
        grid.addWidget(period_label, row, 0); grid.addWidget(period_container, row, 1); row += 1
        window_label = QLabel("Slow Window:")
        window_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        window_container, self.sd_window = create_modern_slider(1, 3600, 20, "s")
        grid.addWidget(window_label, row, 0); grid.addWidget(window_container, row, 1); row += 1
        min_delay_label = QLabel("Minimum Delay:")
        min_delay_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        min_delay_container, self.sd_min = create_modern_slider(1, 60, 4, "s")
        grid.addWidget(min_delay_label, row, 0); grid.addWidget(min_delay_container, row, 1); row += 1
        self.sd_perm_en = create_modern_checkbox("Enable permanent slowdown", False)
        grid.addWidget(self.sd_perm_en, row, 0, 1, 2); row += 1
        perm_threshold_label = QLabel("Permanent After:")
        perm_threshold_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        perm_threshold_container, self.sd_perm_s = create_modern_slider(1, 24*3600, 600, "s")
        grid.addWidget(perm_threshold_label, row, 0); grid.addWidget(perm_threshold_container, row, 1); row += 1
        return self._add_section_separator(grid, row)

    def _add_modern_typewriter_section(self, grid, row):
        title = self._create_modern_section_title("⌨️ Typewriter Effect", "#28a745")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        speed_label = QLabel("Typing Speed:")
        speed_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        speed_container, self.typewriter_speed = create_modern_slider(1, 1000, 20, " ms")
        grid.addWidget(speed_label, row, 0); grid.addWidget(speed_container, row, 1); row += 1
        return self._add_section_separator(grid, row)

    def _add_modern_erase_section(self, grid, row):
        title = self._create_modern_section_title("🗑️ Erase History", "#d73502")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        delay_label = QLabel("Initial Delay:")
        delay_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        delay_container, self.erase_delay = create_modern_slider(10, 3600, 60, "s")
        grid.addWidget(delay_label, row, 0); grid.addWidget(delay_container, row, 1); row += 1
        self.erase_repeat = create_modern_checkbox("Repeat erase periodically", False)
        grid.addWidget(self.erase_repeat, row, 0, 1, 2); row += 1
        interval_label = QLabel("Repeat Interval:")
        interval_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        interval_container, self.erase_interval = create_modern_slider(30, 3600, 120, "s")
        grid.addWidget(interval_label, row, 0); grid.addWidget(interval_container, row, 1); row += 1
        return self._add_section_separator(grid, row)

    def _add_modern_block_section(self, grid, row):
        title = self._create_modern_section_title("🚫 Block Messages", "#8e44ad")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        count_label = QLabel("Block After Messages:")
        count_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        count_container, self.block_msg_count = create_modern_slider(1, 100, 5, " msgs")
        grid.addWidget(count_label, row, 0); grid.addWidget(count_container, row, 1); row += 1
        duration_label = QLabel("Block Duration:")
        duration_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        duration_container, self.block_duration = create_modern_slider(5, 300, 15, "s")
        grid.addWidget(duration_label, row, 0); grid.addWidget(duration_container, row, 1); row += 1
        self.block_repeat = create_modern_checkbox("Repeat block every N messages", True)
        grid.addWidget(self.block_repeat, row, 0, 1, 2); row += 1
        return self._add_section_separator(grid, row)

    def _add_modern_basic_settings(self, grid, row):
        basic_features = [
            FeatureFlag.CUSTOM_CHAT_TITLE, FeatureFlag.TEXT_SIZE_CHANGER,
            FeatureFlag.DELAY_BEFORE_SEND, FeatureFlag.AUTO_END_AFTER_N_MSGS,
            FeatureFlag.AUTO_END_AFTER_T_MIN,
        ]
        if not any(is_enabled(f) for f in basic_features):
            return row
        title = self._create_modern_section_title("📝 UI & Session Settings", "#17a2b8")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        if is_enabled(FeatureFlag.CUSTOM_CHAT_TITLE):
            title_label = QLabel("Custom Chat Title:")
            title_label.setStyleSheet("font-weight: 600; color: #4a5568;")
            self.chat_title_input = QLineEdit()
            self.chat_title_input.setPlaceholderText("e.g., AI Assistant Gamma")
            self.chat_title_input.setStyleSheet("padding: 8px; border: 2px solid #e2e8f0; border-radius: 4px;")
            grid.addWidget(title_label, row, 0); grid.addWidget(self.chat_title_input, row, 1); row += 1
        if is_enabled(FeatureFlag.TEXT_SIZE_CHANGER):
            size_label = QLabel("Text Size:")
            size_label.setStyleSheet("font-weight: 600; color: #4a5568;")
            size_container, self.text_size_spin = create_modern_slider(8, 48, 20, "pt")
            grid.addWidget(size_label, row, 0); grid.addWidget(size_container, row, 1); row += 1
        if is_enabled(FeatureFlag.DELAY_BEFORE_SEND):
            delay_label = QLabel("Send Delay:")
            delay_label.setStyleSheet("font-weight: 600; color: #4a5568;")
            delay_container, self.delay_spin = create_modern_slider(1, 30, 2, "s")
            grid.addWidget(delay_label, row, 0); grid.addWidget(delay_container, row, 1); row += 1
        if is_enabled(FeatureFlag.AUTO_END_AFTER_N_MSGS):
            msgs_label = QLabel("Max Messages:")
            msgs_label.setStyleSheet("font-weight: 600; color: #4a5568;")
            msgs_container, self.messages_spin = create_modern_slider(1, 100, 10, " msgs")
            grid.addWidget(msgs_label, row, 0); grid.addWidget(msgs_container, row, 1); row += 1
        if is_enabled(FeatureFlag.AUTO_END_AFTER_T_MIN):
            mins_label = QLabel("Max Minutes:")
            mins_label.setStyleSheet("font-weight: 600; color: #4a5568;")
            mins_container, self.minutes_spin = create_modern_slider(1, 120, 5, " min")
            grid.addWidget(mins_label, row, 0); grid.addWidget(mins_container, row, 1); row += 1
        return self._add_section_separator(grid, row)

    def _add_modern_ab_section(self, grid, row):
        title = self._create_modern_section_title("🧪 A/B Testing - Option B Features", "#17a2b8")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        content_label = QLabel("Content Features:")
        content_label.setStyleSheet("font-weight: bold; color: #666; margin-top: 8px; font-size: 12pt;")
        grid.addWidget(content_label, row, 0, 1, 2); row += 1
        content_features = [
            ('ab_lie', 'Lie'), ('ab_rude_tone', 'Rude Tone'), ('ab_kind_tone', 'Kind Tone'),
            ('ab_advice_only', 'Advice Only'), ('ab_no_memory', 'No Memory'), ('ab_persona', 'Persona'),
            ('ab_mirror', 'Mirror'), ('ab_anti_mirror', 'Anti Mirror'), ('ab_grammar_errors', 'Grammar Errors'),
            ('ab_positive_feedback', 'Positive Feedback'), ('ab_critical_feedback', 'Critical Feedback'),
            ('ab_neutral_feedback', 'Neutral Feedback'), ('ab_hedging', 'Hedging Language'),
        ]
        for i, (attr_name, display_name) in enumerate(content_features):
            checkbox = create_modern_checkbox(display_name, False)
            setattr(self, attr_name, checkbox)
            grid.addWidget(checkbox, row + i // 2, i % 2)
        row += (len(content_features) + 1) // 2
        threshold_label = QLabel("A/B Test Every:")
        threshold_label.setStyleSheet("font-weight: 600; color: #4a5568; margin-top: 10px;")
        threshold_container, self.ab_threshold_spin = create_modern_slider(1, 50, 5, " msgs")
        grid.addWidget(threshold_label, row, 0); grid.addWidget(threshold_container, row, 1); row += 1
        ui_label = QLabel("UI Features:")
        ui_label.setStyleSheet("font-weight: bold; color: #666; margin-top: 12px; font-size: 12pt;")
        grid.addWidget(ui_label, row, 0, 1, 2); row += 1
        self.ab_streaming = create_modern_checkbox("Streaming", False)
        grid.addWidget(self.ab_streaming, row, 0, 1, 2); row += 1
        self.ab_text_size_changer = create_modern_checkbox("Text Size Changer", False)
        grid.addWidget(self.ab_text_size_changer, row, 0, 1, 2); row += 1
        text_size_b_label = QLabel("      Option B Text Size:")
        text_size_b_label.setStyleSheet("color: #666; margin-left: 20px; font-weight: 600;")
        text_size_b_container, text_size_b_spin = create_modern_slider(8, 48, 24, "pt")
        text_size_b_container.setVisible(False); text_size_b_label.setVisible(False)
        self.ab_setting_widgets['text_size_b'] = text_size_b_spin
        grid.addWidget(text_size_b_label, row, 0); grid.addWidget(text_size_b_container, row, 1); row += 1
        self.ab_text_size_changer.toggled.connect(lambda checked: (text_size_b_container.setVisible(checked), text_size_b_label.setVisible(checked)))
        self.ab_typewriter = create_modern_checkbox("Typewriter", False)
        grid.addWidget(self.ab_typewriter, row, 0, 1, 2); row += 1
        typewriter_speed_b_label = QLabel("      Option B Speed:")
        typewriter_speed_b_label.setStyleSheet("color: #666; margin-left: 20px; font-weight: 600;")
        typewriter_speed_b_container, typewriter_speed_b_spin = create_modern_slider(1, 1000, 50, " ms")
        typewriter_speed_b_container.setVisible(False); typewriter_speed_b_label.setVisible(False)
        self.ab_setting_widgets['typewriter_speed_ms_b'] = typewriter_speed_b_spin
        grid.addWidget(typewriter_speed_b_label, row, 0); grid.addWidget(typewriter_speed_b_container, row, 1); row += 1
        self.ab_typewriter.toggled.connect(lambda checked: (typewriter_speed_b_container.setVisible(checked), typewriter_speed_b_label.setVisible(checked)))
        self.ab_thinking = create_modern_checkbox("Thinking", False)
        grid.addWidget(self.ab_thinking, row, 0, 1, 2); row += 1
        return row
    
    def _add_modern_survey_section(self, grid, row):
        title = self._create_modern_section_title("📊 Survey Settings", "#17a2b8")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        trigger_label = QLabel("Show Survey Every:"); trigger_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        trigger_container, self.survey_trigger_spin = create_modern_slider(1, 20, 5, " messages")
        grid.addWidget(trigger_label, row, 0); grid.addWidget(trigger_container, row, 1); row += 1
        filename_label = QLabel("Survey Filename:"); filename_label.setStyleSheet("font-weight: 600; color: #4a5568;")
        self.survey_filename_input = QLineEdit(); self.survey_filename_input.setPlaceholderText("e.g., survey.json")
        self.survey_filename_input.setStyleSheet("padding: 8px; border: 2px solid #e2e8f0; border-radius: 4px;")
        grid.addWidget(filename_label, row, 0); grid.addWidget(self.survey_filename_input, row, 1); row += 1
        self.edit_survey_btn = QPushButton("Create / Edit Survey"); self.verify_survey_btn = QPushButton("Verify Survey File")
        btn_style = "QPushButton { background: #6c757d; color: white; border: none; border-radius: 8px; padding: 10px; font-weight: bold; font-size: 11pt; } QPushButton:hover { background: #5a6268; }"
        self.edit_survey_btn.setStyleSheet(btn_style); self.verify_survey_btn.setStyleSheet(btn_style)
        grid.addWidget(self.edit_survey_btn, row, 0); grid.addWidget(self.verify_survey_btn, row, 1); row += 1
        self.survey_status_label = QLabel("Status: Unknown"); self.survey_status_label.setStyleSheet("color: #666; margin-top: 5px;")
        grid.addWidget(self.survey_status_label, row, 0, 1, 2); row += 1
        self.edit_survey_btn.clicked.connect(self._launch_survey_builder); self.verify_survey_btn.clicked.connect(self._verify_survey_file)
        return self._add_section_separator(grid, row)
    
    def _add_modern_scripted_section(self, grid, row):
        title = self._create_modern_section_title("🎬 Scripted Response Editor", "#8e44ad")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        self.edit_script_btn = QPushButton("Create / Edit Script"); self.verify_script_btn = QPushButton("Verify Existing Script")
        btn_style = "QPushButton { background: #6c757d; color: white; border: none; border-radius: 8px; padding: 12px 24px; font-weight: bold; min-width: 80px; font-size: 11pt; } QPushButton:hover { background: #5a6268; }"
        self.edit_script_btn.setStyleSheet(btn_style); self.verify_script_btn.setStyleSheet(btn_style)
        filename = feature_settings.get('scripted_convo_file', 'script.json')
        self.script_status_label = QLabel(f"<b>Target file:</b> {filename}<br>Status: Unknown")
        self.script_status_label.setStyleSheet("color: #666; margin-top: 10px;")
        grid.addWidget(self.edit_script_btn, row, 0); grid.addWidget(self.verify_script_btn, row, 1); row += 1
        grid.addWidget(self.script_status_label, row, 0, 1, 2); row += 1
        self.edit_script_btn.clicked.connect(self._launch_script_editor); self.verify_script_btn.clicked.connect(self._verify_script_file)
        return self._add_section_separator(grid, row)
        
    def _add_modern_blueprint_section(self, grid, row):
        title = self._create_modern_section_title("▶️ Dynamic Experiment Blueprint", "#8e44ad")
        grid.addWidget(title, row, 0, 1, 2); row += 1
        filename_label = QLabel("Blueprint Filename:")
        self.blueprint_filename_input = QLineEdit()
        grid.addWidget(filename_label, row, 0); grid.addWidget(self.blueprint_filename_input, row, 1); row += 1
        open_btn = QPushButton("Open Blueprint..."); edit_btn = QPushButton("Create / Edit Blueprint"); verify_btn = QPushButton("Verify File")
        btn_layout = QHBoxLayout(); btn_layout.addWidget(open_btn); btn_layout.addWidget(edit_btn); btn_layout.addWidget(verify_btn)
        grid.addLayout(btn_layout, row, 0, 1, 2); row += 1
        self.blueprint_status_label = QLabel("Status: Unknown")
        grid.addWidget(self.blueprint_status_label, row, 0, 1, 2); row += 1
        open_btn.clicked.connect(lambda: self._load_from_file(self.blueprint_filename_input))
        edit_btn.clicked.connect(self._launch_experiment_designer)
        verify_btn.clicked.connect(self._verify_blueprint_file)
        return self._add_section_separator(grid, row)

    def _launch_script_editor(self):
        editor_dialog = ScriptEditorDialog(self)
        if editor_dialog.exec() == QDialog.Accepted:
            self.script_status_label.setText(f"<b>Target file:</b> {editor_dialog.filename}<br>Status: <b style='color: #28a745;'>Script saved!</b>")
        else:
            self.script_status_label.setText(f"<b>Target file:</b> {editor_dialog.filename}<br>Status: Editor cancelled, no changes saved.")

    def _launch_survey_builder(self):
        builder_dialog = SurveyBuilderDialog(self)
        if builder_dialog.exec() == QDialog.Accepted:
            self.survey_status_label.setText("Status: <b style='color: #28a745;'>Survey saved!</b>")
            self._verify_survey_file(show_success_popup=False)
        else:
            self.survey_status_label.setText("Status: Builder cancelled, no changes saved.")
            
    def _verify_survey_file(self, show_success_popup=True):
        filename = self.survey_filename_input.text().strip()
        if not filename:
            self.survey_status_label.setText("Status: <b style='color: #e74c3c;'>No filename specified.</b>"); return
        survey_path = Path(__file__).parent.parent.parent / "data" / "blueprints" / filename
        if survey_path.exists():
            self.survey_status_label.setText(f"Status: <b style='color: #28a745;'>File '{filename}' FOUND.</b>")
            if show_success_popup: QMessageBox.information(self, "Success", f"Survey file '{filename}' was found.")
        else:
            self.survey_status_label.setText(f"Status: <b style='color: #e74c3c;'>File '{filename}' NOT FOUND.</b>")
            if show_success_popup: QMessageBox.warning(self, "File Not Found", f"Survey file '{filename}' was not found.")

    def _verify_script_file(self, show_success_popup=True):
        filename = feature_settings.get('scripted_convo_file', 'script.json')
        script_path = Path(__file__).parent.parent.parent / "data" / "scripts" / filename
        if script_path.exists():
            self.script_status_label.setText(f"<b>Target file:</b> {filename}<br>Status: <b style='color: #28a745;'>File FOUND. Ready to use.</b>")
            if show_success_popup: QMessageBox.information(self, "Success", f"Script file '{filename}' was found.")
        else:
            self.script_status_label.setText(f"<b>Target file:</b> {filename}<br>Status: <b style='color: #e74c3c;'>File NOT FOUND.</b>")
            if show_success_popup: QMessageBox.warning(self, "File Not Found", f"Script file '{filename}' was not found.")
            
    def _create_modern_section_title(self, title_text, color="#667eea"):
        title = QLabel(title_text)
        title.setStyleSheet(f"""
            QLabel {{
                font-weight: bold; font-size: 14pt; margin-top: 15px; margin-bottom: 10px;
                color: {color}; padding: 8px 12px; background: rgba(102, 126, 234, 0.1);
                border-left: 4px solid {color}; border-radius: 6px;
            }}
        """)
        return title

    def _add_section_separator(self, grid, row):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("QFrame { color: #e2e8f0; background-color: #e2e8f0; height: 1px; margin: 15px 0; }")
        grid.addWidget(separator, row, 0, 1, 2)
        return row + 1
        
    def _load_from_file(self, line_edit_widget):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Blueprint File", "", "JSON Files (*.json)")
        if filepath:
            line_edit_widget.setText(Path(filepath).name)
            self._verify_blueprint_file(show_success_popup=False)

    def _save_and_accept(self):
        if hasattr(self, 'blueprint_filename_input'): feature_settings['blueprint_filename'] = self.blueprint_filename_input.text()
        if hasattr(self, 'mc_trigger_spin'): feature_settings['mc_trigger_count'] = self.mc_trigger_spin.value()
        if hasattr(self, 'mc_changes_list'):
            changes = [{"feature": self.mc_changes_list.item(i).text().split(" ", 1)[1], "enabled": self.mc_changes_list.item(i).text().startswith("Enable")} for i in range(self.mc_changes_list.count())]
            feature_settings['mc_changes'] = changes
        if hasattr(self, 'survey_trigger_spin'): feature_settings['survey_trigger_count'] = self.survey_trigger_spin.value()
        if hasattr(self, 'survey_filename_input'): feature_settings['survey_filename'] = self.survey_filename_input.text()
        if hasattr(self, 'chat_title_input'): feature_settings['custom_chat_title'] = self.chat_title_input.text()
        if hasattr(self, 'text_size_spin'): feature_settings['text_size'] = self.text_size_spin.value()
        if hasattr(self, 'delay_spin'): feature_settings['delay_seconds'] = self.delay_spin.value()
        if hasattr(self, 'messages_spin'): feature_settings['auto_end_messages'] = self.messages_spin.value()
        if hasattr(self, 'minutes_spin'): feature_settings['auto_end_minutes'] = self.minutes_spin.value()
        if hasattr(self, 'sd_period'): feature_settings['slowdown_period_s'] = self.sd_period.value()
        if hasattr(self, 'sd_window'): feature_settings['slowdown_window_s'] = self.sd_window.value()
        if hasattr(self, 'sd_min'): feature_settings['slowdown_min_delay_s'] = self.sd_min.value()
        if hasattr(self, 'sd_perm_en'): feature_settings['slowdown_permanent_after_enabled'] = self.sd_perm_en.isChecked()
        if hasattr(self, 'sd_perm_s'): feature_settings['slowdown_permanent_after_s'] = self.sd_perm_s.value()
        if hasattr(self, 'typewriter_speed'): feature_settings['typewriter_speed_ms'] = self.typewriter_speed.value()
        if hasattr(self, 'erase_delay'): feature_settings['erase_history_delay_s'] = self.erase_delay.value()
        if hasattr(self, 'erase_repeat'): feature_settings['erase_history_repeat'] = self.erase_repeat.isChecked()
        if hasattr(self, 'erase_interval'): feature_settings['erase_history_interval_s'] = self.erase_interval.value()
        if hasattr(self, 'block_msg_count'): feature_settings['block_message_count'] = self.block_msg_count.value()
        if hasattr(self, 'block_duration'): feature_settings['block_duration_s'] = self.block_duration.value()
        if hasattr(self, 'block_repeat'): feature_settings['block_repeat'] = self.block_repeat.isChecked()
        if hasattr(self, 'ab_threshold_spin'): feature_settings['ab_test_message_threshold'] = self.ab_threshold_spin.value()
        ab_features = {
            'ab_lie': 'ab_lie_b', 'ab_rude_tone': 'ab_rude_tone_b', 'ab_kind_tone': 'ab_kind_tone_b',
            'ab_advice_only': 'ab_advice_only_b', 'ab_no_memory': 'ab_no_memory_b', 'ab_persona': 'ab_persona_b',
            'ab_mirror': 'ab_mirror_b', 'ab_anti_mirror': 'ab_anti_mirror_b', 'ab_grammar_errors': 'ab_grammar_errors_b',
            'ab_positive_feedback': 'ab_positive_feedback_b', 'ab_critical_feedback': 'ab_critical_feedback_b',
            'ab_neutral_feedback': 'ab_neutral_feedback_b', 'ab_hedging': 'ab_hedging_b', 'ab_streaming': 'ab_streaming_b',
            'ab_text_size_changer': 'ab_text_size_changer_b', 'ab_typewriter': 'ab_typewriter_b', 'ab_thinking': 'ab_thinking_b'
        }
        for attr, key in ab_features.items():
            if hasattr(self, attr): feature_settings[key] = getattr(self, attr).isChecked()
        for key, widget in self.ab_setting_widgets.items():
            if isinstance(widget, QSlider): feature_settings[key] = widget.value()
            elif isinstance(widget, QCheckBox): feature_settings[key] = widget.isChecked()
        self.accept()