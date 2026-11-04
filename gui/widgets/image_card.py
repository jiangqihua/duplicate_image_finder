"""Image card widget for displaying individual images."""

import os
from datetime import datetime
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from utils.image_utils import ImageUtils


class ImageCard(QWidget):
    """Card displaying single image with metadata and selection checkbox."""

    selection_changed = pyqtSignal(str, bool)  # path, is_selected

    def __init__(self, image_data: Dict[str, Any], parent=None):
        """
        Initialize image card.

        Args:
            image_data: Dictionary with image information
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_data = image_data
        self.checkbox = None
        self.thumbnail_label = None
        self.init_ui()

    def init_ui(self):
        """Create card layout with thumbnail, info, and checkbox."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Checkbox for selection
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_selection_changed)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(200, 200)
        self.thumbnail_label.setMaximumSize(200, 200)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")

        # Filled in by set_thumbnail() once the background load finishes
        self.thumbnail_label.setText("Loading...")

        # File name
        filename = os.path.basename(self.image_data['path'])
        name_label = QLabel(filename)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(200)
        name_label.setToolTip(self.image_data['path'])
        name_label.setStyleSheet("font-weight: bold;")

        # File size
        file_size_str = ImageUtils.format_file_size(self.image_data['file_size'])
        size_label = QLabel(f"Size: {file_size_str}")
        size_label.setStyleSheet("color: #666;")

        # Dimensions
        dimensions_str = ImageUtils.format_dimensions(self.image_data['dimensions'])
        dim_label = QLabel(f"Dimensions: {dimensions_str}")
        dim_label.setStyleSheet("color: #666;")

        # Modification date
        mod_time = datetime.fromtimestamp(self.image_data['modified_time'])
        mod_str = mod_time.strftime("%Y-%m-%d %H:%M")
        mod_label = QLabel(f"Modified: {mod_str}")
        mod_label.setStyleSheet("color: #666; font-size: 10px;")

        # Add widgets to layout
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()
        checkbox_layout.addWidget(self.checkbox)
        checkbox_layout.addStretch()

        layout.addLayout(checkbox_layout)
        layout.addWidget(self.thumbnail_label)
        layout.addWidget(name_label)
        layout.addWidget(size_label)
        layout.addWidget(dim_label)
        layout.addWidget(mod_label)

        # Set fixed width for the card
        self.setFixedWidth(220)

    def set_thumbnail(self, pixmap: QPixmap):
        """
        Display a thumbnail.

        Args:
            pixmap: Thumbnail, null if it could not be loaded
        """
        if pixmap.isNull():
            self.thumbnail_label.setText("Failed to load\nthumbnail")
            return

        # Scale pixmap to fit label while maintaining aspect ratio
        self.thumbnail_label.setPixmap(pixmap.scaled(
            200, 200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def _on_selection_changed(self, state):
        """Handle selection checkbox state change."""
        is_selected = state == Qt.CheckState.Checked.value
        self.selection_changed.emit(self.image_data['path'], is_selected)

    def is_selected(self) -> bool:
        """
        Check if this image is selected.

        Returns:
            True if selected, False otherwise
        """
        return self.checkbox.isChecked()

    def set_selected(self, selected: bool):
        """
        Set selection state.

        Args:
            selected: Whether to select this image
        """
        self.checkbox.setChecked(selected)

    def get_path(self) -> str:
        """
        Get image file path.

        Returns:
            Image file path
        """
        return self.image_data['path']
