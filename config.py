"""Configuration constants for Duplicate Image Finder."""

# Image scanning
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.heic', '.heif'}
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB

# Hashing
DEFAULT_HASH_SIZE = 8
HASH_ALGORITHMS = ['ahash', 'phash', 'dhash']
HASH_WEIGHTS = {'phash': 0.5, 'dhash': 0.3, 'ahash': 0.2}

# Similarity
DEFAULT_THRESHOLD = 5  # 0-64 scale (lower = stricter, finds exact duplicates)
MIN_THRESHOLD = 0
MAX_THRESHOLD = 30

# GUI
THUMBNAIL_SIZE = (200, 200)
THUMBNAIL_CACHE_DIR = '.thumbnail_cache'
WINDOW_SIZE = (1200, 800)
MAX_IMAGES_PER_ROW = 4

# File operations
USE_TRASH_BY_DEFAULT = True
CONFIRMATION_REQUIRED = True

# Performance
MAX_WORKER_THREADS = 4
BATCH_SIZE = 100
