# Duplicate Image Finder

A PyQt6 application to find and delete duplicate or similar images using perceptual hashing.

## Features

- **Perceptual Hashing**: Uses multiple hash algorithms (ahash, phash, dhash) to detect similar images
- **Smart Grouping**: Groups similar images together with similarity percentages
- **Visual Interface**: Shows thumbnail previews with file information
- **Adjustable Threshold**: Fine-tune similarity detection with a slider
- **Safe Deletion**: Moves files to trash instead of permanent deletion
- **Progress Tracking**: Shows real-time progress during scanning and deletion
- **Smart Selection**: One-click "Keep Best (100% Match Only)" for safest bulk selection of exact duplicates only
- **Granular Control**: Per-group "Keep Best Quality" buttons for selective management of all similarity levels

## Installation

1. Make sure you have Python 3.8 or higher installed

2. Install dependencies:
```bash
cd duplicate_image_finder
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python main.py
```

Or make it executable:
```bash
chmod +x main.py
./main.py
```

2. Using the application:
   - Click **Browse** to select a folder containing images
   - Click **Scan Folder** to start searching for duplicates
   - Wait for the scan to complete (progress will be shown)
   - Review groups of similar images:
     - Each group shows similarity percentage
     - Images are sorted by quality (best first)
   - Select images to delete:
     - Manually check boxes on images you want to delete
     - Use **Select All** / **Deselect All** buttons per group
     - Use **Keep Best Quality** button per group to auto-select lower quality images in that group
     - Use **Keep Best (100% Match Only)** button to auto-select duplicates in exact match groups only (safest for bulk deletion)
   - Adjust the **Similarity Threshold** slider:
     - Lower values = stricter matching (only very similar images)
     - Higher values = more lenient (more matches)
   - Click **Delete Selected** to remove selected images
   - Confirm deletion in the dialog

3. Files are moved to your system's trash/recycle bin (not permanently deleted)

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- GIF (.gif)
- WebP (.webp)
- TIFF (.tiff)

## How It Works

### Perceptual Hashing
The application computes three types of perceptual hashes for each image:
- **Average Hash (ahash)**: Fast, basic similarity detection
- **Perceptual Hash (phash)**: Robust to resizing and minor edits
- **Difference Hash (dhash)**: Good at detecting similar content

These hashes are combined with weights (50% phash, 30% dhash, 20% ahash) for accurate similarity detection.

### Similarity Detection
Images are grouped using a Union-Find algorithm:
1. Compute hash distance between every pair of images
2. If distance is below threshold, group them together
3. Filter singleton groups (no duplicates)
4. Sort groups by similarity and size
5. Within groups, sort by quality (resolution, file size, date)

### Quality Sorting
Within each group, images are sorted by:
1. Resolution (highest first)
2. File size (largest first)
3. Modification date (newest first)

This ensures the "Keep Best Quality" feature selects the highest quality image to keep.

## Configuration

Edit `config.py` to customize:
- Supported image extensions
- Default similarity threshold
- Thumbnail size
- Hash algorithms and weights
- GUI settings

## Tips

- **Default threshold is 5** - optimized for finding exact duplicates
- **Increase threshold** (10-20) to find similar but not identical images (resized, compressed versions)
- **Use "Keep Best (100% Match Only)"** button for safest bulk selection - only processes exact duplicates
- **Use "Keep Best Quality"** per group for more selective control on all similarity levels
- **Large folders**: Scanning 1000+ images may take a few minutes
- **Thumbnails are cached** for faster subsequent viewing

## Troubleshooting

### Application won't start
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.8+)

### No images found
- Verify the folder contains supported image formats
- Check file permissions (application needs read access)

### Scanning is slow
- This is normal for large image collections
- The application processes images in the background
- You can cancel the scan at any time

### Deletion failed
- Check file permissions
- Make sure files aren't open in another application
- Check if trash/recycle bin is accessible

## Logs

Application logs are saved to `logs/duplicate_finder.log` for debugging.

## Architecture

```
duplicate_image_finder/
├── main.py                      # Entry point
├── config.py                    # Configuration
├── core/                        # Core logic
│   ├── image_scanner.py         # Find images
│   ├── hash_calculator.py       # Compute hashes
│   ├── similarity_detector.py   # Group similar images
│   └── file_manager.py          # Delete files
├── gui/                         # User interface
│   ├── main_window.py           # Main window
│   └── widgets/                 # UI components
│       ├── image_card.py
│       ├── image_group_viewer.py
│       └── progress_dialog.py
└── utils/                       # Utilities
    ├── image_utils.py           # Thumbnails
    └── threading_utils.py       # Background tasks
```

## License

This project is provided as-is for personal use.

## Safety Notice

- Files are moved to trash, not permanently deleted
- Always review selections before deleting
- Keep backups of important images
- Test with a small folder first
