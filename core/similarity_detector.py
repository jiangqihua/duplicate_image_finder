"""Similarity detector module for grouping similar images."""

import logging
import time
from typing import List, Dict, Any
import numpy as np
from config import DEFAULT_THRESHOLD, HASH_WEIGHTS

logger = logging.getLogger(__name__)

PROGRESS_INTERVAL_SECONDS = 0.05


def _pack_hashes(images: List[Dict[str, Any]], name: str) -> np.ndarray:
    """
    Pack one hash type of every image into an array of 64-bit words.

    Args:
        images: List of image hash dictionaries
        name: Hash type ('ahash', 'phash' or 'dhash')

    Returns:
        Array of shape (len(images), words_per_hash) with dtype uint64
    """
    bits = np.stack([image[name].hash.ravel() for image in images])
    packed = np.packbits(bits, axis=1)
    padding = -packed.shape[1] % 8
    if padding:
        packed = np.pad(packed, ((0, 0), (0, padding)))
    return packed.view(np.uint64)


def _distances_to_rest(packed: Dict[str, np.ndarray], i: int) -> np.ndarray:
    """
    Compute weighted hash distances from image i to every image after it.

    Args:
        packed: Packed hashes per hash type, from _pack_hashes()
        i: Index of the image to compare

    Returns:
        Array of len(images) - i - 1 weighted distances
    """
    def hamming(name: str) -> np.ndarray:
        words = packed[name]
        return np.bitwise_count(words[i] ^ words[i + 1:]).sum(axis=1)

    return (
        HASH_WEIGHTS['ahash'] * hamming('ahash') +
        HASH_WEIGHTS['phash'] * hamming('phash') +
        HASH_WEIGHTS['dhash'] * hamming('dhash')
    )


class SimilarityDetector:
    """Groups images by similarity using perceptual hashes."""

    def __init__(self, threshold: int = DEFAULT_THRESHOLD):
        """
        Initialize the similarity detector.

        Args:
            threshold: Maximum hash difference for similarity (0-64)
                      Lower = more strict, Higher = more lenient
        """
        self.threshold = threshold
        self.image_hashes = []
        self.cancelled = False

    def cancel(self):
        """Stop an in-progress find_similar_groups() call. Safe from any thread."""
        self.cancelled = True

    def find_similar_groups(self, image_hashes: List[Dict[str, Any]],
                           progress_callback=None) -> List[List[Dict[str, Any]]]:
        """
        Group similar images by connected components of the "similar" relation.

        Args:
            image_hashes: List of image hash dictionaries
            progress_callback: Optional callback(current, total, message) for progress updates

        Returns:
            List of groups, each group is a list of similar image dicts.
            Empty if cancelled.
        """
        if not image_hashes:
            return []

        self.image_hashes = image_hashes
        n = len(image_hashes)

        packed = {name: _pack_hashes(image_hashes, name) for name in HASH_WEIGHTS}

        # labels[i] identifies the cluster image i currently belongs to
        labels = np.arange(n)

        total_comparisons = (n * (n - 1)) // 2
        comparison_count = 0
        last_report = time.monotonic()

        # Compare each image against all the images after it
        for i in range(n - 1):
            if self.cancelled:
                logger.info("Similarity comparison cancelled")
                return []

            distances = _distances_to_rest(packed, i)
            matches = np.nonzero(distances <= self.threshold)[0] + i + 1

            # Merge image i's cluster with the clusters of all its matches
            if matches.size:
                labels[np.isin(labels, labels[matches])] = labels[i]

            comparison_count += n - i - 1
            if progress_callback and time.monotonic() - last_report >= PROGRESS_INTERVAL_SECONDS:
                last_report = time.monotonic()
                progress_callback(comparison_count, total_comparisons, "Comparing images")

        # Final progress update
        if progress_callback:
            progress_callback(total_comparisons, total_comparisons, "Grouping similar images")

        # Collect the clusters
        groups_dict = {}
        for i, label in enumerate(labels.tolist()):
            groups_dict.setdefault(label, []).append(image_hashes[i])

        # Filter out singleton groups (no duplicates)
        groups = [group for group in groups_dict.values() if len(group) > 1]

        # Sort groups by average similarity (highest first) and size
        groups.sort(key=lambda g: (self._compute_group_similarity(g), len(g)), reverse=True)

        # Within each group, sort by quality
        for group in groups:
            group.sort(key=lambda img: (
                -img['dimensions'][0] * img['dimensions'][1],  # Resolution (descending)
                -img['file_size'],  # File size (descending)
                -img['modified_time']  # Modification time (descending)
            ))

        logger.info(f"Found {len(groups)} groups with {sum(len(g) for g in groups)} total images")
        return groups

    def _compute_distance(self, hash1: Dict[str, Any], hash2: Dict[str, Any]) -> float:
        """
        Compute weighted hash distance between two images.

        Args:
            hash1: First image hash dictionary
            hash2: Second image hash dictionary

        Returns:
            Weighted distance (lower = more similar)
        """
        # Compute Hamming distance for each hash type
        ahash_dist = hash1['ahash'] - hash2['ahash']
        phash_dist = hash1['phash'] - hash2['phash']
        dhash_dist = hash1['dhash'] - hash2['dhash']

        # Weighted combination
        weighted_distance = (
            HASH_WEIGHTS['ahash'] * ahash_dist +
            HASH_WEIGHTS['phash'] * phash_dist +
            HASH_WEIGHTS['dhash'] * dhash_dist
        )

        return weighted_distance

    def _compute_group_similarity(self, group: List[Dict[str, Any]]) -> float:
        """
        Compute average similarity score for a group.

        Args:
            group: List of image hash dictionaries

        Returns:
            Average similarity score (0-100, higher = more similar)
        """
        if len(group) < 2:
            return 0.0

        packed = {name: _pack_hashes(group, name) for name in HASH_WEIGHTS}

        # Compute average pairwise distance
        total_distance = sum(float(_distances_to_rest(packed, i).sum()) for i in range(len(group) - 1))
        count = len(group) * (len(group) - 1) // 2
        avg_distance = total_distance / count

        # Convert distance to similarity percentage (0-100)
        # Assuming max meaningful distance is 30
        similarity = max(0, min(100, 100 * (1 - avg_distance / 30)))

        return similarity

    def compute_similarity(self, hash1: Dict[str, Any], hash2: Dict[str, Any]) -> float:
        """
        Compute similarity score between two image hashes.

        Args:
            hash1: First image hash dictionary
            hash2: Second image hash dictionary

        Returns:
            Similarity score between 0-100 (100 = identical, 0 = completely different)
        """
        distance = self._compute_distance(hash1, hash2)

        # Convert distance to similarity percentage
        similarity = max(0, min(100, 100 * (1 - distance / 30)))

        return similarity
