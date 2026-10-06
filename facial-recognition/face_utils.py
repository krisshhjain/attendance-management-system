"""
Centralized face embedding extraction utilities.

This module provides a robust face embedding extraction function that handles
multi-face images correctly by selecting the largest detected face, rather than
blindly taking the first face returned by DeepFace.represent().

Fixes the root cause bug where images containing multiple faces would embed
whichever face RetinaFace listed first, not necessarily the correct subject.
"""

import logging
import numpy as np
from deepface import DeepFace
from typing import Union, Tuple, Optional

# Configure logging for face extraction issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceExtractionError(Exception):
    """Raised when face extraction fails or produces ambiguous results."""
    pass


def extract_primary_face_embedding(
    img_path: Union[str, np.ndarray],
    model_name: str = "ArcFace",
    detector_backend: str = "retinaface",
    normalize: bool = True,
    dtype: type = np.float32,
    area_tolerance: float = 1.5,
    min_confidence: float = 0.95
) -> np.ndarray:
    """
    Extract face embedding from an image, selecting the largest face when multiple faces are detected.
    
    This function fixes the multi-face bug by:
    1. Using enforce_detection=True to ensure proper face detection
    2. When multiple faces are found, selecting the one with largest bounding box area
    3. Flagging ambiguous cases where top 2 faces are similar in size
    4. Never falling back to enforce_detection=False (which can embed garbage)
    
    Args:
        img_path: Path to image file or numpy array of image
        model_name: Face recognition model ("ArcFace", "VGG-Face", etc.)
        detector_backend: Face detector ("retinaface", "opencv", etc.)
        normalize: Whether to L2-normalize the embedding
        dtype: Output numpy dtype for the embedding
        area_tolerance: If top 2 faces are within this ratio, flag for manual review
        
    Returns:
        numpy.ndarray: Face embedding vector
        
    Raises:
        FaceExtractionError: If no faces detected, detection fails, or ambiguous multi-face case
        
    Example:
        >>> embedding = extract_primary_face_embedding("person1.jpg")
        >>> print(f"Embedding shape: {embedding.shape}")
        Embedding shape: (512,)
    """
    try:
        # Use enforce_detection=True to ensure proper face detection
        result = DeepFace.represent(
            img_path=img_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=True,
        )
    except Exception as e:
        raise FaceExtractionError(
            f"Face detection failed for {img_path}: {type(e).__name__}: {e}"
        ) from e
    
    if not result:
        raise FaceExtractionError(f"No faces detected in {img_path}")
    
    num_faces = len(result)
    
    if num_faces == 1:
        # Single face - straightforward case
        
        confidence = result[0].get("face_confidence", 1.0)
        if confidence is not None and confidence < min_confidence:
            raise FaceExtractionError(f"Face quality too low: confidence {confidence:.3f} < {min_confidence}")
            
        embedding = np.array(result[0]["embedding"], dtype=dtype)
        logger.debug(f"Single face detected in {img_path}")
        
    elif num_faces > 1:
        # Multiple faces - select the largest by bounding box area
        logger.info(f"Multiple faces detected in {img_path}: {num_faces} faces")
        
        face_areas = []
        for i, face_data in enumerate(result):
            facial_area = face_data.get("facial_area", {})
            width = facial_area.get("w", 0)
            height = facial_area.get("h", 0)
            area = width * height
            face_areas.append((area, i, face_data))
            logger.debug(f"  Face {i}: area={area} (w={width}, h={height})")
        
        # Sort by area (largest first)
        face_areas.sort(reverse=True, key=lambda x: x[0])
        
        largest_area, largest_idx, largest_face = face_areas[0]
        
        # Check if top 2 faces are ambiguously similar in size
        if len(face_areas) >= 2:
            second_area = face_areas[1][0]
            if largest_area > 0 and second_area / largest_area >= (1.0 / area_tolerance):
                raise FaceExtractionError(
                    f"Ambiguous multi-face image {img_path}: "
                    f"largest face area={largest_area}, second largest area={second_area} "
                    f"(ratio={second_area/largest_area:.3f} >= {1.0/area_tolerance:.3f}). "
                    f"Manual review required - cannot reliably select correct face."
                )
        
        
        confidence = largest_face.get("face_confidence", 1.0)
        if confidence is not None and confidence < min_confidence:
            raise FaceExtractionError(f"Face quality too low: confidence {confidence:.3f} < {min_confidence}")
            
        embedding = np.array(largest_face["embedding"], dtype=dtype)
        logger.info(f"Selected largest face (index {largest_idx}, area={largest_area}) from {img_path}")
        
    else:
        # Should never happen with enforce_detection=True, but be defensive
        raise FaceExtractionError(f"Unexpected result format from DeepFace.represent() for {img_path}")
    
    # Apply L2 normalization if requested
    if normalize:
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        else:
            raise FaceExtractionError(f"Zero-norm embedding extracted from {img_path}")
    
    return embedding


def get_face_count(img_path: Union[str, np.ndarray], detector_backend: str = "retinaface") -> int:
    """
    Count the number of faces detected in an image.
    
    Utility function for auditing multi-face images in the dataset.
    
    Args:
        img_path: Path to image file or numpy array of image
        detector_backend: Face detector to use
        
    Returns:
        int: Number of faces detected (0 if detection fails)
    """
    try:
        result = DeepFace.represent(
            img_path=img_path,
            model_name="ArcFace",  # Model doesn't matter for counting
            detector_backend=detector_backend,
            enforce_detection=True,
        )
        return len(result)
    except Exception:
        return 0


def get_face_details(img_path: Union[str, np.ndarray], detector_backend: str = "retinaface") -> list:
    """
    Get detailed information about all faces detected in an image.
    
    Args:
        img_path: Path to image file or numpy array of image
        detector_backend: Face detector to use
        
    Returns:
        list: List of dicts with face detection details (bounding boxes, confidence, etc.)
              Empty list if detection fails.
    """
    try:
        result = DeepFace.represent(
            img_path=img_path,
            model_name="ArcFace",  # Model doesn't matter for face details
            detector_backend=detector_backend,
            enforce_detection=True,
        )
        
        face_details = []
        for i, face_data in enumerate(result):
            facial_area = face_data.get("facial_area", {})
            confidence = face_data.get("face_confidence", None)
            area = facial_area.get("w", 0) * facial_area.get("h", 0)
            
            face_details.append({
                "face_index": i,
                "facial_area": facial_area,
                "area": area,
                "confidence": confidence,
            })
        
        return face_details
        
    except Exception as e:
        logger.debug(f"Face detection failed for {img_path}: {e}")
        return []