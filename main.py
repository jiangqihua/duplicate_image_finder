#!/usr/bin/env python3
"""
Duplicate Image Finder
A PyQt application to find and delete duplicate/similar images.
"""

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow


def setup_logging():
    """Configure application logging."""
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'duplicate_finder.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Duplicate Image Finder started")
    logger.info("=" * 60)


def main():
    """Application entry point."""
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("Duplicate Image Finder")
    app.setOrganizationName("DuplicateFinder")

    # Set application style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
