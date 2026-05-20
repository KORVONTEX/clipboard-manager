import sys
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QSystemTrayIcon, QMenu,
    QCheckBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction
import pyperclip
import keyboard


def get_config_path():
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    app_folder = os.path.join(appdata, 'ClipboardManager')

    if not os.path.exists(app_folder):
        os.makedirs(app_folder)

    return os.path.join(app_folder, 'config.json')


CONFIG_FILE = get_config_path()


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("show_notifications", True)
        except:
            return True
    return True


def save_config(show_notifications):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"show_notifications": show_notifications}, f, indent=2)
    except:
        pass


class ClipboardManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📋 Менеджер буфера обмена")
        self.setGeometry(100, 100, 650, 500)

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.history = []
        self.last_text = ""

        self.show_notifications = load_config()

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.setup_styles()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(500)

        QTimer.singleShot(1000, self.setup_tray)

        self.setup_hotkey()

        self.hide()

    def setup_hotkey(self):
        def on_hotkey():
            QTimer.singleShot(0, self.toggle_window)

        keyboard.add_hotkey('ctrl+shift+alt', on_hotkey)

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-family: 'Segoe UI';
            }
            QListWidget {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 8px;
                font-family: 'Consolas';
                font-size: 10pt;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #45475a;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 5px;
            }
            QListWidget::item:hover {
                background-color: #45475a;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:pressed {
                background-color: #6c7086;
            }
            QPushButton#clearBtn {
                background-color: #f38ba8;
            }
            QPushButton#clearBtn:hover {
                background-color: #eba0ac;
            }
            QCheckBox {
                color: #cdd6f4;
                font-family: 'Segoe UI';
                font-size: 9pt;
            }
        """)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("📋 МЕНЕДЖЕР БУФЕРА ОБМЕНА")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        subtitle = QLabel("Автоматически сохраняет всё, что вы копируете (Ctrl+C)")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 10pt; color: #a6adc8;")
        layout.addWidget(subtitle)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.paste_selected)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.paste_btn = QPushButton("📋 Вставить выбранное")
        self.paste_btn.clicked.connect(self.paste_selected)

        self.clear_btn = QPushButton("🗑️ Очистить историю")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_history)

        btn_layout.addWidget(self.paste_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        self.notification_checkbox = QCheckBox("🔔 Показывать уведомления при копировании")
        self.notification_checkbox.setChecked(self.show_notifications)
        self.notification_checkbox.stateChanged.connect(self.on_checkbox_changed)
        layout.addWidget(self.notification_checkbox)

        hotkey_info = QLabel("🎹 Глобальная горячая клавиша: Ctrl+Shift+Alt")
        hotkey_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_info.setStyleSheet("color: #89b4fa; font-size: 10pt; font-weight: bold; margin-top: 5px;")
        layout.addWidget(hotkey_info)

        self.status = QLabel("✅ Работает в фоне")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #a6adc8; font-size: 9pt; margin-top: 5px;")
        layout.addWidget(self.status)

    def on_checkbox_changed(self, state):
        self.show_notifications = (state == Qt.CheckState.Checked.value)
        save_config(self.show_notifications)
        self.update_tray_menu_text()

        status_text = "✅ Уведомления включены" if self.show_notifications else "🔕 Уведомления выключены"
        self.status.setText(status_text)
        QTimer.singleShot(2000, self.reset_status)

    def update_tray_menu_text(self):
        if hasattr(self, 'tray_notification_action'):
            if self.show_notifications:
                self.tray_notification_action.setText("🔔 Уведомления: ВКЛ")
            else:
                self.tray_notification_action.setText("🔕 Уведомления: ВЫКЛ")

    def setup_tray(self):
        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("📋 Менеджер буфера обмена")

        tray_menu = QMenu()

        show_action = QAction("📋 Показать окно", self)
        show_action.triggered.connect(self.show_window)

        self.tray_notification_action = QAction("", self)
        self.update_tray_menu_text()
        self.tray_notification_action.triggered.connect(self.toggle_notifications_from_tray)

        quit_action = QAction("🚪 Выйти", self)
        quit_action.triggered.connect(self.quit_app)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_notification_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_click)
        self.tray_icon.show()

        self.show_tray_message("Программа запущена\nCtrl+Shift+Alt для вызова")

    def toggle_notifications_from_tray(self):
        self.show_notifications = not self.show_notifications
        save_config(self.show_notifications)

        self.notification_checkbox.setChecked(self.show_notifications)
        self.update_tray_menu_text()

        status_text = "✅ Уведомления включены" if self.show_notifications else "🔕 Уведомления выключены"
        self.status.setText(status_text)
        self.show_tray_message(status_text, 1500)
        QTimer.singleShot(2000, self.reset_status)

    def show_tray_message(self, message, duration=300):
        if self.show_notifications and hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "Clipboard Manager",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration
            )

    def update_list(self):
        self.list_widget.clear()
        for text, timestamp in self.history:
            display = text[:80] + "..." if len(text) > 80 else text
            display = display.replace("\n", "↩ ").replace("\r", "")
            item = QListWidgetItem(f"[{timestamp}]  {display}")
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.list_widget.addItem(item)

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        self.status.setText("💡 Двойной клик по элементу — скопировать в буфер")
        QTimer.singleShot(3000, self.reset_status)

    def toggle_window(self):
        if self.isVisible():
            self.hide()
            self.status.setText("✅ Работает в фоне")
        else:
            self.show_window()

    def reset_status(self):
        self.status.setText("✅ Работает в фоне")

    def check_clipboard(self):
        try:
            current = pyperclip.paste()
            if not current or current == self.last_text:
                return

            is_duplicate = False
            for text, _ in self.history:
                if text == current:
                    is_duplicate = True
                    break

            if not is_duplicate:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.history.insert(0, (current, timestamp))

                if len(self.history) > 50:
                    self.history.pop()

                self.update_list()
                self.last_text = current

                display = current[:80] + "..." if len(current) > 80 else current
                display = display.replace("\n", "↩ ").replace("\r", "")

                if self.show_notifications and hasattr(self, 'tray_icon'):
                    self.tray_icon.showMessage(
                        "📋 Скопировано!",
                        display[:60] + "...",
                        QSystemTrayIcon.MessageIcon.Information,
                        300
                    )
        except Exception as e:
            pass

    def paste_selected(self):
        current = self.list_widget.currentItem()
        if current:
            text = current.data(Qt.ItemDataRole.UserRole)
            pyperclip.copy(text)
            self.status.setText("✅ Скопировано в буфер!")
            QTimer.singleShot(2000, self.reset_status)
            self.hide()

    def clear_history(self):
        if self.history:
            self.history.clear()
            self.list_widget.clear()
            self.status.setText("🗑️ История очищена")
            QTimer.singleShot(2000, self.reset_status)

    def quit_app(self):
        keyboard.unhook_all()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if sys.platform == 'win32':
        import ctypes

        myappid = 'clipboard.manager.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    window = ClipboardManager()
    sys.exit(app.exec())
