import sys
import json
import uuid
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QListWidget, QPushButton, QLabel, QStackedWidget, QWidget, QFrame,
    QListWidgetItem, QLineEdit, QFormLayout, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QScrollArea
)

from app.feature_flags import FeatureFlag, FEATURE_GROUPS
from app.ui.ui_components import CollapsibleSection, create_modern_slider, create_modern_checkbox
from app.ui.script_editor import ScriptEditorDialog
from app.ui.survey_builder import SurveyBuilderDialog

class ExperimentDesignerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experiment Designer")
        self.setMinimumSize(1000, 700)
        self.setObjectName("ExperimentDesigner")
        self.setStyleSheet("""
            QDialog#ExperimentDesigner { background-color: #f0f0f0; }
            QDialog#ExperimentDesigner QWidget { background-color: transparent; color: #212529; }
            #ExperimentDesigner QListWidget, #ExperimentDesigner QLineEdit, #ExperimentDesigner QComboBox, 
            #ExperimentDesigner QTableWidget, #ExperimentDesigner QSpinBox, #ExperimentDesigner QStackedWidget {
                background-color: white; color: black; border: 1px solid #ccc; border-radius: 4px; padding: 4px;
            }
            #ExperimentDesigner QPushButton { color: black; background-color: #e1e1e1; border: 1px solid #adadad; padding: 8px; border-radius: 4px; }
            #ExperimentDesigner QPushButton:hover { background-color: #e9e9e9; }
        """)
        
        self.settings_frames = {}
        self.settings_widgets = {}

        dialog_layout = QVBoxLayout(self)
        panel_layout = QHBoxLayout()
        panel_layout.setContentsMargins(10, 10, 10, 10)

        left_panel_widget = QFrame()
        left_panel_widget.setFrameShape(QFrame.StyledPanel)
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.addWidget(QLabel("<b>Experiment Timeline</b>"))
        self.block_list_widget = QListWidget()
        self.block_list_widget.setDragDropMode(QListWidget.InternalMove)
        left_panel_layout.addWidget(self.block_list_widget)
        list_btn_layout = QHBoxLayout()
        self.add_block_btn = QPushButton("Add Block")
        self.remove_block_btn = QPushButton("Remove Block")
        list_btn_layout.addWidget(self.add_block_btn)
        list_btn_layout.addWidget(self.remove_block_btn)
        left_panel_layout.addLayout(list_btn_layout)
        panel_layout.addWidget(left_panel_widget, 1)

        right_panel_widget = QFrame()
        right_panel_widget.setFrameShape(QFrame.StyledPanel)
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.addWidget(QLabel("<b>Block Inspector</b>"))
        self.editor_stack = QStackedWidget()
        self.blank_editor = QLabel("Select a block to edit, or add a new one.")
        self.blank_editor.setAlignment(Qt.AlignCenter)
        self.blank_editor.setStyleSheet("font-size: 14pt; color: #888;")
        self.editor_stack.addWidget(self.blank_editor)
        self.block_editor = self._create_block_editor()
        self.editor_stack.addWidget(self.block_editor)
        right_panel_layout.addWidget(self.editor_stack, 1)
        panel_layout.addWidget(right_panel_widget, 2)
        dialog_layout.addLayout(panel_layout)
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Open | QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        dialog_layout.addWidget(self.button_box)

        self.add_block_btn.clicked.connect(self._add_block)
        self.remove_block_btn.clicked.connect(self._remove_selected_block)
        self.block_list_widget.currentItemChanged.connect(self._on_block_selected)
        self.button_box.button(QDialogButtonBox.Open).clicked.connect(self._load_from_file)
        self.button_box.button(QDialogButtonBox.Save).clicked.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)

        for _, button in self.feature_buttons.items():
            button.toggled.connect(self._update_settings_visibility)

    def _create_block_editor(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        basic_settings_widget = QWidget()
        form_layout = QFormLayout(basic_settings_widget)
        self.block_name_edit = QLineEdit()
        self.block_duration_spin = QSpinBox()
        self.block_duration_spin.setRange(1, 999)
        self.block_duration_spin.setSuffix(" messages")
        form_layout.addRow(QLabel("<b>Block Name:</b>"), self.block_name_edit)
        form_layout.addRow(QLabel("<b>Duration:</b>"), self.block_duration_spin)
        layout.addWidget(basic_settings_widget)
        layout.addWidget(QLabel("<b>Active Features:</b>"))
        self.feature_editor_widget, self.feature_buttons = self._create_feature_editor()
        layout.addWidget(self.feature_editor_widget)
        layout.addWidget(QLabel("<b>Feature Settings:</b>"))
        self.settings_area = QScrollArea()
        self.settings_area.setWidgetResizable(True)
        self.settings_area.setStyleSheet("QScrollArea { border: 1px solid #ccc; border-radius: 4px; background-color: white; }")
        settings_container = QWidget()
        self.settings_layout = QVBoxLayout(settings_container)
        self.settings_layout.setContentsMargins(10, 10, 10, 10)
        self.settings_layout.addStretch()
        self.settings_area.setWidget(settings_container)
        layout.addWidget(self.settings_area, 1)
        self._create_all_settings_widgets()
        return container

    def _create_feature_editor(self):
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setStyleSheet("QScrollArea { border: none; }")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        feature_buttons = {}
        flag_to_group_map = {}
        for group_title, flag_list in FEATURE_GROUPS.items():
            for flag_name in flag_list:
                flag_to_group_map[flag_name] = group_title
        sections = {title: CollapsibleSection(title, mode='light') for title in FEATURE_GROUPS.keys()}
        for flag in FeatureFlag:
            if flag == FeatureFlag.DYNAMIC_FEATURE_CHANGING:
                continue
            btn = QPushButton(flag.name.replace('_', ' ').title())
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { text-align: left; padding: 8px; background-color: #f0f0f0; border: 1px solid #ccc; }
                QPushButton:checked { background-color: #c8e6c9; border-color: #81c784; font-weight: bold; }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            feature_buttons[flag] = btn
            group_title = flag_to_group_map.get(flag.name, "Other")
            if group_title not in sections:
                sections[group_title] = CollapsibleSection(group_title, mode='light')
            sections[group_title].addButton(btn)
        for section in sections.values():
            if section.button_count > 0:
                layout.addWidget(section)
        layout.addStretch()
        container.setWidget(widget)
        return container, feature_buttons

    def _create_all_settings_widgets(self):
        # ... (This method is the same as the last version I provided) ...
        pass

    def _create_vas_editor(self):
        container = QWidget()
        layout = QFormLayout(container)
        layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.vas_question_edit = QLineEdit()
        self.vas_left_label_edit = QLineEdit()
        self.vas_right_label_edit = QLineEdit()
        layout.addRow("<b>Question Text:</b>", self.vas_question_edit)
        layout.addRow("<b>Left Scale Label (0%):</b>", self.vas_left_label_edit)
        layout.addRow("<b>Right Scale Label (100%):</b>", self.vas_right_label_edit)
        return container

    def _create_likert_editor(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        form_layout = QFormLayout()
        self.likert_question_edit = QLineEdit()
        form_layout.addRow("<b>Question Text:</b>", self.likert_question_edit)
        self.likert_points_spinbox = QSpinBox()
        self.likert_points_spinbox.setRange(3, 20)
        self.likert_points_spinbox.setSingleStep(1)
        form_layout.addRow("<b>Number of Points:</b>", self.likert_points_spinbox)
        layout.addLayout(form_layout)
        layout.addWidget(QLabel("<b>Anchors (Optional):</b>"))
        self.likert_anchors_table = QTableWidget()
        self.likert_anchors_table.setColumnCount(2)
        self.likert_anchors_table.setHorizontalHeaderLabels(["Point", "Anchor Text"])
        self.likert_anchors_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # --- FIX #1 ---
        self.likert_anchors_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.likert_anchors_table)
        self.likert_points_spinbox.valueChanged.connect(self._update_likert_table)
        return container
        
    def _create_options_editor(self, title):
        container = QWidget()
        layout = QVBoxLayout(container)
        form_layout = QFormLayout()
        question_edit = QLineEdit()
        form_layout.addRow("<b>Question Text:</b>", question_edit)
        layout.addLayout(form_layout)
        layout.addWidget(QLabel(f"<b>{title}:</b>"))
        options_list = QListWidget()
        
        # --- FIX #2 ---
        font = QApplication.font()
        font.setPointSize(10)
        options_list.setFont(font)

        options_list.setAlternatingRowColors(True)
        layout.addWidget(options_list)
        btn_layout = QHBoxLayout()
        add_option_edit = QLineEdit()
        add_option_edit.setPlaceholderText("Enter new option text...")
        add_btn = QPushButton("Add Option")
        remove_btn = QPushButton("Remove Selected")
        btn_layout.addWidget(add_option_edit, 1)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        layout.addLayout(btn_layout)
        editor_widgets = {
            "question": question_edit, "options_list": options_list,
            "add_option_edit": add_option_edit, "add_btn": add_btn, "remove_btn": remove_btn
        }
        
        def add_item():
            text = add_option_edit.text().strip()
            if text:
                new_item = QListWidgetItem(text)
                new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                options_list.addItem(new_item)
                add_option_edit.clear()
        
        def remove_item():
            current_item = options_list.currentItem()
            if current_item:
                options_list.takeItem(options_list.row(current_item))
        
        def edit_item(item):
            options_list.editItem(item)

        add_btn.clicked.connect(add_item)
        remove_btn.clicked.connect(remove_item)
        add_option_edit.returnPressed.connect(add_item)
        options_list.itemDoubleClicked.connect(edit_item)

        container.setProperty("editor_widgets", editor_widgets)
        return container

    def _update_likert_table(self, num_points):
        # ... (This method is unchanged) ...
        pass

    def _add_question(self):
        # ... (This method is unchanged) ...
        pass
        
    def _delete_question(self):
        # ... (This method is unchanged) ...
        pass

    def _on_question_selected(self, current_item, previous_item):
        # ... (This method is unchanged) ...
        pass

    def _save_editor_to_item(self, item_to_save):
        # ... (This method is unchanged) ...
        pass

    def _load_from_file(self):
        # ... (This method is unchanged) ...
        pass

    def _save_and_accept(self):
        # ... (This method is unchanged) ...
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    builder = SurveyBuilderDialog()
    builder.show()
    sys.exit(app.exec())