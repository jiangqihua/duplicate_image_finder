"""Main window for Duplicate Image Finder application."""

import logging
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QSlider, QFileDialog,
                             QMessageBox)
from PyQt6.QtCore import Qt, QThread, QTimer
from core.image_scanner import ImageScanner
from core.hash_calculator import HashCalculator
from core.file_manager import FileManager
from gui.widgets.image_group_viewer import ImageGroupViewer
from gui.widgets.progress_dialog import ProgressDialog
from utils.threading_utils import ScanWorker, GroupWorker, DeleteWorker
from utils.image_utils import ImageUtils
from config import WINDOW_SIZE, DEFAULT_THRESHOLD, MIN_THRESHOLD, MAX_THRESHOLD, REGROUP_DELAY_MS

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
        self.file_manager = FileManager()

        # Data
        self.image_hashes = []
        self.groups = []
        self.current_folder = ""

        # Worker threads
        self.scan_worker = None
        self.group_worker = None
        self.delete_worker = None
        self.progress_dialog = None

        # Operation state, see _update_controls()
        self.scanning = False
        self.deleting = False
        self.grouping_active = False
        self.pending_threshold = None  # Threshold to group with after the current run

        # Waits for the threshold slider to settle
        self.regroup_timer = QTimer(self)
        self.regroup_timer.setSingleShot(True)
        self.regroup_timer.setInterval(REGROUP_DELAY_MS)
        self.regroup_timer.timeout.connect(self._regroup)

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

        # Stop whatever is still running from earlier results
        self.regroup_timer.stop()
        self._cancel_grouping()
        self._wait_for_worker(self.scan_worker)

        # Clear previous results
        self.image_hashes = []
        self.groups = []
        self.image_viewer.clear()

        self.scanning = True
        self._update_controls()

        # Create progress dialog
        self.progress_dialog = ProgressDialog("Scanning Images", self)
        self.progress_dialog.rejected.connect(self._on_scan_cancelled)

        # Create and start worker thread
        self.scan_worker = ScanWorker(self.scanner, self.hash_calculator, folder_path)
        self.scan_worker.progress.connect(self.progress_dialog.update_progress)
        self.scan_worker.finished.connect(self.on_scan_complete)
        self.scan_worker.error.connect(self.on_scan_error)

        logger.info(f"Started scanning folder: {folder_path}")

        self.scan_worker.start()
        self.progress_dialog.show()

    def _on_scan_cancelled(self):
        """Handle the user cancelling a scan, during hashing or comparing."""
        self.scan_worker.cancel()
        self._cancel_grouping()
        self._close_progress_dialog()

        self.image_hashes = []
        self.groups = []
        self.scanning = False
        self._update_controls()

        self.status_label.setText("Scan cancelled.")
        logger.info("Scan cancelled by user")

    def on_scan_complete(self, image_hashes: List[Dict[str, Any]]):
        """
        Handle scan completion by starting the comparison stage.

        Args:
            image_hashes: List of image hash dictionaries
        """
        if self.scan_worker.cancelled:
            return

        self.image_hashes = image_hashes

        if not image_hashes:
            self._close_progress_dialog()
            self.scanning = False
            self._update_controls()
            self.status_label.setText("No images found in the selected folder.")
            return

        logger.info(f"Scan complete: {len(image_hashes)} images processed")

        self.status_label.setText(f"Processing {len(image_hashes)} images, finding duplicates...")
        self.progress_dialog.start_stage("Finding Duplicates")
        self._start_grouping(self.threshold_slider.value())

    def on_scan_error(self, error_message: str):
        """
        Handle scan error.

        Args:
            error_message: Error message
        """
        if self.scan_worker.cancelled:
            return

        self._close_progress_dialog()
        self.scanning = False
        self._update_controls()

        self.status_label.setText("Scan failed. Please try again.")
        logger.error(f"Scan error: {error_message}")

        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n\n{error_message}")

    def on_threshold_changed(self, value: int):
        """
        Handle threshold slider change.

        Args:
            value: New threshold value
        """
        self.threshold_label.setText(str(value))

        if self.image_hashes:
            self.regroup_timer.start()
            self._update_controls()

    def _regroup(self):
        """Regroup the existing hashes with the slider's threshold."""
        if not self.image_hashes:
            return

        self.status_label.setText("Finding duplicates with the new threshold...")
        self._start_grouping(self.threshold_slider.value())
        self._update_controls()

    def _start_grouping(self, threshold: int):
        """
        Group the current hashes, replacing any grouping that is still running.

        Args:
            threshold: Maximum weighted hash distance for similarity
        """
        if self.grouping_active:
            # on_grouping_complete() starts the new run when the old one stops
            self.pending_threshold = threshold
            self.group_worker.cancel()
            return

        self.pending_threshold = None
        self.grouping_active = True

        self._wait_for_worker(self.group_worker)
        self.group_worker = GroupWorker(self.image_hashes, threshold)
        self.group_worker.progress.connect(self._on_grouping_progress)
        self.group_worker.finished.connect(self.on_grouping_complete)
        self.group_worker.error.connect(self.on_grouping_error)
        self.group_worker.start()

    def _cancel_grouping(self):
        """Stop any running grouping and discard its result."""
        self.pending_threshold = None
        if self.grouping_active:
            self.group_worker.cancel()

    def _on_grouping_progress(self, percent: int, total: int, message: str):
        """
        Show grouping progress.

        Args:
            percent: Percentage done
            total: Always 100
            message: Progress message
        """
        if self.progress_dialog:
            self.progress_dialog.update_progress(percent, total, message)
        elif not self.group_worker.cancelled:
            self.status_label.setText(f"{message}... {percent}%")

    def on_grouping_complete(self, groups: Optional[List[List[Dict[str, Any]]]]):
        """
        Handle the end of a grouping run.

        Args:
            groups: The groups, or None if the run was cancelled
        """
        self.grouping_active = False

        if self.pending_threshold is not None:
            self._start_grouping(self.pending_threshold)
            return

        if groups is None or self.group_worker.cancelled:
            self._update_controls()
            return

        was_scanning = self.scanning
        self.scanning = False
        self._close_progress_dialog()

        self.groups = groups
        self.image_viewer.set_groups(groups)
        self._update_controls()

        # Update status
        stats = self.image_viewer.get_stats()
        if stats['total_groups'] > 0:
            self.status_label.setText(
                f"Found {stats['total_groups']} groups with {stats['total_images']} duplicate images"
            )
        elif was_scanning:
            self.status_label.setText(f"No duplicates found among {len(self.image_hashes)} images")
        else:
            self.status_label.setText("No duplicates found with current threshold")

        logger.info(f"Found {stats['total_groups']} groups with {stats['total_images']} images")

    def on_grouping_error(self, error_message: str):
        """
        Handle grouping error.

        Args:
            error_message: Error message
        """
        self.grouping_active = False
        self.pending_threshold = None
        self.scanning = False
        self._close_progress_dialog()
        self._update_controls()

        self.status_label.setText("Finding duplicates failed. Please try again.")
        logger.error(f"Grouping error: {error_message}")

        QMessageBox.critical(self, "Error", f"An error occurred while finding duplicates:\n\n{error_message}")

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

        self.deleting = True
        self._update_controls()

        # Create progress dialog
        self.progress_dialog = ProgressDialog("Deleting Images", self)
        self.progress_dialog.set_cancelable(False)  # Don't allow canceling deletion

        # Create and start delete worker
        self.delete_worker = DeleteWorker(self.file_manager, selected_paths, use_trash=True)
        self.delete_worker.progress.connect(self.progress_dialog.update_progress)
        self.delete_worker.finished.connect(self.on_delete_complete)
        self.delete_worker.error.connect(self.on_delete_error)

        logger.info(f"Started deleting {len(selected_paths)} files")

        self.delete_worker.start()
        self.progress_dialog.show()

    def on_delete_complete(self, results: Dict[str, Any]):
        """
        Handle deletion completion.

        Args:
            results: Dictionary with deletion results
        """
        self._close_progress_dialog()

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

            # Update only the affected groups (fast, no recomputation!)
            self.groups = self.image_viewer.remove_images(deleted_paths)

            # Update status
            stats = self.image_viewer.get_stats()
            if stats['total_groups'] > 0:
                self.status_label.setText(
                    f"Deleted {success_count} images. "
                    f"Found {stats['total_groups']} groups with {stats['total_images']} duplicates remaining."
                )
            else:
                self.status_label.setText(f"Deleted {success_count} images. No duplicates remaining.")

        self.deleting = False
        self._update_controls()

        logger.info(f"Deletion complete: {success_count} succeeded, {failed_count} failed")

    def on_delete_error(self, error_message: str):
        """
        Handle deletion error.

        Args:
            error_message: Error message
        """
        self._close_progress_dialog()

        QMessageBox.critical(self, "Deletion Error", f"An error occurred during deletion:\n\n{error_message}")

        self.status_label.setText("Deletion failed.")
        self.deleting = False
        self._update_controls()

        logger.error(f"Deletion error: {error_message}")

    def clear_results(self):
        """Clear all results and reset the view."""
        self.regroup_timer.stop()
        self._cancel_grouping()

        self.image_hashes = []
        self.groups = []
        self.image_viewer.clear()
        self.status_label.setText("Results cleared. Ready to scan.")
        self._update_controls()

        logger.info("Results cleared")

    def _update_controls(self):
        """Enable the controls that are valid for the current state."""
        busy = self.scanning or self.deleting
        regrouping = self.grouping_active or self.regroup_timer.isActive()
        can_act_on_groups = bool(self.groups) and not busy and not regrouping

        self.scan_button.setEnabled(not busy)
        self.threshold_slider.setEnabled(not busy)
        self.clear_button.setEnabled(bool(self.image_hashes) and not busy)
        self.delete_button.setEnabled(can_act_on_groups)
        self.keep_best_all_button.setEnabled(can_act_on_groups)

    def _close_progress_dialog(self):
        """Close the current progress dialog because its operation ended."""
        if self.progress_dialog:
            self.progress_dialog.finish()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

    @staticmethod
    def _wait_for_worker(worker: Optional[QThread]):
        """
        Wait for a stopping worker: destroying a running QThread aborts the app.

        Args:
            worker: The worker, if there is one
        """
        if worker is not None:
            worker.wait()

    def closeEvent(self, event):
        """Stop background work before the window closes."""
        self.regroup_timer.stop()
        self._cancel_grouping()
        if self.scan_worker is not None:
            self.scan_worker.cancel()

        for worker in (self.scan_worker, self.group_worker, self.delete_worker):
            self._wait_for_worker(worker)
        self.image_viewer.shutdown()

        super().closeEvent(event)

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
