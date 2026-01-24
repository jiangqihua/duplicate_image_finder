"""File manager module for safe file operations."""

import os
import logging
from typing import List, Dict, Any, Tuple
from send2trash import send2trash
from config import USE_TRASH_BY_DEFAULT

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations with safety features."""

    def delete_files(self, file_paths: List[str], use_trash: bool = USE_TRASH_BY_DEFAULT) -> Dict[str, Any]:
        """
        Delete files safely.

        Args:
            file_paths: Files to delete
            use_trash: Move to trash instead of permanent delete

        Returns:
            Dictionary with results:
            {
                'success': List[str],  # Successfully deleted
                'failed': List[Tuple[str, str]]  # (path, error_message)
            }
        """
        results = {
            'success': [],
            'failed': []
        }

        for file_path in file_paths:
            try:
                # Validate file exists
                if not os.path.exists(file_path):
                    results['failed'].append((file_path, "File not found"))
                    continue

                # Validate it's a file (not a directory)
                if not os.path.isfile(file_path):
                    results['failed'].append((file_path, "Not a file"))
                    continue

                # Delete the file
                if use_trash:
                    success = self.move_to_trash(file_path)
                    if success:
                        results['success'].append(file_path)
                    else:
                        results['failed'].append((file_path, "Failed to move to trash"))
                else:
                    os.remove(file_path)
                    results['success'].append(file_path)
                    logger.info(f"Permanently deleted: {file_path}")

            except PermissionError as e:
                results['failed'].append((file_path, f"Permission denied: {e}"))
                logger.warning(f"Permission denied deleting {file_path}: {e}")
            except Exception as e:
                results['failed'].append((file_path, str(e)))
                logger.error(f"Error deleting {file_path}: {e}")

        logger.info(f"Deleted {len(results['success'])}/{len(file_paths)} files successfully")
        if results['failed']:
            logger.warning(f"Failed to delete {len(results['failed'])} files")

        return results

    def move_to_trash(self, file_path: str) -> bool:
        """
        Move file to system trash/recycle bin.

        Args:
            file_path: Path to the file

        Returns:
            True if successful, False otherwise
        """
        try:
            send2trash(file_path)
            logger.info(f"Moved to trash: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to move {file_path} to trash: {e}")
            return False

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get detailed file information.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        try:
            stat = os.stat(file_path)
            return {
                'path': file_path,
                'name': os.path.basename(file_path),
                'size': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime,
                'exists': True
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {
                'path': file_path,
                'exists': False,
                'error': str(e)
            }

    def calculate_total_size(self, file_paths: List[str]) -> int:
        """
        Calculate total size of files.

        Args:
            file_paths: List of file paths

        Returns:
            Total size in bytes
        """
        total_size = 0
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
            except Exception as e:
                logger.warning(f"Error getting size of {file_path}: {e}")

        return total_size
