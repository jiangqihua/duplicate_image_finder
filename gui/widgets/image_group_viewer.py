"""Image group viewer widget for displaying groups of similar images."""

import subprocess
import sys
from typing import Iterable, List, Dict, Any
from PyQt6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QPushButton, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from gui.widgets.image_card import ImageCard
from core.similarity_detector import SimilarityDetector
from utils.image_utils import ImageUtils
from utils.threading_utils import ThumbnailLoader
from config import MAX_IMAGES_PER_ROW, GROUP_LOAD_BATCH, GROUP_LOAD_AHEAD_SCREENS

# One shared style sheet: setting a sheet on every card and group box is slow.
CONTAINER_STYLE = """
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
    ImageCard {
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: white;
        padding: 5px;
    }
    ImageCard:hover {
        border: 1px solid #999;
    }
"""


class ImageGroupViewer(QScrollArea):
    """
    Displays groups of similar images.

    Group widgets are only built as they get close to the visible area, so
    self.group_widgets always covers a prefix of self.groups. Selection is kept
    in self.selected_paths because images may not have a card yet.
    """

    def __init__(self, parent=None):
        """
        Initialize image group viewer.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.groups = []
        self.group_widgets = []
        self.cards_by_path = {}
        self.selected_paths = set()
        self.similarity_detector = SimilarityDetector()
        self.image_utils = ImageUtils()

        self.thumbnail_loader = ThumbnailLoader(self.image_utils, self)
        self.thumbnail_loader.loaded.connect(self._on_thumbnail_loaded)

        self.fill_timer = QTimer(self)
        self.fill_timer.setSingleShot(True)
        self.fill_timer.setInterval(10)
        self.fill_timer.timeout.connect(self._fill_viewport)

        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container widget
        self.container = QWidget()
        self.container.setStyleSheet(CONTAINER_STYLE)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setSpacing(10)
        self.container_layout.addStretch()

        self.setWidget(self.container)

        scroll_bar = self.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._schedule_fill)
        scroll_bar.rangeChanged.connect(self._schedule_fill)

    def resizeEvent(self, event):
        """Build more groups if the larger view needs them."""
        super().resizeEvent(event)
        self._schedule_fill()

    def set_groups(self, groups: List[List[Dict[str, Any]]]):
        """
        Update displayed groups.

        Args:
            groups: List of groups, each group is a list of image dicts
        """
        # Clear existing widgets
        self.clear()

        self.groups = groups

        if not groups:
            self._show_no_results()
            return

        self.verticalScrollBar().setValue(0)
        self._schedule_fill()

    def remove_images(self, paths: Iterable[str]) -> List[List[Dict[str, Any]]]:
        """
        Remove images, updating only the groups that contain them.

        Groups left with fewer than two images are removed entirely.

        Args:
            paths: Paths of the images to remove

        Returns:
            The remaining groups
        """
        removed = set(paths)
        new_groups = []
        new_widgets = []

        for index, group in enumerate(self.groups):
            widget = self.group_widgets[index] if index < len(self.group_widgets) else None
            remaining = [image for image in group if image['path'] not in removed]

            if len(remaining) == len(group):
                new_groups.append(group)
                if widget:
                    new_widgets.append(widget)
                continue

            # The group changes, so forget its cards and removed selections
            group_paths = {image['path'] for image in group}
            for path in group_paths:
                self.cards_by_path.pop(path, None)

            if len(remaining) > 1:
                self.selected_paths -= group_paths & removed
                new_groups.append(remaining)
                if widget:
                    new_widget = self.create_group_widget(remaining, len(new_groups) - 1)
                    self.container_layout.insertWidget(self.container_layout.indexOf(widget), new_widget)
                    new_widgets.append(new_widget)
            else:
                # The survivor is no longer a duplicate: never leave it selected
                self.selected_paths -= group_paths

            if widget:
                self._discard_widget(widget)

        self.groups = new_groups
        self.group_widgets = new_widgets

        for index, widget in enumerate(self.group_widgets):
            widget.setTitle(self._group_title(index, widget.similarity))

        if self.groups:
            self._schedule_fill()
        else:
            self._show_no_results()

        return self.groups

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
        group_box = QGroupBox(self._group_title(group_index, similarity))
        group_box.similarity = similarity

        group_layout = QVBoxLayout(group_box)

        # Add control buttons
        controls_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._select_all_in_group(group, True))

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._select_all_in_group(group, False))

        keep_best_btn = QPushButton("Keep Best Quality")
        keep_best_btn.clicked.connect(lambda: self._keep_best_in_group(group))
        keep_best_btn.setToolTip("Keep highest resolution image, select others for deletion")

        open_all_btn = QPushButton("Open All")
        open_all_btn.clicked.connect(lambda: self._open_all_in_group(group))
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

        for count, image_data in enumerate(group, start=1):
            images_layout.addWidget(self._create_card(image_data))

            # Add spacing after every MAX_IMAGES_PER_ROW images
            if count % MAX_IMAGES_PER_ROW == 0:
                # Create new row
                group_layout.addLayout(images_layout)
                images_layout = QHBoxLayout()
                images_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                images_layout.setSpacing(10)

        # Add remaining images
        if len(group) % MAX_IMAGES_PER_ROW != 0:
            images_layout.addStretch()
            group_layout.addLayout(images_layout)

        return group_box

    def _create_card(self, image_data: Dict[str, Any]) -> ImageCard:
        """
        Create the card for an image and start loading its thumbnail.

        Args:
            image_data: Dictionary with image information

        Returns:
            The new card
        """
        path = image_data['path']
        card = ImageCard(image_data)
        card.set_selected(path in self.selected_paths)
        card.selection_changed.connect(self._on_card_selection_changed)
        self.cards_by_path[path] = card

        pixmap = self.image_utils.get_cached_pixmap(path)
        if pixmap is not None:
            card.set_thumbnail(pixmap)
        else:
            self.thumbnail_loader.request(path)

        return card

    def _on_thumbnail_loaded(self, path: str, image: QImage):
        """
        Show a thumbnail that finished loading.

        Args:
            path: Path to the image
            image: Thumbnail, null if loading failed
        """
        pixmap = QPixmap.fromImage(image)
        if not pixmap.isNull():
            self.image_utils.cache_pixmap(path, pixmap)

        card = self.cards_by_path.get(path)
        if card:
            card.set_thumbnail(pixmap)

    def _on_card_selection_changed(self, path: str, selected: bool):
        """
        Record a selection made on a card.

        Args:
            path: Path to the image
            selected: Whether the image is now selected
        """
        if selected:
            self.selected_paths.add(path)
        else:
            self.selected_paths.discard(path)

    def _set_selected(self, path: str, selected: bool):
        """
        Set an image's selection, whether or not it has a card yet.

        Args:
            path: Path to the image
            selected: Whether to select the image
        """
        self._on_card_selection_changed(path, selected)
        card = self.cards_by_path.get(path)
        if card:
            card.set_selected(selected)

    def _select_all_in_group(self, group: List[Dict[str, Any]], select: bool):
        """
        Select or deselect all images in a group.

        Args:
            group: The group
            select: Whether to select (True) or deselect (False)
        """
        for image in group:
            self._set_selected(image['path'], select)

    def _open_all_in_group(self, group: List[Dict[str, Any]]):
        """
        Open all images in a group with the system default viewer.

        Args:
            group: The group
        """
        paths = [img['path'] for img in group]
        if sys.platform == 'darwin':
            subprocess.Popen(['open'] + paths)
        elif sys.platform == 'win32':
            for path in paths:
                subprocess.Popen(['start', '', path], shell=True)
        else:
            for path in paths:
                subprocess.Popen(['xdg-open', path])

    def _keep_best_in_group(self, group: List[Dict[str, Any]]):
        """
        Keep the best quality image, select others for deletion.

        Args:
            group: The group
        """
        # First image is already sorted as best quality (highest resolution, etc.)
        # Deselect first image (keep it), select others (delete them)
        for index, image in enumerate(group):
            self._set_selected(image['path'], index != 0)

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

        for group in self.groups:
            # Only process groups with 100% similarity (exact matches)
            if self.similarity_detector._compute_group_similarity(group) >= min_similarity:
                self._keep_best_in_group(group)
                processed_count += 1

        return processed_count

    def get_selected_images(self) -> List[str]:
        """
        Get list of selected image paths.

        Returns:
            List of selected image file paths
        """
        return [image['path'] for group in self.groups for image in group
                if image['path'] in self.selected_paths]

    def clear(self):
        """Clear all groups and widgets."""
        self.fill_timer.stop()
        self.thumbnail_loader.cancel_pending()

        # Remove all widgets from layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                self._discard_widget(item.widget())
        self.container_layout.addStretch()

        self.groups = []
        self.group_widgets = []
        self.cards_by_path = {}
        self.selected_paths = set()

    def shutdown(self):
        """Stop background work before the application exits."""
        self.fill_timer.stop()
        self.thumbnail_loader.shutdown()

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

    def _schedule_fill(self):
        """Check soon whether more groups need building."""
        if not self.fill_timer.isActive():
            self.fill_timer.start()

    def _fill_viewport(self):
        """Build the next few groups if the user is getting close to the end."""
        built = len(self.group_widgets)
        if built >= len(self.groups):
            return

        scroll_bar = self.verticalScrollBar()
        ahead = scroll_bar.maximum() - scroll_bar.value()
        if ahead > self.viewport().height() * GROUP_LOAD_AHEAD_SCREENS:
            return

        for index in range(built, min(built + GROUP_LOAD_BATCH, len(self.groups))):
            widget = self.create_group_widget(self.groups[index], index)
            self.group_widgets.append(widget)
            # The last layout item is the stretch
            self.container_layout.insertWidget(self.container_layout.count() - 1, widget)

        # Let the layout update and event loop run before building more
        self._schedule_fill()

    def _show_no_results(self):
        """Show the "no duplicates found" message."""
        no_results_label = QLabel("No duplicate images found.")
        no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results_label.setStyleSheet("font-size: 14px; color: #666; padding: 50px;")
        self.container_layout.insertWidget(0, no_results_label)

    @staticmethod
    def _discard_widget(widget: QWidget):
        """
        Remove a widget from view now and delete it once it is safe to.

        Args:
            widget: The widget
        """
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()

    @staticmethod
    def _group_title(group_index: int, similarity: float) -> str:
        """
        Get a group's title.

        Args:
            group_index: Index of the group
            similarity: Similarity percentage of the group

        Returns:
            The title
        """
        return f"Group {group_index + 1} - Similarity: {similarity:.0f}%"
