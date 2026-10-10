#!/usr/bin/env python3
"""
Scoped embedding regeneration script.

Regenerates embeddings ONLY for the 20 identities and specific 6 files per identity
that were used in the original experiment, based on the backed-up cache files.
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
import numpy as np

from face_utils import extract_primary_face_embedding, FaceExtractionError, get_face_details

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scoped_regeneration.log'),
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

# Exact file list from original experiment (based on backup)
ORIGINAL_FILES = {
    'n000002': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000003': ['0001_01', '0002_01', '0003_01', '0004_02', '0005_01', '0006_01'],
    'n000004': ['0001_01', '0002_02', '0003_01', '0004_02', '0005_01', '0006_01'],
    'n000005': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000006': ['0001_01', '0002_02', '0003_01', '0004_01', '0004_02', '0004_03'],
    'n000007': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_02', '0006_02'],
    'n000008': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_02', '0006_01'],
    'n000010': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000011': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000012': ['0001_01', '0002_01', '0003_01', '0004_01', '0004_02', '0005_03'],
    'n000013': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000014': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000015': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000016': ['0001_02', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000017': ['0001_01', '0002_01', '0002_02', '0003_01', '0004_01', '0005_01'],
    'n000018': ['0001_01', '0002_01', '0003_02', '0004_01', '0005_01', '0006_01'],
    'n000019': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000020': ['0001_01', '0002_02', '0003_01', '0004_01', '0005_01', '0006_01'],
    'n000021': ['0001_01', '0002_02', '0003_01', '0004_01', '0005_02', '0006_01'],
    'n000022': ['0001_01', '0002_01', '0003_01', '0004_01', '0005_01', '0006_01'],
}

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]


class ScopedRegenerationStats:
    """Track scoped regeneration statistics."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.processed = 0
        self.successful = 0
        self.failed = 0
        
        self.detection_failures = []
        self.ambiguous_faces = []
        self.other_failures = []
        self.file_not_found = []
        
        self.per_identity_results = {}
    
    def add_success(self, identity: str, filename: str, img_path: Path):
        """Record successful embedding extraction."""
        self.processed += 1
        self.successful += 1
        
        if identity not in self.per_identity_results:
            self.per_identity_results[identity] = {'successful': [], 'failed': []}
        
        self.per_identity_results[identity]['successful'].append(filename)
        logger.debug(f"✓ {identity}/{filename}")
    
    def add_failure(self, identity: str, filename: str, img_path: Path, error: Exception, face_details=None):
        """Record failed embedding extraction."""
        self.processed += 1
        self.failed += 1
        
        if identity not in self.per_identity_results:
            self.per_identity_results[identity] = {'successful': [], 'failed': []}
        
        self.per_identity_results[identity]['failed'].append({
            'filename': filename,
            'error': str(error),
            'error_type': type(error).__name__
        })
        
        failure_info = {
            'identity': identity,
            'filename': filename, 
            'image_path': str(img_path) if img_path else 'not_found',
            'error_type': type(error).__name__,
            'error_message': str(error),
        }
        
        if face_details:
            failure_info['face_details'] = face_details
            if len(face_details) >= 2:
                areas = sorted([f['area'] for f in face_details], reverse=True)
                failure_info['largest_area'] = areas[0]
                failure_info['second_area'] = areas[1]
                failure_info['area_ratio'] = areas[1] / areas[0] if areas[0] > 0 else 0
        
        # Categorize failure
        error_msg = str(error).lower()
        if 'no such file' in error_msg or 'cannot find the path' in error_msg:
            self.file_not_found.append(failure_info)
        elif isinstance(error, FaceExtractionError):
            if 'no faces detected' in error_msg or 'detection failed' in error_msg:
                self.detection_failures.append(failure_info)
            elif 'ambiguous multi-face' in error_msg:
                self.ambiguous_faces.append(failure_info)
            else:
                self.other_failures.append(failure_info)
        else:
            self.other_failures.append(failure_info)
        
        logger.warning(f"✗ {identity}/{filename}: {error}")
    
    def generate_report(self):
        """Generate final report."""
        duration = datetime.now() - self.start_time
        
        return {
            'summary': {
                'start_time': self.start_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'total_processed': self.processed,
                'successful': self.successful,
                'failed': self.failed,
                'success_rate': self.successful / self.processed if self.processed > 0 else 0,
                'expected_files': sum(len(files) for files in ORIGINAL_FILES.values()),
            },
            'failure_breakdown': {
                'file_not_found': len(self.file_not_found),
                'detection_failures': len(self.detection_failures),
                'ambiguous_multi_face': len(self.ambiguous_faces),
                'other_failures': len(self.other_failures),
            },
            'detailed_failures': {
                'file_not_found': self.file_not_found,
                'detection_failures': self.detection_failures,
                'ambiguous_multi_face': self.ambiguous_faces,
                'other_failures': self.other_failures,
            },
            'per_identity_results': self.per_identity_results,
        }


def find_image_file(identity_dir: Path, base_filename: str) -> Path:
    """Find the actual image file given the base filename (without extension)."""
    if not identity_dir.exists():
        raise FileNotFoundError(f"Identity directory not found: {identity_dir}")
    
    # Try each possible extension
    for ext in IMAGE_EXTENSIONS:
        candidate = identity_dir / f"{base_filename}{ext}"
        if candidate.exists():
            return candidate
    
    # Case-insensitive search as fallback
    try:
        for file_path in identity_dir.iterdir():
            if file_path.is_file():
                name_no_ext = file_path.stem.lower()
                if name_no_ext == base_filename.lower():
                    return file_path
    except (PermissionError, OSError):
        pass
    
    raise FileNotFoundError(f"Image file not found: {identity_dir}/{base_filename}{{.jpg,.jpeg,.png}}")


def regenerate_scoped_embeddings():
    """Regenerate embeddings for the exact original file list."""
    logger.info("=" * 80)
    logger.info("SCOPED FACE EMBEDDING REGENERATION")
    logger.info(f"Processing {len(ORIGINAL_FILES)} identities, {sum(len(files) for files in ORIGINAL_FILES.values())} files total")
    logger.info("=" * 80)
    
    stats = ScopedRegenerationStats()
    
    # Create fresh cache directories
    TRAIN_CACHE.mkdir(parents=True, exist_ok=True)
    
    for identity, filenames in ORIGINAL_FILES.items():
        logger.info(f"\nProcessing identity {identity}: {len(filenames)} files")
        
        identity_dir = TRAIN_DIR / identity
        
        identity_successful = 0
        
        for filename in filenames:
            try:
                # Find the actual image file
                img_path = find_image_file(identity_dir, filename)
                
                # Extract embedding using the fixed function
                embedding = extract_primary_face_embedding(
                    img_path=str(img_path),
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    normalize=True,
                    dtype=np.float32
                )
                
                # Save to cache using original flat naming convention
                cache_filename = f"{identity}_{filename}.npy"
                cache_path = TRAIN_CACHE / cache_filename
                np.save(cache_path, embedding)
                
                stats.add_success(identity, filename, img_path)
                identity_successful += 1
                
            except Exception as error:
                # Get face details for better failure reporting
                face_details = None
                if 'img_path' in locals() and img_path and img_path.exists():
                    face_details = get_face_details(str(img_path), "retinaface")
                
                stats.add_failure(identity, filename, img_path if 'img_path' in locals() else None, error, face_details)
        
        logger.info(f"Identity {identity}: {identity_successful}/{len(filenames)} files successful")
    
    return stats


def main():
    """Main regeneration workflow."""
    # Run scoped regeneration
    stats = regenerate_scoped_embeddings()
    
    # Generate report
    report = stats.generate_report()
    
    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"scoped_regeneration_report_{timestamp}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("SCOPED REGENERATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Expected files: {report['summary']['expected_files']}")
    logger.info(f"Processed: {stats.processed}")
    logger.info(f"Successful: {stats.successful}")
    logger.info(f"Failed: {stats.failed}")
    logger.info(f"Success rate: {stats.successful/stats.processed*100:.1f}%")
    
    logger.info(f"\nFailure breakdown:")
    logger.info(f"  File not found: {len(stats.file_not_found)}")
    logger.info(f"  Detection failures: {len(stats.detection_failures)}")
    logger.info(f"  Ambiguous multi-face: {len(stats.ambiguous_faces)}")
    logger.info(f"  Other failures: {len(stats.other_failures)}")
    
    # Highlight problematic identities
    problematic_identities = []
    for identity, results in stats.per_identity_results.items():
        success_count = len(results['successful'])
        total_count = success_count + len(results['failed'])
        if success_count < 6:  # Should have 6 files per identity
            problematic_identities.append(f"{identity}: {success_count}/6 successful")
    
    if problematic_identities:
        logger.info(f"\nIdentities with missing files:")
        for identity_info in problematic_identities:
            logger.info(f"  {identity_info}")
    
    logger.info(f"\nDetailed report saved: {report_path}")
    
    return report_path


if __name__ == "__main__":
    main()