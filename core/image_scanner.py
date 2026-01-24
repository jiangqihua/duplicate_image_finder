"""Image scanner module for discovering image files."""

import os
import logging
from typing import List, Callable, Optional
from PIL import Image
from config import SUPPORTED_EXTENSIONS, MAX_IMAGE_SIZE

logger = logging.getLogger(__name__)


class ImageScanner:
    """Scans directories for image files."""

    def __init__(self):
        """Initialize the image scanner."""
        self.cancelled = False

    def scan_folder(self, folder_path: str, recursive: bool = True,
                   progress_callback: Optional[Callable[[int, str], None]] = None) -> List[str]:
        """
        Scan folder for image files.

        Args:
            folder_path: Path to scan
            recursive: Whether to scan subdirectories
            progress_callback: Optional callback(count, current_file) for progress updates

        Returns:
            List of valid image file paths
        """
        self.cancelled = False
        image_paths = []

        try:
            if recursive:
                # Walk through directory tree
                for root, dirs, files in os.walk(folder_path):
                    if self.cancelled:
                        break

                    for filename in files:
                        if self.cancelled:
                            break

                        file_path = os.path.join(root, filename)

                        # Check extension
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in SUPPORTED_EXTENSIONS:
                            # Validate the image
                            if self.is_valid_image(file_path):
                                image_paths.append(file_path)

                                if progress_callback:
                                    progress_callback(len(image_paths), file_path)
            else:
                # Scan only current directory
                for filename in os.listdir(folder_path):
                    if self.cancelled:
                        break

                    file_path = os.path.join(folder_path, filename)

                    if not os.path.isfile(file_path):
                        continue

                    _, ext = os.path.splitext(filename)
                    if ext.lower() in SUPPORTED_EXTENSIONS:
                        if self.is_valid_image(file_path):
                            image_paths.append(file_path)

                            if progress_callback:
                                progress_callback(len(image_paths), file_path)

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {folder_path}: {e}")
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")

        logger.info(f"Found {len(image_paths)} valid images in {folder_path}")
        return image_paths

    def is_valid_image(self, file_path: str) -> bool:
        """
        Check if file is a valid image.

        Args:
            file_path: Path to the file

        Returns:
            True if file is a valid image, False otherwise
        """
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.debug(f"Skipping empty file: {file_path}")
                return False

            if file_size > MAX_IMAGE_SIZE:
                logger.debug(f"Skipping large file ({file_size} bytes): {file_path}")
                return False

            # Try to open with PIL
            with Image.open(file_path) as img:
                # Verify it's a valid image by loading it
                img.verify()

            return True

        except (IOError, OSError) as e:
            logger.debug(f"Invalid image file {file_path}: {e}")
            return False
        except Exception as e:
            logger.debug(f"Error validating {file_path}: {e}")
            return False

    def cancel(self):
        """Cancel the scanning operation."""
        self.cancelled = True
        logger.info("Image scanning cancelled")
