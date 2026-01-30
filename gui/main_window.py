"""Main window for Duplicate Image Finder application."""

import logging
from typing import List, Dict, Any
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QSlider, QFileDialog,
                             QMessageBox)
from PyQt6.QtCore import Qt
from core.image_scanner import ImageScanner
from core.hash_calculator import HashCalculator
from core.similarity_detector import SimilarityDetector
from core.file_manager import FileManager
from gui.widgets.image_group_viewer import ImageGroupViewer
from gui.widgets.progress_dialog import ProgressDialog
from utils.threading_utils import ScanWorker, DeleteWorker
from utils.image_utils import ImageUtils
from config import WINDOW_SIZE, DEFAULT_THRESHOLD, MIN_THRESHOLD, MAX_THRESHOLD

logger = logging.getLogger(__name__)
image_utils = ImageUtils()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()

        # Core components
        self.scanner = ImageScanner()
        self.hash_calculator = HashCalculator()
        self.similarity_detector = SimilarityDetector()
        self.file_manager = FileManager()

        # Data
        self.image_hashes = []
        self.groups = []
        self.current_folder = ""

        # Worker threads
        self.scan_worker = None
        self.delete_worker = None
        self.progress_dialog = None

        # UI components
        self.folder_input = None
        self.threshold_slider = None
        self.threshold_label = None
        self.status_label = None
        self.image_viewer = None
        self.scan_button = None
        self.delete_button = None
        self.clear_button = None
        self.keep_best_all_button = None

        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Duplicate Image Finder")
        self.resize(*WINDOW_SIZE)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Folder selection section
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Folder:")
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select a folder to scan...")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_folder)

        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(browse_button)

        main_layout.addLayout(folder_layout)

        # Threshold slider section
        threshold_layout = QHBoxLayout()
        threshold_title = QLabel("Similarity Threshold:")

        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(MIN_THRESHOLD)
        self.threshold_slider.setMaximum(MAX_THRESHOLD)
        self.threshold_slider.setValue(DEFAULT_THRESHOLD)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(5)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)

        self.threshold_label = QLabel(f"{DEFAULT_THRESHOLD}")
        self.threshold_label.setMinimumWidth(30)

        hint_label = QLabel("(Lower = Stricter, Higher = More Lenient)")
        hint_label.setStyleSheet("color: #666; font-size: 10px;")

        threshold_layout.addWidget(threshold_title)
        threshold_layout.addWidget(self.threshold_slider, 1)
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addWidget(hint_label)

        main_layout.addLayout(threshold_layout)

        # Action buttons section
        buttons_layout = QHBoxLayout()

        self.scan_button = QPushButton("Scan Folder")
        self.scan_button.clicked.connect(self.scan_folder)
        self.scan_button.setStyleSheet("font-weight: bold; padding: 8px;")

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("padding: 8px;")

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_results)
        self.clear_button.setEnabled(False)
        self.clear_button.setStyleSheet("padding: 8px;")

        self.keep_best_all_button = QPushButton("Keep Best (100% Match Only)")
        self.keep_best_all_button.clicked.connect(self.keep_best_in_all_groups)
        self.keep_best_all_button.setEnabled(False)
        self.keep_best_all_button.setStyleSheet("padding: 8px; background-color: #4CAF50; color: white;")
        self.keep_best_all_button.setToolTip("Auto-select duplicates in groups with 100% similarity (exact matches only)")

        buttons_layout.addWidget(self.scan_button)
        buttons_layout.addWidget(self.keep_best_all_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addStretch()

        main_layout.addLayout(buttons_layout)

        # Status label
        self.status_label = QLabel("Ready. Select a folder and click 'Scan Folder' to begin.")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

        # Image viewer
        self.image_viewer = ImageGroupViewer()
        main_layout.addWidget(self.image_viewer, 1)

        logger.info("Main window initialized")

    def browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Scan",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            self.folder_input.setText(folder)
            self.current_folder = folder

    def scan_folder(self):
        """Start scanning folder for duplicate images."""
        folder_path = self.folder_input.text().strip()

        if not folder_path:
            QMessageBox.warning(self, "No Folder Selected", "Please select a folder to scan.")
            return

        # Clear previous results
        self.image_hashes = []
        self.groups = []
        self.image_viewer.clear()

        # Disable controls
        self.scan_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.threshold_slider.setEnabled(False)

        # Create progress dialog
        self.progress_dialog = ProgressDialog("Scanning Images", self)

        # Create and start worker thread
        self.scan_worker = ScanWorker(self.scanner, self.hash_calculator, folder_path)
        self.scan_worker.progress.connect(self.progress_dialog.update_progress)
        self.scan_worker.finished.connect(self.on_scan_complete)
        self.scan_worker.error.connect(self.on_scan_error)

        self.progress_dialog.rejected.connect(self._on_scan_cancelled)

        self.scan_worker.start()
        self.progress_dialog.exec()

        logger.info(f"Started scanning folder: {folder_path}")

    def _on_scan_cancelled(self):
        """Handle scan cancellation by the user."""
        self.scan_worker.cancel()
        self.scan_button.setEnabled(True)
        self.status_label.setText("Scan cancelled.")
        logger.info("Scan cancelled by user")

    def on_scan_complete(self, image_hashes: List[Dict[str, Any]]):
        """
        Handle scan completion.

        Args:
            image_hashes: List of image hash dictionaries
        """
        self.progress_dialog.close()

        self.image_hashes = image_hashes

        if not image_hashes:
            self.status_label.setText("No images found in the selected folder.")
            self.scan_button.setEnabled(True)
            return

        logger.info(f"Scan complete: {len(image_hashes)} images processed")

        # Update status
        self.status_label.setText(f"Processing {len(image_hashes)} images, finding duplicates...")

        # Create progress dialog for similarity comparison
        comparison_progress = ProgressDialog("Finding Duplicates", self)
        comparison_progress.set_cancelable(False)
        comparison_progress.show()

        # Process events to show the dialog
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # Find similar groups with progress callback
        threshold = self.threshold_slider.value()
        self.similarity_detector.threshold = threshold
        self.groups = self.similarity_detector.find_similar_groups(
            image_hashes,
            progress_callback=lambda curr, total, msg: self._update_comparison_progress(
                comparison_progress, curr, total, msg
            )
        )

        # Close progress dialog
        comparison_progress.close()

        # Display results
        self.image_viewer.set_groups(self.groups)

        # Update status
        stats = self.image_viewer.get_stats()
        if stats['total_groups'] > 0:
            self.status_label.setText(
                f"Found {stats['total_groups']} groups with {stats['total_images']} duplicate images"
            )
            self.delete_button.setEnabled(True)
            self.clear_button.setEnabled(True)
            self.keep_best_all_button.setEnabled(True)
        else:
            self.status_label.setText(f"No duplicates found among {len(image_hashes)} images")
            self.keep_best_all_button.setEnabled(False)

        # Re-enable controls
        self.scan_button.setEnabled(True)
        self.threshold_slider.setEnabled(True)

        logger.info(f"Found {stats['total_groups']} groups with {stats['total_images']} images")

    def on_scan_error(self, error_message: str):
        """
        Handle scan error.

        Args:
            error_message: Error message
        """
        self.progress_dialog.close()

        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n\n{error_message}")

        self.status_label.setText("Scan failed. Please try again.")
        self.scan_button.setEnabled(True)

        logger.error(f"Scan error: {error_message}")

    def on_threshold_changed(self, value: int):
        """
        Handle threshold slider change.

        Args:
            value: New threshold value
        """
        self.threshold_label.setText(str(value))

        # If we have image hashes, recompute groups
        if self.image_hashes:
            self.similarity_detector.threshold = value

            # Show progress dialog for large image sets
            if len(self.image_hashes) > 100:
                comparison_progress = ProgressDialog("Recomputing Groups", self)
                comparison_progress.set_cancelable(False)
                comparison_progress.show()

                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()

                self.groups = self.similarity_detector.update_threshold(
                    value,
                    progress_callback=lambda curr, total, msg: self._update_comparison_progress(
                        comparison_progress, curr, total, msg
                    )
                )

                comparison_progress.close()
            else:
                # Small dataset, no need for progress dialog
                self.groups = self.similarity_detector.update_threshold(value)

            self.image_viewer.set_groups(self.groups)

            # Update status
            stats = self.image_viewer.get_stats()
            if stats['total_groups'] > 0:
                self.status_label.setText(
                    f"Found {stats['total_groups']} groups with {stats['total_images']} duplicate images"
                )
                self.delete_button.setEnabled(True)
                self.keep_best_all_button.setEnabled(True)
            else:
                self.status_label.setText(f"No duplicates found with current threshold")
                self.delete_button.setEnabled(False)
                self.keep_best_all_button.setEnabled(False)

    def delete_selected(self):
        """Delete selected images."""
        selected_paths = self.image_viewer.get_selected_images()

        if not selected_paths:
            QMessageBox.information(self, "No Selection", "Please select images to delete.")
            return

        # Calculate total size
        total_size = self.file_manager.calculate_total_size(selected_paths)
        size_str = image_utils.format_file_size(total_size)

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_paths)} selected image(s)?\n\n"
            f"Total size: {size_str}\n\n"
            f"Images will be moved to trash (not permanently deleted).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable controls
        self.delete_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.clear_button.setEnabled(False)

        # Create progress dialog
        self.progress_dialog = ProgressDialog("Deleting Images", self)
        self.progress_dialog.set_cancelable(False)  # Don't allow canceling deletion

        # Create and start delete worker
        self.delete_worker = DeleteWorker(self.file_manager, selected_paths, use_trash=True)
        self.delete_worker.progress.connect(self.progress_dialog.update_progress)
        self.delete_worker.finished.connect(self.on_delete_complete)
        self.delete_worker.error.connect(self.on_delete_error)

        self.delete_worker.start()
        self.progress_dialog.exec()

        logger.info(f"Started deleting {len(selected_paths)} files")

    def on_delete_complete(self, results: Dict[str, Any]):
        """
        Handle deletion completion.

        Args:
            results: Dictionary with deletion results
        """
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()

        success_count = len(results['success'])
        failed_count = len(results['failed'])

        # Show results
        if failed_count == 0:
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {success_count} image(s)."
            )
        else:
            error_details = "\n".join([f"{path}: {error}" for path, error in results['failed'][:5]])
            if failed_count > 5:
                error_details += f"\n... and {failed_count - 5} more"

            QMessageBox.warning(
                self,
                "Deletion Completed with Errors",
                f"Successfully deleted {success_count} image(s).\n"
                f"Failed to delete {failed_count} image(s).\n\n"
                f"Errors:\n{error_details}"
            )

        # Refresh the view by removing deleted images
        if success_count > 0:
            deleted_paths = set(results['success'])

            # Remove deleted images from image_hashes
            self.image_hashes = [img for img in self.image_hashes if img['path'] not in deleted_paths]

            # Filter deleted images from existing groups (fast, no recomputation!)
            if self.groups:
                # Remove deleted images from each group
                filtered_groups = []
                for group in self.groups:
                    filtered_group = [img for img in group if img['path'] not in deleted_paths]
                    # Keep groups that still have duplicates (2+ images)
                    if len(filtered_group) > 1:
                        filtered_groups.append(filtered_group)

                self.groups = filtered_groups
                self.image_viewer.set_groups(self.groups)

                # Update status
                stats = self.image_viewer.get_stats()
                if stats['total_groups'] > 0:
                    self.status_label.setText(
                        f"Deleted {success_count} images. "
                        f"Found {stats['total_groups']} groups with {stats['total_images']} duplicates remaining."
                    )
                else:
                    self.status_label.setText(f"Deleted {success_count} images. No duplicates remaining.")
            else:
                self.clear_results()
                self.status_label.setText(f"Deleted {success_count} images. No images remaining.")

        # Re-enable controls
        self.scan_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        if self.image_viewer.get_stats()['total_groups'] > 0:
            self.delete_button.setEnabled(True)
            self.keep_best_all_button.setEnabled(True)
        else:
            self.keep_best_all_button.setEnabled(False)

        logger.info(f"Deletion complete: {success_count} succeeded, {failed_count} failed")

    def on_delete_error(self, error_message: str):
        """
        Handle deletion error.

        Args:
            error_message: Error message
        """
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()

        QMessageBox.critical(self, "Deletion Error", f"An error occurred during deletion:\n\n{error_message}")

        self.status_label.setText("Deletion failed.")
        self.scan_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.clear_button.setEnabled(True)

        logger.error(f"Deletion error: {error_message}")

    def clear_results(self):
        """Clear all results and reset the view."""
        self.image_hashes = []
        self.groups = []
        self.image_viewer.clear()
        self.status_label.setText("Results cleared. Ready to scan.")
        self.delete_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.keep_best_all_button.setEnabled(False)

        logger.info("Results cleared")

    def _update_comparison_progress(self, dialog, current, total, message):
        """
        Update comparison progress dialog and process events.

        Args:
            dialog: Progress dialog instance
            current: Current comparison count
            total: Total comparisons
            message: Progress message
        """
        dialog.update_progress(current, total, message)

        # Process events to keep UI responsive
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def keep_best_in_all_groups(self):
        """Apply 'Keep Best Quality' to groups with 100% similarity only."""
        if not self.groups:
            return

        # Apply keep best to 100% match groups only
        processed_count = self.image_viewer.keep_best_in_all_groups(min_similarity=100.0)

        # Update status with selection count
        selected_count = len(self.image_viewer.get_selected_images())
        stats = self.image_viewer.get_stats()

        if processed_count > 0:
            self.status_label.setText(
                f"Auto-selected {selected_count} images in {processed_count} exact match groups "
                f"(100% similarity, out of {stats['total_groups']} total groups)"
            )
        else:
            self.status_label.setText(
                f"No groups with 100% similarity found. "
                f"Use per-group 'Keep Best Quality' buttons for other matches."
            )

        logger.info(f"Applied 'Keep Best' to {processed_count}/{stats['total_groups']} groups (100% similarity), selected {selected_count} images")
