import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QDialog, QListWidget,
    QLineEdit, QPushButton, QDialogButtonBox, QAbstractItemView, QLabel,
    QMessageBox, QListWidgetItem, QTextEdit, QStackedWidget, QWidget
)
from ..feature_flags import feature_settings

class ScriptEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JSON Script Editor")
        self.setMinimumSize(800, 600)
        self.filename = feature_settings.get('scripted_convo_file', 'script.json')
        self.script_path = Path(__file__).parent.parent.parent / "data" / "scripts" / self.filename
        self.current_editing_item = None
        self._setup_ui()
        self._connect_signals()
        self._load_script_from_file()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        left_panel_layout = QVBoxLayout()
        add_btn_layout = QHBoxLayout()
        self.add_normal_btn = QPushButton("Add Normal Step")
        self.add_ab_btn = QPushButton("Add A/B Test Step")
        add_btn_layout.addWidget(self.add_normal_btn)
        add_btn_layout.addWidget(self.add_ab_btn)
        left_panel_layout.addLayout(add_btn_layout)
        self.step_list_widget = QListWidget()
        self.step_list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.step_list_widget.setAlternatingRowColors(True)
        self.step_list_widget.setMinimumWidth(300)
        left_panel_layout.addWidget(self.step_list_widget)
        self.delete_btn = QPushButton("Delete Selected Step")
        self.delete_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        left_panel_layout.addWidget(self.delete_btn)
        main_layout.addLayout(left_panel_layout, 1)
        
        right_panel_layout = QVBoxLayout()
        self.editor_stack = QStackedWidget()
        self.blank_editor_widget = QWidget()
        blank_layout = QVBoxLayout(self.blank_editor_widget)
        blank_layout.addStretch()
        blank_label = QLabel("Select a step from the list to edit it,\nor add a new step.")
        blank_label.setAlignment(Qt.AlignCenter)
        blank_label.setStyleSheet("font-size: 14pt; color: #888;")
        blank_layout.addWidget(blank_label)
        blank_layout.addStretch()
        self.normal_editor_widget = self._create_normal_editor_widget()
        self.ab_editor_widget = self._create_ab_editor_widget()
        self.editor_stack.addWidget(self.blank_editor_widget)
        self.editor_stack.addWidget(self.normal_editor_widget)
        self.editor_stack.addWidget(self.ab_editor_widget)
        right_panel_layout.addWidget(self.editor_stack, 1)
        self.apply_changes_btn = QPushButton("Apply Changes to Step")
        self.apply_changes_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        right_panel_layout.addWidget(self.apply_changes_btn)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        right_panel_layout.addWidget(self.button_box)
        main_layout.addLayout(right_panel_layout, 2)

    def _create_normal_editor_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Normal Response:")
        label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 5px;")
        self.normal_edit_box = QTextEdit()
        layout.addWidget(label)
        layout.addWidget(self.normal_edit_box)
        return widget

    def _create_ab_editor_widget(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("A/B Test Response:")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 5px; color: #c0392b;")
        main_layout.addWidget(title_label)
        split_layout = QHBoxLayout()
        layout_a = QVBoxLayout()
        label_a = QLabel("Response A")
        self.ab_edit_a = QTextEdit()
        layout_a.addWidget(label_a)
        layout_a.addWidget(self.ab_edit_a)
        layout_b = QVBoxLayout()
        label_b = QLabel("Response B")
        self.ab_edit_b = QTextEdit()
        layout_b.addWidget(label_b)
        layout_b.addWidget(self.ab_edit_b)
        split_layout.addLayout(layout_a)
        split_layout.addLayout(layout_b)
        main_layout.addLayout(split_layout)
        return widget

    def _connect_signals(self):
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.add_normal_btn.clicked.connect(self._add_normal_step)
        self.add_ab_btn.clicked.connect(self._add_ab_step)
        self.delete_btn.clicked.connect(self._delete_selected_step)
        self.apply_changes_btn.clicked.connect(self._save_editor_to_item)
        self.step_list_widget.currentItemChanged.connect(self._on_step_selected)

    def _load_script_from_file(self):
        if not self.script_path.exists():
            print(f"No script file found at {self.script_path}, starting fresh.")
            return
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Script file is not a valid JSON list.")
            self.step_list_widget.clear()
            for step_data in data:
                self._add_step_to_list_widget(step_data)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load or parse {self.filename}:\n{e}")

    def _add_step_to_list_widget(self, step_data, insert_row=None):
        item_type = step_data.get("type", "normal")
        display_text = ""
        if item_type == "normal":
            summary = step_data.get('response', '')[:40] + "..."
            display_text = f"[Normal]: \"{summary}\""
        elif item_type == "ab_test":
            summary_a = step_data.get('response_a', '')[:20] + "..."
            summary_b = step_data.get('response_b', '')[:20] + "..."
            display_text = f"[A/B]: A:\"{summary_a}\" | B:\"{summary_b}\""
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, step_data)
        if insert_row is not None:
            self.step_list_widget.insertItem(insert_row, item)
        else:
            self.step_list_widget.addItem(item)
        return item

    def _add_normal_step(self):
        new_step_data = {"type": "normal", "response": "New normal response. Edit me."}
        item = self._add_step_to_list_widget(new_step_data)
        self.step_list_widget.setCurrentItem(item)

    def _add_ab_step(self):
        new_step_data = {
            "type": "ab_test",
            "response_a": "New A-Side Response. Edit me.",
            "response_b": "New B-Side Response. Edit me."
        }
        item = self._add_step_to_list_widget(new_step_data)
        self.step_list_widget.setCurrentItem(item)
        
    def _delete_selected_step(self):
        current_row = self.step_list_widget.currentRow()
        if current_row >= 0:
            item = self.step_list_widget.takeItem(current_row)
            del item

    def _on_step_selected(self, current_item, previous_item):
        if previous_item:
            self._save_editor_to_item(previous_item)
        if not current_item:
            self.editor_stack.setCurrentWidget(self.blank_editor_widget)
            self.current_editing_item = None
            return
        data = current_item.data(Qt.UserRole)
        self.current_editing_item = current_item
        if data.get("type") == "normal":
            self.normal_edit_box.setPlainText(data.get("response", ""))
            self.editor_stack.setCurrentWidget(self.normal_editor_widget)
        elif data.get("type") == "ab_test":
            self.ab_edit_a.setPlainText(data.get("response_a", ""))
            self.ab_edit_b.setPlainText(data.get("response_b", ""))
            self.editor_stack.setCurrentWidget(self.ab_editor_widget)
        else:
            self.editor_stack.setCurrentWidget(self.blank_editor_widget)

    def _save_editor_to_item(self, item_to_save=None):
        if not item_to_save:
            item_to_save = self.current_editing_item
        if not item_to_save:
            return
        data = item_to_save.data(Qt.UserRole)
        item_type = data.get("type")
        if item_type == "normal":
            data["response"] = self.normal_edit_box.toPlainText()
            summary = data['response'][:40] + "..."
            item_to_save.setText(f"[Normal]: \"{summary}\"")
        elif item_type == "ab_test":
            data["response_a"] = self.ab_edit_a.toPlainText()
            data["response_b"] = self.ab_edit_b.toPlainText()
            summary_a = data['response_a'][:20] + "..."
            summary_b = data['response_b'][:20] + "..."
            item_to_save.setText(f"[A/B]: A:\"{summary_a}\" | B:\"{summary_b}\"")
        item_to_save.setData(Qt.UserRole, data)

    def _save_and_accept(self):
        self._save_editor_to_item()
        script_to_save = []
        for i in range(self.step_list_widget.count()):
            item = self.step_list_widget.item(i)
            data = item.data(Qt.UserRole)
            script_to_save.append(data)
        try:
            with open(self.script_path, 'w', encoding='utf-8') as f:
                json.dump(script_to_save, f, indent=4)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save script file: {e}\n\nPlease check permissions and try again.")