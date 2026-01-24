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
- imagehash (perceptual hashing)
- send2trash (safe file deletion)

## Architecture

### Core Processing Pipeline

1. **Image Scanning** (`core/image_scanner.py`):
   - Recursively scans directories for supported image formats
   - Validates images using PIL (checks file size, format)
   - Supported formats: jpg, jpeg, png, bmp, gif, webp, tiff

2. **Hash Calculation** (`core/hash_calculator.py`):
   - Computes three perceptual hash types per image:
     - ahash (Average Hash) - 20% weight
     - phash (Perceptual Hash) - 50% weight
     - dhash (Difference Hash) - 30% weight
   - Stores metadata: file size, dimensions, modification time

3. **Similarity Detection** (`core/similarity_detector.py`):
   - Uses Union-Find algorithm to group similar images
   - Compares all image pairs using weighted hash distance
   - Groups images if distance ≤ threshold (default: 5)
   - Filters out singleton groups (no matches)
   - Sorts groups by similarity percentage and size

4. **Quality Ranking** (within each group):
   - Images sorted by: resolution → file size → modification date (all descending)
   - Best quality image appears first in each group

### GUI Architecture

- **Main Window** (`gui/main_window.py`): Application orchestration, event handling
- **Image Card** (`gui/widgets/image_card.py`): Individual image display with checkbox
- **Image Group Viewer** (`gui/widgets/image_group_viewer.py`): Displays grouped similar images
- **Progress Dialog** (`gui/widgets/progress_dialog.py`): Cancellable progress tracking

### Background Processing

- Scanning and hash calculation run in QThreads (via `utils/threading_utils.py`)
- Progress callbacks update UI without blocking
- Operations are cancellable mid-execution

## Configuration

`config.py` contains all tunable parameters:

- **Hash weights**: `HASH_WEIGHTS = {'phash': 0.5, 'dhash': 0.3, 'ahash': 0.2}`
- **Similarity threshold**: `DEFAULT_THRESHOLD = 5` (0-64 scale, lower = stricter)
- **Thumbnail caching**: `.thumbnail_cache/` directory stores generated thumbnails
- **Performance**: `MAX_WORKER_THREADS = 4`, `BATCH_SIZE = 100`

## Key Implementation Details

### Similarity Calculation
- Distance is weighted combination of three hash distances (Hamming distance)
- Threshold of 5 finds exact duplicates; 10-20 finds similar images (resized, compressed)
- Similarity percentage = `100 * (1 - distance / 30)`

### Selection Modes
- **Keep Best (100% Match Only)**: Auto-selects duplicates in exact match groups (similarity = 100%)
- **Keep Best Quality** (per group): Selects all images except the highest quality one in that group

### File Operations
- Deletion uses `send2trash` library (safe, recoverable)
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
- Current implementation uses Union-Find; could be replaced with hierarchical clustering or other approaches

### Adding UI Features
- Background operations must use QThread to avoid blocking UI
- Use progress callbacks: `callback(current, total, message)` signature
- Update `threading_utils.py` for new background task types
