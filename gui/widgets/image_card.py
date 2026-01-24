"""Image card widget for displaying individual images."""

import os
from datetime import datetime
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from utils.image_utils import ImageUtils

image_utils = ImageUtils()


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

        # Load thumbnail (lazy loading)
        self.load_thumbnail()

        # File name
        filename = os.path.basename(self.image_data['path'])
        name_label = QLabel(filename)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(200)
        name_label.setToolTip(self.image_data['path'])
        name_label.setStyleSheet("font-weight: bold;")

        # File size
        file_size_str = image_utils.format_file_size(self.image_data['file_size'])
        size_label = QLabel(f"Size: {file_size_str}")
        size_label.setStyleSheet("color: #666;")

        # Dimensions
        dimensions_str = image_utils.format_dimensions(self.image_data['dimensions'])
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
        self.setStyleSheet("""
            ImageCard {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
                padding: 5px;
            }
            ImageCard:hover {
                border: 1px solid #999;
            }
        """)

    def load_thumbnail(self):
        """Load and display thumbnail."""
        try:
            pixmap = image_utils.create_thumbnail(self.image_data['path'])

            if not pixmap.isNull():
                # Scale pixmap to fit label while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    200, 200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.thumbnail_label.setText("Failed to load\nthumbnail")
        except Exception as e:
            self.thumbnail_label.setText("Error loading\nthumbnail")

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
