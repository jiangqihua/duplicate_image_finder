"""Image utilities for thumbnail generation and formatting."""

import os
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Dict, Any
from PIL import Image
from PyQt6.QtGui import QPixmap
from config import THUMBNAIL_SIZE, THUMBNAIL_CACHE_DIR

logger = logging.getLogger(__name__)


class ImageUtils:
    """Utilities for image processing."""

    def __init__(self):
        """Initialize image utilities."""
        self.cache_dir = Path(THUMBNAIL_CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache = {}

    def create_thumbnail(self, image_path: str, size: Tuple[int, int] = THUMBNAIL_SIZE) -> QPixmap:
        """
        Create thumbnail with caching.

        Args:
            image_path: Path to the image
            size: Thumbnail size (width, height)

        Returns:
            QPixmap thumbnail
        """
        # Check memory cache
        cache_key = f"{image_path}_{size[0]}x{size[1]}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]

        # Check disk cache
        cache_file = self._get_cache_path(image_path, size)
        if cache_file.exists():
            pixmap = QPixmap(str(cache_file))
            if not pixmap.isNull():
                self.memory_cache[cache_key] = pixmap
                return pixmap

        # Generate thumbnail
        try:
            pixmap = self._generate_thumbnail(image_path, size, cache_file)
            self.memory_cache[cache_key] = pixmap
            return pixmap
        except Exception as e:
            logger.error(f"Error creating thumbnail for {image_path}: {e}")
            # Return empty pixmap
            return QPixmap()

    def _generate_thumbnail(self, image_path: str, size: Tuple[int, int], cache_file: Path) -> QPixmap:
        """
        Generate thumbnail and save to cache.

        Args:
            image_path: Path to the image
            size: Thumbnail size
            cache_file: Path to cache file

        Returns:
            QPixmap thumbnail
        """
        with Image.open(image_path) as img:
            # Use draft mode for faster loading
            img.draft('RGB', size)

            # Convert to RGB if needed
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Create thumbnail maintaining aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Save to cache
            img.save(cache_file, 'JPEG', quality=85)

        # Load as QPixmap
        pixmap = QPixmap(str(cache_file))
        return pixmap

    def _get_cache_path(self, image_path: str, size: Tuple[int, int]) -> Path:
        """
        Get cache file path for an image.

        Args:
            image_path: Path to the image
            size: Thumbnail size

        Returns:
            Path to cache file
        """
        cache_key = f"{image_path}_{size[0]}x{size[1]}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{cache_hash}.jpg"

    @staticmethod
    def get_image_info(image_path: str) -> Dict[str, Any]:
        """
        Extract image metadata.

        Args:
            image_path: Path to the image

        Returns:
            Dictionary with image information
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'path': image_path,
                    'format': img.format,
                    'mode': img.mode,
                    'dimensions': img.size,
                    'file_size': os.path.getsize(image_path),
                    'modified_time': os.path.getmtime(image_path)
                }
        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {e}")
            return {
                'path': image_path,
                'error': str(e)
            }

    @staticmethod
    def format_file_size(bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            bytes: File size in bytes

        Returns:
            Formatted string (e.g., '2.3 MB')
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"

    @staticmethod
    def format_dimensions(dimensions: Tuple[int, int]) -> str:
        """
        Format image dimensions.

        Args:
            dimensions: (width, height)

        Returns:
            Formatted string (e.g., '1920x1080')
        """
        return f"{dimensions[0]}x{dimensions[1]}"

    def clear_cache(self):
        """Clear thumbnail cache."""
        try:
            for cache_file in self.cache_dir.glob("*.jpg"):
                cache_file.unlink()
            self.memory_cache.clear()
            logger.info("Thumbnail cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
