from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QFrame,
    QGraphicsDropShadowEffect, QLabel, QPushButton, QProgressBar, QScrollArea,
    QSizePolicy, QDialog
)

from app.data_logger import set_features, set_participant_info
from app.feature_flags import FeatureFlag, enabled_features, FEATURE_GROUPS, feature_settings
from app.helpers import is_enabled
from app.themes import THEMES, get_theme, save_theme_preference, load_theme_preference
from app.constants import SONA_ID
from app.ui.ui_components import CollapsibleSection
from app.ui.tooltip import CustomTooltip, current_tooltip
from app.ui.dialogs import SettingsDialog
from app.ui.ConsentDebrief import SonaIdDialog, ConsentDialog
from app.ui.chat_window import ChatWindow
from app.help_text import get_feature_tooltip

class ControlPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ControlPanel")
        self.current_theme_name = load_theme_preference()
        app = QApplication.instance()
        if app:
            app.setEffectEnabled(Qt.UIEffect.UI_AnimateTooltip, False)
            app.setEffectEnabled(Qt.UIEffect.UI_FadeTooltip, False)

        self._build_ui()
        self._update_feature_progress(None, False)

    def _build_ui(self) -> None:
        self.setWindowTitle("Control Panel")
        self.resize(900, 700)
        
        theme = get_theme(self.current_theme_name)
        self.setStyleSheet(f"""
            #ControlPanel {{
                background: {theme['background']};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)

        container = QFrame(self)
        container.setObjectName("controlCard")
        container.setStyleSheet("""
            #controlCard {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-radius: 20px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0,0,0, 150))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header = QLabel("Feature Control Panel", alignment=Qt.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                font-size: 28pt; font-weight: 700; color: white;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                margin-bottom: 8px; background: transparent;
            }
        """)
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        self.theme_btn = QPushButton("Theme")
        self.theme_btn.setFixedSize(80, 35)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15); color: white;
                border: 1px solid rgba(255, 255, 255, 0.4); border-radius: 8px;
                font-size: 11pt; font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.6);
            }
        """)
        self.theme_btn.clicked.connect(self._show_theme_menu)
        header_layout.addWidget(self.theme_btn)
        layout.addLayout(header_layout)

        self.theme_menu = QWidget(self)
        self.theme_menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.theme_menu.setAttribute(Qt.WA_TranslucentBackground)
        self.theme_menu.setStyleSheet("QWidget { background: rgba(40, 40, 40, 0.95); border: 2px solid rgba(255, 255, 255, 0.8); border-radius: 12px; }")
        theme_menu_layout = QVBoxLayout(self.theme_menu)
        theme_menu_layout.setContentsMargins(10, 10, 10, 10)
        theme_menu_layout.setSpacing(5)

        for theme_name, theme_colors in THEMES.items():
            theme_btn = QPushButton(theme_name)
            theme_btn.setFixedHeight(45)
            is_active = (theme_name == self.current_theme_name)
            border_style = "3px solid white" if is_active else "1px solid rgba(255, 255, 255, 0.3)"
            theme_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {theme_colors['background']}; color: white; border: {border_style};
                    border-radius: 8px; padding: 8px; font-size: 11pt; font-weight: bold;
                    text-align: left; padding-left: 15px; text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
                }}
                QPushButton:hover {{ border: 2px solid white; }}
            """)
            theme_btn.clicked.connect(lambda checked, name=theme_name: self._select_theme(name))
            theme_menu_layout.addWidget(theme_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 10px; background: rgba(255, 255, 255, 0.2);
                text-align: center; font-weight: bold; color: white; height: 20px;
            }}
            QProgressBar::chunk {{
                border-radius: 10px; background: {theme['progress_bar']};
            }}
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(16)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { background: rgba(0, 0, 0, 0.1); width: 12px; border-radius: 6px; margin: 0; } QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.4); border-radius: 6px; min-height: 20px; } QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.7); } QScrollBar:vertical:!enabled { background: transparent; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.sections_layout = QVBoxLayout(scroll_widget)
        self.sections_layout.setSpacing(0)

        flag_to_group_map = {}
        for group_title, flag_list in FEATURE_GROUPS.items():
            for flag_name in flag_list:
                flag_to_group_map[flag_name] = group_title
        
        self.sections = {title: CollapsibleSection(title) for title in FEATURE_GROUPS}
        self.sections["Other"] = CollapsibleSection("Other Features")

        self.feature_buttons = {}
        for flag in FeatureFlag:
            btn = self._create_modern_feature_button(flag)
            self.feature_buttons[flag] = btn
            group_title = flag_to_group_map.get(flag.name, "Other")
            self.sections[group_title].addButton(btn)

        for group_title in FEATURE_GROUPS:
            section = self.sections[group_title]
            if section.button_count > 0:
                section.finalize_grid()
                self.sections_layout.addWidget(section)
        
        other_section = self.sections["Other"]
        if other_section.button_count > 0:
            other_section.finalize_grid()
            self.sections_layout.addWidget(other_section)

        self.sections_layout.addStretch(1)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area, 1)

        cont = QPushButton("Continue to Chat")
        cont.setObjectName("cont_btn")
        cont.setFixedHeight(50)
        cont.setStyleSheet(f"QPushButton {{ background: {theme['button_gradient']}; color: white; border: none; border-radius: 25px; font-size: 16pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }} QPushButton:hover {{ background: {theme['button_hover']}; }}")
        cont.clicked.connect(self._start_chat)
        layout.addWidget(cont)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container, stretch=1)
        main_layout.setContentsMargins(40, 40, 40, 40)

    def _show_theme_menu(self):
        btn_pos = self.theme_btn.mapToGlobal(self.theme_btn.rect().bottomRight())
        self.theme_menu.move(btn_pos.x() - self.theme_menu.width() + 20, btn_pos.y() + 5)
        self.theme_menu.show()

    def _select_theme(self, theme_name):
        self._apply_theme(theme_name)
        self.theme_menu.close()
        for btn in self.theme_menu.findChildren(QPushButton):
            if btn.text() in THEMES:
                btn_theme = THEMES[btn.text()]
                is_active = (btn.text() == theme_name)
                border_style = "3px solid white" if is_active else "1px solid rgba(255, 255, 255, 0.3)"
                btn.setStyleSheet(f"QPushButton {{ background: {btn_theme['background']}; color: white; border: {border_style}; border-radius: 8px; padding: 8px; font-size: 11pt; font-weight: bold; text-align: left; padding-left: 15px; text-shadow: 1px 1px 2px rgba(0,0,0,0.7); }} QPushButton:hover {{ border: 2px solid white; }}")

    def _apply_theme(self, theme_name):
        self.current_theme_name = theme_name
        save_theme_preference(theme_name)
        theme = get_theme(theme_name)
        
        self.setStyleSheet(f"#ControlPanel {{ background: {theme['background']}; font-family: 'Segoe UI', Arial, sans-serif; }}")
        
        self.progress_bar.setStyleSheet(f"QProgressBar {{ border: none; border-radius: 10px; background: rgba(255, 255, 255, 0.2); text-align: center; font-weight: bold; color: white; height: 20px; }} QProgressBar::chunk {{ border-radius: 10px; background: {theme['progress_bar']}; }}")
        
        cont_btn = self.findChild(QPushButton, "cont_btn")
        if cont_btn:
            cont_btn.setStyleSheet(f"QPushButton {{ background: {theme['button_gradient']}; color: white; border: none; border-radius: 25px; font-size: 16pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }} QPushButton:hover {{ background: {theme['button_hover']}; }}")
    
    def eventFilter(self, obj, event):
        global current_tooltip
        if event.type() == event.Type.Enter:
            if hasattr(obj, 'tooltip_text') and obj.tooltip_text:
                if current_tooltip:
                    current_tooltip.hide()
                current_tooltip = CustomTooltip(obj.tooltip_text)
                pos = obj.mapToGlobal(obj.rect().bottomRight())
                current_tooltip.move(pos.x() - current_tooltip.width(), pos.y() + 5)
                current_tooltip.show()
                return True
        elif event.type() == event.Type.Leave:
            if current_tooltip:
                current_tooltip.hide()
                current_tooltip = None
            return True
        return super().eventFilter(obj, event)

    def _create_modern_feature_button(self, flag):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setChecked(bool(enabled_features.get(flag, False)))
        btn.setMinimumHeight(70)
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        button_layout = QHBoxLayout(btn)
        button_layout.setContentsMargins(12, 8, 8, 8)
        
        feature_label = QLabel(flag.name.replace('_', ' ').title())
        feature_label.setStyleSheet("color: white; font-size: 11pt; font-weight: bold; background: transparent;")
        feature_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        icon_widget = QLabel("🔍")
        icon_widget.setFixedSize(20, 20)
        icon_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_widget.setStyleSheet("QLabel { background: rgba(255, 255, 255, 0.5); border-radius: 10px; font-size: 11pt; padding: 0px; color: rgba(0, 0, 0, 0.8); } QLabel:hover { background: rgba(255, 255, 255, 0.8); }")
        
        icon_widget.tooltip_text = get_feature_tooltip(flag)
        icon_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        icon_widget.installEventFilter(self)
        
        button_layout.addWidget(feature_label, 0)
        button_layout.addStretch(1)
        button_layout.addWidget(icon_widget, 0)
        
        theme = get_theme(self.current_theme_name)
        btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(255, 255, 255, 0.1); border: 2px solid rgba(255, 255, 255, 0.6); border-radius: 12px; text-align: left; min-width: 160px; }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.9); }}
            QPushButton:checked {{ background: {theme['feature_enabled']}; border: 2px solid #11998e; }}
            QPushButton:checked:hover {{ background: {theme['feature_enabled']}; }}
        """)
        
        btn.toggled.connect(lambda checked, f=flag: self._update_feature_progress(f, checked))
        return btn

    def _update_feature_progress(self, flag, checked):
        if flag is not None:
            enabled_features[flag] = checked
        
        enabled_count = sum(1 for enabled in enabled_features.values() if enabled)
        total_count = len(FeatureFlag)
        
        progress = int((enabled_count / total_count) * 100) if total_count > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"{enabled_count}/{total_count} Features Enabled")

    def _features_need_settings(self) -> bool:
        features_with_settings = [
            FeatureFlag.TEXT_SIZE_CHANGER, FeatureFlag.DELAY_BEFORE_SEND,
            FeatureFlag.AUTO_END_AFTER_N_MSGS, FeatureFlag.AUTO_END_AFTER_T_MIN,
            FeatureFlag.SLOWDOWN, FeatureFlag.ERASE_HISTORY, FeatureFlag.BLOCK_MSGS,
            FeatureFlag.AB_TESTING, FeatureFlag.TYPEWRITER, FeatureFlag.SCRIPTED_RESPONSES,
            FeatureFlag.CUSTOM_CHAT_TITLE, FeatureFlag.INTER_TRIAL_SURVEY,
            FeatureFlag.DYNAMIC_FEATURE_CHANGING,
        ]
        return any(is_enabled(feature) for feature in features_with_settings)

    def _start_chat(self) -> None:
        if self._features_need_settings():
            settings_dialog = SettingsDialog(self)
            if not settings_dialog.exec():
                return

        set_features(enabled_features)
        
        from ..data_logger import set_feature_settings
        try:
            set_feature_settings(feature_settings)
        except Exception as e:
            print(f"Error storing feature settings: {e}")
        
        self.hide() 

        sona = SonaIdDialog() 
        if not sona.exec():
            self.showMaximized()
            return 
        
        set_participant_info(sona_id=SONA_ID)

        consent = ConsentDialog() 
        if not consent.exec():
            self.showMaximized()
            return
        set_participant_info(consent=True)
        
        self.chat_window = ChatWindow()
        self.chat_window.showMaximized()

        try:
            if self.chat_window.search_button:
                self.chat_window.search_button.setVisible(is_enabled(FeatureFlag.WEB_SEARCH))
        except Exception:
            pass