import datetime
import os
import sys
import threading
import time

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# The string to detect for starting and resetting the cooldown
TARGET_STRING = "Your Undying Retribution Relic saves your life. The Relic has lost power for 3 minutes."
RESET_STRING = "Your Undying Retribution relic is now ready."  # String that resets the cooldown


class Overlay(QWidget):
    start_timer_signal = pyqtSignal(int)  # Signal to start the timer from another thread
    reset_timer_signal = pyqtSignal()     # Signal to reset the timer from another thread

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(52, 20, 150, 60)
        self.layout = QVBoxLayout()

        # Add a background with transparency
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border: 1px solid white;")

        self.label = QLabel("Undying Ready")
        self.label.setStyleSheet("QLabel { color: white; font-size: 24px; }")  # White text for readability
        self.layout.addWidget(self.label)

        self.setLayout(self.layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.time_left = 0
        self.last_triggered = None  # Track the last time the message was detected

        # Variables for dragging
        self.is_dragging = False
        self.drag_start_position = QPoint()

        # Connect the signals to their respective slots
        self.start_timer_signal.connect(self.start_countdown)
        self.reset_timer_signal.connect(self.reset_countdown)

    def start_countdown(self, duration):
        current_time = datetime.datetime.now()

        # Always reset and start the timer, even if it's already running
        self.time_left = duration
        self.last_triggered = current_time
        self.label.setText(f"Undying cooldown: {self.time_left // 60}:{self.time_left % 60:02d}")
        self.timer.start(1000)  # Update every second

    def reset_countdown(self):
        # Immediately reset the countdown timer
        print("Timer is being reset...")
        self.time_left = 0
        self.timer.stop()
        self.label.setText("Relic Power Restored")

    def update_countdown(self):
        if self.time_left > 0:
            self.time_left -= 1
            minutes = self.time_left // 60
            seconds = self.time_left % 60
            self.label.setText(f"Undying cooldown: {minutes}:{seconds:02d}")
        else:
            self.timer.stop()
            self.label.setText("Relic Power Restored")

    # Mouse press event for dragging and right-click termination
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Close the overlay before quitting
            self.close()  # Close the overlay window
            QApplication.quit()  # Exit the application

    # Mouse move event for dragging
    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()

    # Mouse release event to stop dragging
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
        self.setFixedSize(350, 150)  # (Width, Height)

        # Layout
        layout = QVBoxLayout()

        if users:
            # Create a dropdown (QComboBox) for users
            self.combo = QComboBox(self)
            self.combo.addItems(users)
            layout.addWidget(self.combo)

            # Button to confirm selection
            self.button = QPushButton("Confirm", self)
            self.button.clicked.connect(self.accept)  # Close dialog on button press
            layout.addWidget(self.button)
        else:
            # Display message about missing plugin if no users found
            self.message_label = QLabel(self)
            self.message_label.setText(
                "No user folders found.\nPlease ensure that the 'Chat Logger' plugin is installed\n"
                "and the 'Game Chat' checkbox is ticked."
            )
            layout.addWidget(self.message_label)

            # Button to close dialog
            self.button = QPushButton("Close", self)
            self.button.clicked.connect(self.reject)  # Close dialog on button press
            layout.addWidget(self.button)

        self.setLayout(layout)


def get_users_folder():
    """Find the folders at the Jcode level that represent different users."""
    home_directory = os.path.expanduser("~")  # User's home directory
    log_base_path = os.path.join(home_directory, ".relicrsps", "chatlogs")

    # Check if the base path exists
    if not os.path.exists(log_base_path):
        raise FileNotFoundError(f"Log directory not found at {log_base_path}")

    # List directories in the log base path (these are the usernames)
    users = [folder for folder in os.listdir(log_base_path) if os.path.isdir(os.path.join(log_base_path, folder))]
    return log_base_path, users


def monitor_log_file(file_path, overlay):
    with open(file_path, 'r') as file:
        # Move to the end of the file
        file.seek(0, 2)

        while True:
            line = file.readline()
            if line:
                if TARGET_STRING in line:
                    # Emit signal to start the timer in the main thread
                    overlay.start_timer_signal.emit(180)  # 3-minute countdown
                elif RESET_STRING in line:
                    # Emit signal to reset the timer in the main thread
                    print("Resetting cooldown due to relic reset message.")
                    overlay.reset_timer_signal.emit()  # Use signal to reset timer
            time.sleep(0.1)  # Small delay to prevent CPU overuse


def main():
    # Get the users folder and list of usernames
    log_base_path, users = get_users_folder()

    # Initialize the QApplication
    app = QApplication(sys.argv)

    # Prompt the user to select a username
    user_dialog = UserSelectionDialog(users)

    if user_dialog.exec_() == QDialog.Accepted and users:
        selected_user = user_dialog.combo.currentText()
        print(f"Selected user: {selected_user}")
    else:
        print("No users found or selection canceled.")
        return

    # Create the overlay and start the monitoring for the selected user
    overlay = Overlay()
    overlay.show()

    # Construct the log path for the selected user
    log_file_path = os.path.join(log_base_path, selected_user, "game", "latest.log")

    # Start monitoring the log file in a separate thread
    monitor_thread = threading.Thread(target=monitor_log_file, args=(log_file_path, overlay))
    monitor_thread.daemon = True  # Daemon thread so it exits with the main program
    monitor_thread.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
