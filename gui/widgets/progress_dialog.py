"""Progress dialog widget for long-running operations."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt


class ProgressDialog(QDialog):
    """Progress dialog for long-running operations."""

    def __init__(self, title: str, parent=None):
        """
        Initialize progress dialog.

        Args:
            title: Dialog title
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        self.cancel_button = None
        self.progress_bar = None
        self.message_label = None
        self.cancelled = False

        self.init_ui()

    def init_ui(self):
        """Create dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Message label
        self.message_label = QLabel("Initializing...")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_button)

    def update_progress(self, current: int, total: int, message: str = ""):
        """
        Update progress bar and message.

        Args:
            current: Current progress value
            total: Total progress value
            message: Progress message to display
        """
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_bar.setMaximum(100)

            if message:
                self.message_label.setText(f"{message} ({current}/{total})")
            else:
                self.message_label.setText(f"Progress: {current}/{total}")
        else:
            # Indeterminate progress
            self.progress_bar.setMaximum(0)
            if message:
                self.message_label.setText(message)

    def set_cancelable(self, cancelable: bool):
        """
        Enable/disable cancel button.

        Args:
            cancelable: Whether the operation can be cancelled
        """
        self.cancel_button.setEnabled(cancelable)

    def _on_cancel(self):
        """Handle cancel button click."""
        self.cancelled = True
        self.message_label.setText("Cancelling...")
        self.cancel_button.setEnabled(False)
        self.reject()

    def is_cancelled(self) -> bool:
        """
        Check if user cancelled the operation.

        Returns:
            True if cancelled, False otherwise
        """
        return self.cancelled

    def closeEvent(self, event):
        """Handle dialog close event."""
        if not self.cancelled:
            self._on_cancel()
        event.accept()
