"""Image group viewer widget for displaying groups of similar images."""

import subprocess
import sys
from typing import List, Dict, Any
from PyQt6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QPushButton, QLabel)
from PyQt6.QtCore import Qt
from gui.widgets.image_card import ImageCard
from core.similarity_detector import SimilarityDetector
from config import MAX_IMAGES_PER_ROW


class ImageGroupViewer(QScrollArea):
    """Displays groups of similar images."""

    def __init__(self, parent=None):
        """
        Initialize image group viewer.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.groups = []
        self.group_widgets = []
        self.image_cards = []
        self.similarity_detector = SimilarityDetector()

        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container widget
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setSpacing(10)

        self.setWidget(self.container)

    def set_groups(self, groups: List[List[Dict[str, Any]]]):
        """
        Update displayed groups.

        Args:
            groups: List of groups, each group is a list of image dicts
        """
        # Clear existing widgets
        self.clear()

        self.groups = groups
        self.group_widgets = []
        self.image_cards = []

        if not groups:
            # Show "no duplicates found" message
            no_results_label = QLabel("No duplicate images found.")
            no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results_label.setStyleSheet("font-size: 14px; color: #666; padding: 50px;")
            self.container_layout.addWidget(no_results_label)
            return

        # Create widget for each group
        for group_index, group in enumerate(groups):
            group_widget = self.create_group_widget(group, group_index)
            self.group_widgets.append(group_widget)
            self.container_layout.addWidget(group_widget)

        # Add stretch at the end
        self.container_layout.addStretch()

    def create_group_widget(self, group: List[Dict[str, Any]], group_index: int) -> QWidget:
        """
        Create widget for a single group.

        Args:
            group: List of image dictionaries in this group
            group_index: Index of this group

        Returns:
            QGroupBox containing the group
        """
        # Calculate average similarity for this group
        similarity = self.similarity_detector._compute_group_similarity(group)

        # Create group box
        group_box = QGroupBox(f"Group {group_index + 1} - Similarity: {similarity:.0f}%")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #999;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #333;
            }
        """)

        group_layout = QVBoxLayout(group_box)

        # Add control buttons
        controls_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._select_all_in_group(group_index, True))

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._select_all_in_group(group_index, False))

        keep_best_btn = QPushButton("Keep Best Quality")
        keep_best_btn.clicked.connect(lambda: self._keep_best_in_group(group_index))
        keep_best_btn.setToolTip("Keep highest resolution image, select others for deletion")

        open_all_btn = QPushButton("Open All")
        open_all_btn.clicked.connect(lambda: self._open_all_in_group(group_index))
        open_all_btn.setToolTip("Open all images in this group with the system viewer")

        controls_layout.addWidget(select_all_btn)
        controls_layout.addWidget(deselect_all_btn)
        controls_layout.addWidget(keep_best_btn)
        controls_layout.addWidget(open_all_btn)
        controls_layout.addStretch()

        group_layout.addLayout(controls_layout)

        # Add image cards
        images_layout = QHBoxLayout()
        images_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        images_layout.setSpacing(10)

        group_cards = []
        for image_data in group:
            card = ImageCard(image_data)
            group_cards.append(card)
            images_layout.addWidget(card)

            # Add spacing after every MAX_IMAGES_PER_ROW images
            if len(group_cards) % MAX_IMAGES_PER_ROW == 0:
                # Create new row
                group_layout.addLayout(images_layout)
                images_layout = QHBoxLayout()
                images_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                images_layout.setSpacing(10)

        # Add remaining images
        if len(group_cards) % MAX_IMAGES_PER_ROW != 0:
            images_layout.addStretch()
            group_layout.addLayout(images_layout)

        self.image_cards.extend(group_cards)

        return group_box

    def _select_all_in_group(self, group_index: int, select: bool):
        """
        Select or deselect all images in a group.

        Args:
            group_index: Index of the group
            select: Whether to select (True) or deselect (False)
        """
        if group_index >= len(self.groups):
            return

        group = self.groups[group_index]
        group_size = len(group)

        # Calculate starting index for this group's cards
        start_index = sum(len(self.groups[i]) for i in range(group_index))

        for i in range(start_index, start_index + group_size):
            if i < len(self.image_cards):
                self.image_cards[i].set_selected(select)

    def _open_all_in_group(self, group_index: int):
        """
        Open all images in a group with the system default viewer.

        Args:
            group_index: Index of the group
        """
        if group_index >= len(self.groups):
            return

        paths = [img['path'] for img in self.groups[group_index]]
        if sys.platform == 'darwin':
            subprocess.Popen(['open'] + paths)
        elif sys.platform == 'win32':
            for path in paths:
                subprocess.Popen(['start', '', path], shell=True)
        else:
            for path in paths:
                subprocess.Popen(['xdg-open', path])

    def _keep_best_in_group(self, group_index: int):
        """
        Keep the best quality image, select others for deletion.

        Args:
            group_index: Index of the group
        """
        if group_index >= len(self.groups):
            return

        group = self.groups[group_index]
        group_size = len(group)

        # Calculate starting index for this group's cards
        start_index = sum(len(self.groups[i]) for i in range(group_index))

        # First image is already sorted as best quality (highest resolution, etc.)
        # Deselect first image (keep it), select others (delete them)
        for i in range(start_index, start_index + group_size):
            if i < len(self.image_cards):
                is_first = (i == start_index)
                self.image_cards[i].set_selected(not is_first)

    def keep_best_in_all_groups(self, min_similarity: float = 100.0) -> int:
        """
        Apply 'Keep Best Quality' to groups with 100% similarity only.

        This will deselect the best quality image in each 100% match group
        and select all others for deletion. Only processes groups with similarity
        >= min_similarity (default 100%).

        Args:
            min_similarity: Minimum similarity percentage (0-100) to process group

        Returns:
            Number of groups processed
        """
        processed_count = 0

        for group_index in range(len(self.groups)):
            # Calculate similarity for this group
            group = self.groups[group_index]
            similarity = self.similarity_detector._compute_group_similarity(group)

            # Only process groups with 100% similarity (exact matches)
            if similarity >= min_similarity:
                self._keep_best_in_group(group_index)
                processed_count += 1

        return processed_count

    def get_selected_images(self) -> List[str]:
        """
        Get list of selected image paths.

        Returns:
            List of selected image file paths
        """
        selected = []
        for card in self.image_cards:
            if card.is_selected():
                selected.append(card.get_path())
        return selected

    def clear(self):
        """Clear all groups and widgets."""
        # Remove all widgets from layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.groups = []
        self.group_widgets = []
        self.image_cards = []

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about current groups.

        Returns:
            Dictionary with statistics
        """
        total_images = sum(len(group) for group in self.groups)
        total_groups = len(self.groups)
        selected_count = len(self.get_selected_images())

        return {
            'total_groups': total_groups,
            'total_images': total_images,
            'selected_count': selected_count
        }
