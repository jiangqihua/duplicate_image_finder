"""Hash calculator module for computing perceptual hashes."""

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from PIL import Image
import imagehash
from config import DEFAULT_HASH_SIZE

logger = logging.getLogger(__name__)


class HashCalculator:
    """Computes perceptual hashes for images."""

    def __init__(self, hash_size: int = DEFAULT_HASH_SIZE):
        """
        Initialize the hash calculator.

        Args:
            hash_size: Size of hash (default 8x8 = 64 bits)
        """
        self.hash_size = hash_size
        self.cancelled = False

    def compute_hash(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Compute multiple hash types for an image.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing hashes and metadata, or None if failed
            {
                'path': str,
                'ahash': imagehash.ImageHash,  # Average hash
                'phash': imagehash.ImageHash,  # Perceptual hash
                'dhash': imagehash.ImageHash,  # Difference hash
                'file_size': int,
                'dimensions': tuple[int, int],
                'modified_time': float
            }
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Compute multiple hash types for robustness
                result = {
                    'path': image_path,
                    'ahash': imagehash.average_hash(img, hash_size=self.hash_size),
                    'phash': imagehash.phash(img, hash_size=self.hash_size),
                    'dhash': imagehash.dhash(img, hash_size=self.hash_size),
                    'file_size': os.path.getsize(image_path),
                    'dimensions': img.size,
                    'modified_time': os.path.getmtime(image_path)
                }

                return result

        except (IOError, OSError) as e:
            logger.warning(f"Failed to process {image_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing {image_path}: {e}")
            return None

    def compute_batch(self, image_paths: List[str],
                     progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[Dict[str, Any]]:
        """
        Compute hashes for multiple images with progress tracking.

        Args:
            image_paths: List of image file paths
            progress_callback: Optional callback(current, total, message) for progress updates

        Returns:
            List of hash dictionaries for successfully processed images
        """
        self.cancelled = False
        results = []
        total = len(image_paths)

        for i, image_path in enumerate(image_paths):
            if self.cancelled:
                logger.info("Hash calculation cancelled")
                break

            # Update progress
            if progress_callback:
                filename = os.path.basename(image_path)
                progress_callback(i + 1, total, f"Processing {filename}")

            # Compute hash
            result = self.compute_hash(image_path)
            if result:
                results.append(result)

        logger.info(f"Successfully computed hashes for {len(results)}/{total} images")
        return results

    def cancel(self):
        """Cancel the hash calculation operation."""
        self.cancelled = True
        logger.info("Hash calculation cancelled")
