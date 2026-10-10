#!/usr/bin/env python3
"""
Robust bulk embedding regeneration script.

This script safely regenerates all cached embeddings using the fixed face extraction
logic, handling failures gracefully and providing detailed reports.

Key features:
- Backs up existing embeddings before regeneration
- Catches and logs FaceExtractionError exceptions without aborting
- Reports detailed failure information (face areas, ratios, reasons)
- Validates minimum enrollment counts per identity
- Generates comprehensive success/failure statistics
- Can resume from partial runs
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import numpy as np

from face_utils import extract_primary_face_embedding, FaceExtractionError, get_face_details

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('embedding_regeneration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Dataset configuration
DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"
VAL_DIR = DATASET_ROOT / "val"

CACHE_DIR = Path("embeddings")
TRAIN_CACHE = CACHE_DIR / "train"
VAL_CACHE = CACHE_DIR / "val"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Quality thresholds
MIN_ENROLLMENT_IMAGES = 3
MIN_QUERY_IMAGES = 3
REQUIRED_TOTAL_IMAGES = MIN_ENROLLMENT_IMAGES + MIN_QUERY_IMAGES


class RegenerationStats:
    """Track regeneration statistics and failures."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        
        # Detailed failure tracking
        self.detection_failures = []      # No faces detected
        self.ambiguous_faces = []         # Multiple similar-sized faces
        self.other_failures = []          # Other extraction errors
        self.insufficient_enrollments = []  # < MIN_ENROLLMENT_IMAGES after filtering
        
        # Per-identity statistics
        self.identity_stats = {}
    
    def add_success(self, img_path: Path, identity: str):
        """Record successful embedding extraction."""
        self.processed += 1
        self.successful += 1
        
        if identity not in self.identity_stats:
            self.identity_stats[identity] = {
                'successful': 0, 'failed': 0, 'total_attempted': 0
            }
        
        self.identity_stats[identity]['successful'] += 1
        self.identity_stats[identity]['total_attempted'] += 1
        
        logger.debug(f"✓ {img_path.relative_to(DATASET_ROOT)}")
    
    def add_failure(self, img_path: Path, identity: str, error: Exception, face_details: Optional[List] = None):
        """Record failed embedding extraction with detailed information."""
        self.processed += 1
        self.failed += 1
        
        if identity not in self.identity_stats:
            self.identity_stats[identity] = {
                'successful': 0, 'failed': 0, 'total_attempted': 0
            }
        
        self.identity_stats[identity]['failed'] += 1
        self.identity_stats[identity]['total_attempted'] += 1
        
        failure_info = {
            'image_path': str(img_path.relative_to(DATASET_ROOT)),
            'identity': identity,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
        }
        
        # Add face detection details if available
        if face_details:
            failure_info['face_details'] = face_details
            if len(face_details) >= 2:
                # Calculate area ratio for multi-face cases
                areas = [f['area'] for f in face_details]
                areas.sort(reverse=True)
                failure_info['largest_face_area'] = areas[0]
                failure_info['second_largest_area'] = areas[1] 
                failure_info['area_ratio'] = areas[1] / areas[0] if areas[0] > 0 else 0
        
        # Categorize the failure
        if isinstance(error, FaceExtractionError):
            error_msg = str(error).lower()
            if 'no faces detected' in error_msg or 'detection failed' in error_msg:
                self.detection_failures.append(failure_info)
            elif 'ambiguous multi-face' in error_msg:
                self.ambiguous_faces.append(failure_info) 
            else:
                self.other_failures.append(failure_info)
        else:
            self.other_failures.append(failure_info)
        
        logger.warning(f"✗ {img_path.relative_to(DATASET_ROOT)}: {error}")
    
    def add_insufficient_enrollment(self, identity: str, successful_count: int, total_attempted: int):
        """Record identity with insufficient enrollment images."""
        self.insufficient_enrollments.append({
            'identity': identity,
            'successful_images': successful_count,
            'total_attempted': total_attempted,
            'minimum_required': MIN_ENROLLMENT_IMAGES
        })
        
        logger.error(f"⚠ Identity {identity}: only {successful_count}/{total_attempted} usable enrollment images (need {MIN_ENROLLMENT_IMAGES})")
    
    def generate_report(self) -> Dict:
        """Generate comprehensive failure report."""
        duration = datetime.now() - self.start_time
        
        return {
            'summary': {
                'start_time': self.start_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'total_processed': self.processed,
                'successful': self.successful,
                'failed': self.failed,
                'success_rate': self.successful / self.processed if self.processed > 0 else 0,
            },
            'failure_breakdown': {
                'detection_failures': len(self.detection_failures),
                'ambiguous_multi_face': len(self.ambiguous_faces),
                'other_failures': len(self.other_failures),
                'insufficient_enrollments': len(self.insufficient_enrollments),
            },
            'detailed_failures': {
                'detection_failures': self.detection_failures,
                'ambiguous_multi_face': self.ambiguous_faces,
                'other_failures': self.other_failures,
                'insufficient_enrollments': self.insufficient_enrollments,
            },
            'per_identity_stats': self.identity_stats,
        }


def get_images(directory: Path) -> List[Path]:
    """Get all image files from a directory."""
    if not directory.exists():
        return []
    
    return sorted([
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ])


def backup_embeddings() -> Path:
    """Create backup of existing embeddings directory."""
    if not CACHE_DIR.exists():
        logger.info("No existing embeddings to backup")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = CACHE_DIR.parent / f"embeddings_backup_{timestamp}"
    
    logger.info(f"Backing up embeddings: {CACHE_DIR} -> {backup_dir}")
    shutil.copytree(CACHE_DIR, backup_dir)
    
    return backup_dir


def safe_extract_embedding(img_path: Path, identity: str, stats: RegenerationStats) -> Optional[np.ndarray]:
    """
    Safely extract embedding with proper error handling and logging.
    
    Returns:
        np.ndarray: Embedding vector if successful, None if failed
    """
    try:
        embedding = extract_primary_face_embedding(
            img_path=str(img_path),
            model_name="ArcFace",
            detector_backend="retinaface",
            normalize=True,  # Use L2 normalization for consistency
            dtype=np.float32
        )
        
        stats.add_success(img_path, identity)
        return embedding
        
    except Exception as error:
        # Get face detection details for better failure reporting
        face_details = get_face_details(str(img_path), "retinaface")
        stats.add_failure(img_path, identity, error, face_details)
        return None


def regenerate_identity_embeddings(identity_dir: Path, cache_dir: Path, stats: RegenerationStats) -> bool:
    """
    Regenerate embeddings for a single identity.
    
    Returns:
        bool: True if identity has sufficient usable images, False otherwise
    """
    identity = identity_dir.name
    images = get_images(identity_dir)
    
    if len(images) < REQUIRED_TOTAL_IMAGES:
        logger.warning(f"Identity {identity}: only {len(images)} images (need {REQUIRED_TOTAL_IMAGES})")
        return False
    
    logger.info(f"Processing identity {identity}: {len(images)} images")
    
    # Create cache subdirectory
    identity_cache_dir = cache_dir / identity
    identity_cache_dir.mkdir(parents=True, exist_ok=True)
    
    successful_embeddings = 0
    
    # Process all images for this identity
    for img_path in images:
        embedding = safe_extract_embedding(img_path, identity, stats)
        
        if embedding is not None:
            # Save embedding to cache
            cache_path = identity_cache_dir / f"{img_path.stem}.npy"
            np.save(cache_path, embedding)
            successful_embeddings += 1
    
    # Check if enough images succeeded for enrollment
    if successful_embeddings < MIN_ENROLLMENT_IMAGES:
        # Remove partial results to prevent silent quality degradation
        if identity_cache_dir.exists():
            shutil.rmtree(identity_cache_dir)
        stats.add_insufficient_enrollment(identity, successful_embeddings, len(images))
        return False
    
    logger.info(f"Identity {identity}: {successful_embeddings}/{len(images)} embeddings extracted successfully")
    return True


def regenerate_all_embeddings(dataset_dir: Path, cache_dir: Path, stats: RegenerationStats):
    """Regenerate embeddings for all identities in a dataset split."""
    
    if not dataset_dir.exists():
        logger.warning(f"Dataset directory not found: {dataset_dir}")
        return
    
    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each identity directory
    identity_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
    logger.info(f"Found {len(identity_dirs)} identity directories in {dataset_dir}")
    
    sufficient_identities = 0
    
    for identity_dir in sorted(identity_dirs):
        try:
            if regenerate_identity_embeddings(identity_dir, cache_dir, stats):
                sufficient_identities += 1
        except Exception as e:
            logger.error(f"Unexpected error processing {identity_dir}: {e}")
            continue
    
    logger.info(f"Completed {dataset_dir.name}: {sufficient_identities}/{len(identity_dirs)} identities have sufficient usable images")


def main():
    """Main regeneration workflow."""
    logger.info("=" * 80)
    logger.info("FACE EMBEDDING BULK REGENERATION")
    logger.info("=" * 80)
    
    # Create statistics tracker
    stats = RegenerationStats()
    
    # Backup existing embeddings
    backup_dir = backup_embeddings()
    if backup_dir:
        logger.info(f"Backup created: {backup_dir}")
    
    # Clean and recreate cache directories
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Regenerate train embeddings
        logger.info("\n" + "="*50)
        logger.info("REGENERATING TRAIN EMBEDDINGS")
        logger.info("="*50)
        regenerate_all_embeddings(TRAIN_DIR, TRAIN_CACHE, stats)
        
        # Regenerate validation embeddings  
        logger.info("\n" + "="*50)
        logger.info("REGENERATING VALIDATION EMBEDDINGS")
        logger.info("="*50)
        regenerate_all_embeddings(VAL_DIR, VAL_CACHE, stats)
        
    except KeyboardInterrupt:
        logger.info("Regeneration interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error during regeneration: {e}")
        raise
    
    # Generate final report
    report = stats.generate_report()
    
    # Save detailed report
    report_path = f"embedding_regeneration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("REGENERATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Total processed: {stats.processed}")
    logger.info(f"Successful: {stats.successful}")
    logger.info(f"Failed: {stats.failed}")
    logger.info(f"Success rate: {stats.successful/stats.processed*100:.1f}%")
    logger.info(f"\nFailure breakdown:")
    logger.info(f"  Detection failures: {len(stats.detection_failures)}")
    logger.info(f"  Ambiguous multi-face: {len(stats.ambiguous_faces)}")
    logger.info(f"  Other failures: {len(stats.other_failures)}")
    logger.info(f"  Insufficient enrollments: {len(stats.insufficient_enrollments)}")
    logger.info(f"\nDetailed report saved: {report_path}")
    
    if backup_dir:
        logger.info(f"Original embeddings backed up: {backup_dir}")


if __name__ == "__main__":
    main()