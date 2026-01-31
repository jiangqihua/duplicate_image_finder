# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PyQt6 desktop application that finds and manages duplicate/similar images using perceptual hashing algorithms. Images are grouped by similarity and can be safely deleted (moved to trash).

## Development Commands

### Setup
```bash
./setup.sh              # Create venv and install dependencies
# OR manually:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
python main.py          # Direct execution
# OR
./run.sh               # Run with venv activation
```

### Dependencies
Core dependencies in `requirements.txt`:
- PyQt6 (GUI framework)
- Pillow (image processing)
- pillow-heif (HEIC/HEIF format support)
- imagehash (perceptual hashing)
- send2trash (safe file deletion)

## Project Structure

```
duplicate_image_finder/
├── main.py                          # Entry point: logging setup, QApplication init
├── config.py                        # All tunable parameters
├── requirements.txt
├── setup.sh / run.sh                # Environment setup and launch scripts
├── core/                            # Processing pipeline
│   ├── image_scanner.py             # Directory scanning and image validation
│   ├── hash_calculator.py           # Perceptual hash computation (ahash/phash/dhash)
│   ├── similarity_detector.py       # Union-Find clustering by hash distance
│   └── file_manager.py              # Safe file deletion via send2trash
├── gui/                             # PyQt6 UI
│   ├── main_window.py               # Main window: orchestration, controls, threading
│   └── widgets/
│       ├── image_card.py            # Single image thumbnail + metadata + checkbox
│       ├── image_group_viewer.py    # Scrollable list of grouped image cards
│       └── progress_dialog.py       # Modal progress bar with cancel support
├── utils/
│   ├── image_utils.py               # Thumbnail generation with two-level cache (memory + disk)
│   └── threading_utils.py           # ScanWorker, DeleteWorker, generic WorkerThread
├── .thumbnail_cache/                # Generated at runtime
└── logs/                            # Generated at runtime (duplicate_finder.log)
```

## Architecture

### Core Processing Pipeline

1. **Image Scanning** (`core/image_scanner.py`):
   - Recursively scans directories for supported image formats
   - Validates images using PIL (checks file size, format, calls `img.verify()`)
   - Supported formats: jpg, jpeg, png, bmp, gif, webp, tiff, heic, heif
   - Max file size: 50 MB (configured in `config.py`)
   - Cancellable via `cancel()` method

2. **Hash Calculation** (`core/hash_calculator.py`):
   - Computes three perceptual hash types per image:
     - ahash (Average Hash) - 20% weight
     - phash (Perceptual Hash) - 50% weight
     - dhash (Difference Hash) - 30% weight
   - Returns dict per image: `{path, ahash, phash, dhash, file_size, dimensions, modified_time}`
   - HEIC/HEIF support via `pillow_heif.register_heif_opener()`

3. **Similarity Detection** (`core/similarity_detector.py`):
   - Uses Union-Find (disjoint set) algorithm to group similar images
   - Compares all image pairs using weighted hash distance (O(n^2) comparisons)
   - Groups images if distance <= threshold (default: 5)
   - Filters out singleton groups
   - Sorts groups by similarity percentage (descending), then size
   - `update_threshold()` re-clusters existing hashes without re-computing them

4. **Quality Ranking** (within each group):
   - Images sorted by: resolution -> file size -> modification date (all descending)
   - Best quality image appears first in each group

### GUI Architecture

- **Main Window** (`gui/main_window.py`): Folder selection, threshold slider (0-30), scan/delete/clear buttons, status bar. Threshold slider triggers re-clustering without re-hashing.
- **Image Group Viewer** (`gui/widgets/image_group_viewer.py`): Scrollable groups, each with Select All / Deselect All / Keep Best Quality / Open All buttons. Images laid out in rows of `MAX_IMAGES_PER_ROW` (4).
- **Image Card** (`gui/widgets/image_card.py`): 220px-wide card with thumbnail (200x200), filename, file size, dimensions, modification date, and selection checkbox. Emits `selection_changed` signal.
- **Progress Dialog** (`gui/widgets/progress_dialog.py`): Modal dialog with progress bar, message label, optional cancel button. Deletion progress is non-cancellable.

### Background Processing

- `ScanWorker`: Runs scan + hash computation in a QThread. Cancellable (cancels both scanner and hash calculator).
- `DeleteWorker`: Runs file deletion in a QThread. Non-cancellable. 10ms sleep between deletions to keep UI responsive.
- `WorkerThread`: Generic worker for arbitrary callables.
- All workers emit `progress(int, int, str)`, `finished(object)`, and `error(str)` signals.

### Thumbnail Caching (`utils/image_utils.py`)

- Two-level cache: in-memory dict (fast) + disk cache in `.thumbnail_cache/` (persistent)
- Cache key: MD5 of `"{path}_{W}x{H}"`
- Thumbnails saved as JPEG quality 85

## Configuration

`config.py` contains all tunable parameters:

- **Supported formats**: `SUPPORTED_EXTENSIONS` - includes `.heic`, `.heif`
- **Hash weights**: `HASH_WEIGHTS = {'phash': 0.5, 'dhash': 0.3, 'ahash': 0.2}`
- **Similarity threshold**: `DEFAULT_THRESHOLD = 5` (0-64 scale, lower = stricter)
- **Threshold range**: `MIN_THRESHOLD = 0`, `MAX_THRESHOLD = 30`
- **Hash size**: `DEFAULT_HASH_SIZE = 8` (8x8 = 64-bit hashes)
- **Thumbnail**: `THUMBNAIL_SIZE = (200, 200)`, cached in `.thumbnail_cache/`
- **Window**: `WINDOW_SIZE = (1200, 800)`, `MAX_IMAGES_PER_ROW = 4`
- **Performance**: `MAX_WORKER_THREADS = 4`, `BATCH_SIZE = 100`
- **File ops**: `USE_TRASH_BY_DEFAULT = True`, `CONFIRMATION_REQUIRED = True`

## Key Implementation Details

### Similarity Calculation
- Distance = weighted Hamming distance: `0.2*ahash + 0.5*phash + 0.3*dhash`
- Threshold 5 finds exact duplicates; 10-20 finds similar images (resized, compressed)
- Similarity percentage = `100 * (1 - distance / 30)`

### Selection Modes
- **Keep Best (100% Match Only)**: Auto-selects duplicates in exact match groups only
- **Keep Best Quality** (per group): Selects all images except the highest quality one
- **Open All** (per group): Opens all images in system viewer (macOS `open`, Windows `start`, Linux `xdg-open`)

### Incremental Updates
- Threshold changes re-cluster without re-hashing (via `SimilarityDetector.update_threshold()`)
- After deletion, groups are filtered in-place without re-clustering

### File Operations
- Deletion uses `send2trash` library (safe, recoverable from system trash)
- Always requires user confirmation before deletion
- Logs to `logs/duplicate_finder.log`

## Common Workflows

### Adding a New Hash Algorithm
1. Import algorithm in `core/hash_calculator.py`
2. Add to `compute_hash()` method result dictionary
3. Update `HASH_ALGORITHMS` and `HASH_WEIGHTS` in `config.py`
4. Update weight calculation in `similarity_detector.py:_compute_distance()`

### Modifying Similarity Logic
- Edit `SimilarityDetector._compute_distance()` for custom distance calculation
- Edit `SimilarityDetector.find_similar_groups()` for different clustering algorithms
- Current implementation uses Union-Find; could be replaced with hierarchical clustering

### Adding UI Features
- Background operations must use QThread to avoid blocking UI
- Use progress callbacks: `callback(current, total, message)` signature
- Update `threading_utils.py` for new background task types
- Per-group buttons go in `ImageGroupViewer.create_group_widget()` controls layout

### Adding Image Format Support
1. Add extension to `SUPPORTED_EXTENSIONS` in `config.py`
2. If PIL doesn't natively support it, add an opener plugin (like `pillow_heif.register_heif_opener()`) in `image_scanner.py`, `hash_calculator.py`, and `image_utils.py`
3. Add the plugin to `requirements.txt`
