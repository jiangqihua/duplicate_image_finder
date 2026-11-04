"""Threading utilities for background task execution."""

import logging
from typing import Callable, Any, List, Dict
from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage
from core.similarity_detector import SimilarityDetector
from utils.image_utils import ImageUtils
from config import MAX_WORKER_THREADS

logger = logging.getLogger(__name__)


class WorkerThread(QThread):
    """Generic worker thread for long-running tasks."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(object)  # result
    error = pyqtSignal(str)  # error message

    def __init__(self, task_func: Callable, *args, **kwargs):
        """
        Initialize worker thread.

        Args:
            task_func: Function to execute in background
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.cancelled = False
        self._result = None

    def run(self):
        """Execute task in background."""
        try:
            logger.info(f"Worker thread started: {self.task_func.__name__}")

            # Execute the task
            self._result = self.task_func(*self.args, **self.kwargs)

            if not self.cancelled:
                self.finished.emit(self._result)
                logger.info(f"Worker thread completed: {self.task_func.__name__}")

        except Exception as e:
            error_msg = f"Error in worker thread: {e}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)

    def cancel(self):
        """Cancel running task."""
        self.cancelled = True
        logger.info(f"Worker thread cancelled: {self.task_func.__name__}")

    def get_result(self) -> Any:
        """
        Get the result of the task.

        Returns:
            Task result
        """
        return self._result


class ScanWorker(QThread):
    """Worker thread specifically for scanning and hashing images."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list)  # list of image hashes
    error = pyqtSignal(str)  # error message

    def __init__(self, scanner, hash_calculator, folder_path: str):
        """
        Initialize scan worker.

        Args:
            scanner: ImageScanner instance
            hash_calculator: HashCalculator instance
            folder_path: Path to scan
        """
        super().__init__()
        self.scanner = scanner
        self.hash_calculator = hash_calculator
        self.folder_path = folder_path
        self.cancelled = False

    def run(self):
        """Execute scanning and hashing."""
        try:
            logger.info(f"Starting scan of {self.folder_path}")

            # Scan for images
            image_paths = self.scanner.scan_folder(
                self.folder_path,
                recursive=True,
                progress_callback=self._scan_progress
            )

            if self.cancelled:
                return

            if not image_paths:
                self.error.emit("No images found in the selected folder")
                return

            logger.info(f"Found {len(image_paths)} images, computing hashes...")

            # Compute hashes
            image_hashes = self.hash_calculator.compute_batch(
                image_paths,
                progress_callback=self._hash_progress
            )

            if not self.cancelled:
                self.finished.emit(image_hashes)
                logger.info(f"Scan completed: {len(image_hashes)} images processed")

        except Exception as e:
            error_msg = f"Error during scan: {e}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)

    def _scan_progress(self, count: int, file_path: str):
        """
        Callback for scan progress.

        Args:
            count: Number of images found so far
            file_path: Current file being scanned
        """
        if self.cancelled:
            self.scanner.cancel()  # scan_folder() resets the flag when it starts
            return

        import os
        filename = os.path.basename(file_path)
        self.progress.emit(count, 0, f"Scanning: {filename}")

    def _hash_progress(self, current: int, total: int, message: str):
        """
        Callback for hash computation progress.

        Args:
            current: Current image index
            total: Total number of images
            message: Progress message
        """
        if self.cancelled:
            self.hash_calculator.cancel()  # compute_batch() resets the flag when it starts
            return

        self.progress.emit(current, total, message)

    def cancel(self):
        """Cancel the scan operation."""
        self.cancelled = True
        self.scanner.cancel()
        self.hash_calculator.cancel()
        logger.info("Scan worker cancelled")


class GroupWorker(QThread):
    """Worker thread for grouping already-hashed images by similarity."""

    progress = pyqtSignal(int, int, str)  # percent, 100, message
    finished = pyqtSignal(object)  # list of groups, or None if cancelled
    error = pyqtSignal(str)  # error message

    def __init__(self, image_hashes: List[Dict[str, Any]], threshold: int):
        """
        Initialize group worker.

        Args:
            image_hashes: List of image hash dictionaries
            threshold: Maximum weighted hash distance for similarity
        """
        super().__init__()
        self.image_hashes = image_hashes
        self.detector = SimilarityDetector(threshold)
        self.cancelled = False

    def run(self):
        """Execute grouping."""
        try:
            groups = self.detector.find_similar_groups(
                self.image_hashes,
                progress_callback=self._on_progress
            )
            self.finished.emit(None if self.cancelled else groups)

        except Exception as e:
            error_msg = f"Error while grouping images: {e}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)

    def _on_progress(self, current: int, total: int, message: str):
        """
        Report progress as a percentage: pair counts can overflow a signal's int.

        Args:
            current: Comparisons done
            total: Total comparisons
            message: Progress message
        """
        self.progress.emit(100 * current // total if total else 100, 100, message)

    def cancel(self):
        """Cancel the grouping operation."""
        self.cancelled = True
        self.detector.cancel()


class _ThumbnailTask(QRunnable):
    """Loads one thumbnail on a thread pool thread."""

    def __init__(self, loader: 'ThumbnailLoader', image_path: str):
        """
        Initialize task.

        Args:
            loader: Loader that reports the result
            image_path: Path to the image
        """
        super().__init__()
        self.loader = loader
        self.image_path = image_path

    def run(self):
        """Load the thumbnail and report it."""
        self.loader.loaded.emit(self.image_path, self.loader.image_utils.load_thumbnail_image(self.image_path))


class ThumbnailLoader(QObject):
    """Loads thumbnails in the background, delivering them on the main thread."""

    loaded = pyqtSignal(str, QImage)  # path, thumbnail (null if loading failed)

    def __init__(self, image_utils: ImageUtils, parent=None):
        """
        Initialize thumbnail loader.

        Args:
            image_utils: Provides the thumbnail disk cache
            parent: Parent object
        """
        super().__init__(parent)
        self.image_utils = image_utils
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(MAX_WORKER_THREADS)

    def request(self, image_path: str):
        """
        Queue a thumbnail to load.

        Args:
            image_path: Path to the image
        """
        self.pool.start(_ThumbnailTask(self, image_path))

    def cancel_pending(self):
        """Drop the queued thumbnails that have not started yet."""
        self.pool.clear()

    def shutdown(self):
        """Drop queued thumbnails and wait for the running ones to finish."""
        self.pool.clear()
        self.pool.waitForDone()


class DeleteWorker(QThread):
    """Worker thread specifically for deleting files."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(dict)  # deletion results
    error = pyqtSignal(str)  # error message

    def __init__(self, file_manager, file_paths: list, use_trash: bool = True):
        """
        Initialize delete worker.

        Args:
            file_manager: FileManager instance
            file_paths: List of file paths to delete
            use_trash: Whether to use trash
        """
        super().__init__()
        self.file_manager = file_manager
        self.file_paths = file_paths
        self.use_trash = use_trash

    def run(self):
        """Execute file deletion."""
        try:
            logger.info(f"Starting deletion of {len(self.file_paths)} files")

            results = {
                'success': [],
                'failed': []
            }

            total = len(self.file_paths)

            # Delete files one at a time with progress updates
            for i, file_path in enumerate(self.file_paths):
                import os
                filename = os.path.basename(file_path)

                # Emit progress
                self.progress.emit(i + 1, total, f"Deleting {filename}")

                # Delete the file
                try:
                    if not os.path.exists(file_path):
                        results['failed'].append((file_path, "File not found"))
                        continue

                    if not os.path.isfile(file_path):
                        results['failed'].append((file_path, "Not a file"))
                        continue

                    if self.use_trash:
                        success = self.file_manager.move_to_trash(file_path)
                        if success:
                            results['success'].append(file_path)
                        else:
                            results['failed'].append((file_path, "Failed to move to trash"))
                    else:
                        os.remove(file_path)
                        results['success'].append(file_path)

                except PermissionError as e:
                    results['failed'].append((file_path, f"Permission denied"))
                except Exception as e:
                    results['failed'].append((file_path, str(e)))

                # Small delay to prevent UI freezing
                self.msleep(10)

            self.finished.emit(results)
            logger.info(f"Deletion completed: {len(results['success'])} succeeded, {len(results['failed'])} failed")

        except Exception as e:
            error_msg = f"Error during deletion: {e}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)
