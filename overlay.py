import datetime
import os
import sys
import threading
import time

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# The string to detect for starting and resetting the cooldown
TARGET_STRING = "Your Undying Retribution Relic saves your life. The Relic has lost power for 3 minutes."
RESET_STRING = "Your Undying Retribution relic is now ready."  # String that resets the cooldown

def resource_path(relative_path):
    """ Get the absolute path to the resource (works for PyInstaller). """
    if hasattr(sys, '_MEIPASS'):
        # If running in a PyInstaller bundle, look in the _MEIPASS folder
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        # If running as a script, use the current directory
        return os.path.join(os.path.abspath("."), relative_path)

class Overlay(QWidget):
    start_timer_signal = pyqtSignal(int)  # Signal to start the timer from another thread
    reset_timer_signal = pyqtSignal()     # Signal to reset the timer from another thread

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(52, 20, 150, 150)  # Adjust size

        # Use absolute positioning to overlap text and image
        self.image_label = QLabel("Ready", self)
        self.image_label.setGeometry(0, 0, 68, 68)  # Set the size of the image label
        pixmap = QPixmap(resource_path("undyingimg.png"))
        self.image_label.setPixmap(pixmap)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background-color: rgba(79, 75, 71, 170); border: 4px solid #40372F; border-radius: 4px;")
        

        # Text label that will appear on top of the image
        self.text_label = QLabel("Ready", self)
        self.text_label.setGeometry(0, 28, 68, 45)  # Position the text at the bottom part of the image
        self.text_label.setStyleSheet("""
            color: limegreen;
            font-size: 18px;
            font-weight: bold;
        """)
        
        # Apply drop shadow to simulate text outline
        self.apply_text_shadow(self.text_label)
        
        # align text to center
        self.text_label.setAlignment(Qt.AlignCenter)  # Center the text
        self.image_label.stackUnder(self.text_label)

        # Timer settings
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.time_left = 0
        self.last_triggered = None

        # Variables for dragging
        self.is_dragging = False
        self.drag_start_position = QPoint()

        # Connect the signals to their respective slots
        self.start_timer_signal.connect(self.start_countdown)
        self.reset_timer_signal.connect(self.reset_countdown)
        
    def apply_text_shadow(self, label):
        """Applies a shadow effect to the text, simulating an outline."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setOffset(0, 0)  # No offset for a centered outline
        shadow.setColor(QColor(0, 0, 0))  # Black shadow
        label.setGraphicsEffect(shadow)

    def start_countdown(self, duration):
        self.time_left = duration
        self.timer.start(1000)
        self.update_label()

    def reset_countdown(self):
        self.time_left = 0
        self.timer.stop()
        self.update_label("Ready")  # Reset to "Ready"

    def update_countdown(self):
        if self.time_left > 0:
            self.time_left -= 1
            self.update_label()
        else:
            self.reset_countdown()

    def update_label(self, text=None):
        if text:
            # Set color to limegreen when showing "Ready"
            self.text_label.setStyleSheet("color: limegreen; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 1px black;")
            self.text_label.setText(text)
        else:
            # Set color to white during countdown
            self.text_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 1px black;")
            minutes = self.time_left // 60
            seconds = self.time_left % 60
            self.text_label.setText(f"{minutes}:{seconds:02d}")

    # Mouse press event for dragging and right-click termination
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.close()
            QApplication.quit()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            event.accept()


class UserSelectionDialog(QDialog):
    def __init__(self, users, parent=None):
        super().__init__(parent)

        # Set the window title
        self.setWindowTitle("Undying Cooldown Overlay")

        # Remove the "?" help button from the title bar
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # Set a reasonable fixed size for the window
        self.setFixedSize(350, 150)

        # Layout
        layout = QVBoxLayout()

        if users:
            self.combo = QComboBox(self)
            self.combo.addItems(users)
            layout.addWidget(self.combo)

            self.button = QPushButton("Confirm", self)
            self.button.clicked.connect(self.accept)
            layout.addWidget(self.button)
        else:
            self.message_label = QLabel(self)
            self.message_label.setText(
                "No user folders found.\nPlease ensure that the 'Chat Logger' plugin is installed\n"
                "and the 'Game Chat' checkbox is ticked."
            )
            layout.addWidget(self.message_label)

            self.button = QPushButton("Close", self)
            self.button.clicked.connect(self.reject)
            layout.addWidget(self.button)

        self.setLayout(layout)


def get_users_folder():
    """Find the folders at the Jcode level that represent different users."""
    home_directory = os.path.expanduser("~")  # User's home directory
    log_base_path = os.path.join(home_directory, ".relicrsps", "chatlogs")

    if not os.path.exists(log_base_path):
        raise FileNotFoundError(f"Log directory not found at {log_base_path}")

    users = [folder for folder in os.listdir(log_base_path) if os.path.isdir(os.path.join(log_base_path, folder))]
    return log_base_path, users


def monitor_log_file(file_path, overlay):
    with open(file_path, 'r') as file:
        file.seek(0, 2)

        while True:
            line = file.readline()
            if line:
                if TARGET_STRING in line:
                    overlay.start_timer_signal.emit(180)  # 3-minute countdown
                elif RESET_STRING in line:
                    overlay.reset_timer_signal.emit()
            time.sleep(0.1)


def main():
    log_base_path, users = get_users_folder()

    app = QApplication(sys.argv)
    user_dialog = UserSelectionDialog(users)

    if user_dialog.exec_() == QDialog.Accepted and users:
        selected_user = user_dialog.combo.currentText()
        print(f"Selected user: {selected_user}")
    else:
        print("No users found or selection canceled.")
        return

    overlay = Overlay()
    overlay.show()

    log_file_path = os.path.join(log_base_path, selected_user, "game", "latest.log")
    monitor_thread = threading.Thread(target=monitor_log_file, args=(log_file_path, overlay))
    monitor_thread.daemon = True
    monitor_thread.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
