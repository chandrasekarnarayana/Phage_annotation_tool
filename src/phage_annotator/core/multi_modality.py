"""Multi-modality annotation filtering and propagation utilities (

This module provides utilities for:
- Filtering annotations by modality
- Propagating annotations across modalities
- Managing modality-specific annotation state
"""

from __future__ import annotations

from typing import List, Optional

from phage_annotator.core.annotation import Keypoint


def filter_by_modality(
    keypoints: List[Keypoint],
    modality_idx: Optional[int] = None,
    show_all: bool = True,
) -> List[Keypoint]:
    """Filter annotations by modality index.
    
    Parameters
    ----------
    keypoints : list of Keypoint
        Annotations to filter.
    modality_idx : int, optional
        Modality index to filter by. If None, no modality filtering is applied.
    show_all : bool, default=True
        If True, annotations with modality_idx=None are always shown (global annotations).
        If False, only annotations matching the exact modality_idx are returned.
    
    Returns
    -------
    list of Keypoint
        Filtered annotations.
    
    Examples
    --------
    >>> kps = [
    ...     Keypoint(..., modality_idx=0),
    ...     Keypoint(..., modality_idx=1),
    ...     Keypoint(..., modality_idx=None),  # Global
    ... ]
    >>> filter_by_modality(kps, modality_idx=0)
    # Returns: modality 0 + global annotations
    >>> filter_by_modality(kps, modality_idx=0, show_all=False)
    # Returns: only modality 0 annotations
    """
    if modality_idx is None:
        # No modality filtering requested
        return keypoints
    
    filtered = []
    for kp in keypoints:
        if kp.modality_idx == modality_idx:
            # Exact modality match
            filtered.append(kp)
        elif show_all and kp.modality_idx is None:
            # Global annotation (visible on all modalities)
            filtered.append(kp)
    
    return filtered


def propagate_to_modality(
    keypoints: List[Keypoint],
    target_modality_idx: int,
) -> List[Keypoint]:
    """Create copies of annotations assigned to a target modality.
    
    This "propagates" annotations from their current modality to a new modality,
    creating duplicates with the target modality_idx.
    
    Parameters
    ----------
    keypoints : list of Keypoint
        Annotations to propagate.
    target_modality_idx : int
        Target modality index for new annotations.
    
    Returns
    -------
    list of Keypoint
        New annotations with target modality_idx.
    
    Examples
    --------
    >>> kps = [Keypoint(..., modality_idx=0)]
    >>> new_kps = propagate_to_modality(kps, target_modality_idx=1)
    # Returns new annotations with modality_idx=1
    """
    import uuid
    from dataclasses import replace
    
    propagated = []
    for kp in keypoints:
        # Create a copy with new modality_idx and new annotation_id
        new_kp = replace(
            kp,
            modality_idx=target_modality_idx,
            annotation_id=str(uuid.uuid4()),  # New unique ID
            source=f"propagated_from_modality_{kp.modality_idx}",
        )
        propagated.append(new_kp)
    
    return propagated


def assign_to_modality(
    keypoints: List[Keypoint],
    modality_idx: Optional[int],
) -> List[Keypoint]:
    """Assign annotations to a specific modality (in-place modification).
    
    Parameters
    ----------
    keypoints : list of Keypoint
        Annotations to assign.
    modality_idx : int or None
        Modality index to assign, or None for global annotations.
    
    Returns
    -------
    list of Keypoint
        Same list with modified modality_idx (for chaining).
    
    Examples
    --------
    >>> kps = [Keypoint(..., modality_idx=None)]
    >>> assign_to_modality(kps, modality_idx=0)
    # All annotations now have modality_idx=0
    """
    for kp in keypoints:
        kp.modality_idx = modality_idx
    return keypoints


def get_modality_summary(keypoints: List[Keypoint]) -> dict[Optional[int], int]:
    """Get annotation counts per modality.
    
    Parameters
    ----------
    keypoints : list of Keypoint
        Annotations to summarize.
    
    Returns
    -------
    dict
        Mapping of modality_idx → count. None key represents global annotations.
    
    Examples
    --------
    >>> kps = [
    ...     Keypoint(..., modality_idx=0),
    ...     Keypoint(..., modality_idx=0),
    ...     Keypoint(..., modality_idx=1),
    ...     Keypoint(..., modality_idx=None),
    ... ]
    >>> get_modality_summary(kps)
    {0: 2, 1: 1, None: 1}
    """
    summary: dict[Optional[int], int] = {}
    for kp in keypoints:
        summary[kp.modality_idx] = summary.get(kp.modality_idx, 0) + 1
    return summary
