"""Similarity detector module for grouping similar images."""

import logging
from typing import List, Dict, Any
from config import DEFAULT_THRESHOLD, HASH_WEIGHTS

logger = logging.getLogger(__name__)


class UnionFind:
    """Union-Find (Disjoint Set) data structure for efficient grouping."""

    def __init__(self, n: int):
        """
        Initialize Union-Find structure.

        Args:
            n: Number of elements
        """
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """
        Find root parent of element with path compression.

        Args:
            x: Element index

        Returns:
            Root parent index
        """
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]

    def union(self, x: int, y: int):
        """
        Merge two sets containing x and y.

        Args:
            x: First element index
            y: Second element index
        """
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return

        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1


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

    def find_similar_groups(self, image_hashes: List[Dict[str, Any]],
                           progress_callback=None) -> List[List[Dict[str, Any]]]:
        """
        Group similar images using Union-Find clustering.

        Args:
            image_hashes: List of image hash dictionaries
            progress_callback: Optional callback(current, total, message) for progress updates

        Returns:
            List of groups, each group is a list of similar image dicts
        """
        if not image_hashes:
            return []

        self.image_hashes = image_hashes
        n = len(image_hashes)

        # Initialize Union-Find structure
        uf = UnionFind(n)

        # Calculate total comparisons for progress tracking
        total_comparisons = (n * (n - 1)) // 2
        comparison_count = 0

        # Compare all pairs of images
        for i in range(n):
            for j in range(i + 1, n):
                distance = self._compute_distance(image_hashes[i], image_hashes[j])

                # If distance is below threshold, union the sets
                if distance <= self.threshold:
                    uf.union(i, j)

                # Update progress
                comparison_count += 1
                if progress_callback and comparison_count % 100 == 0:  # Update every 100 comparisons
                    progress_callback(comparison_count, total_comparisons,
                                    f"Comparing images ({comparison_count}/{total_comparisons})")

        # Final progress update
        if progress_callback:
            progress_callback(total_comparisons, total_comparisons, "Grouping similar images...")

        # Extract groups from Union-Find
        groups_dict = {}
        for i in range(n):
            root = uf.find(i)
            if root not in groups_dict:
                groups_dict[root] = []
            groups_dict[root].append(image_hashes[i])

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

        total_distance = 0.0
        count = 0

        # Compute average pairwise distance
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                total_distance += self._compute_distance(group[i], group[j])
                count += 1

        avg_distance = total_distance / count if count > 0 else 0

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

    def update_threshold(self, new_threshold: int, progress_callback=None) -> List[List[Dict[str, Any]]]:
        """
        Update threshold and recompute groups.

        Args:
            new_threshold: New threshold value
            progress_callback: Optional callback for progress updates

        Returns:
            Updated list of groups
        """
        self.threshold = new_threshold
        return self.find_similar_groups(self.image_hashes, progress_callback)
