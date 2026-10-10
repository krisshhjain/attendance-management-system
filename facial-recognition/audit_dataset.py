#!/usr/bin/env python3
"""
Dataset multi-face audit script.

Scans every image in the dataset and reports:
- How many images have multiple detected faces
- Which specific files contain multiple faces  
- Bounding box sizes and ratios for multi-face images
- Summary statistics by identity

Saves results as JSON for manual review of flagged images.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from face_utils import get_face_details

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Dataset configuration
DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"
VAL_DIR = DATASET_ROOT / "val"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def get_images_in_directory(directory: Path) -> List[Path]:
    """Get all image files recursively from a directory."""
    if not directory.exists():
        return []
    
    images = []
    for item in directory.rglob("*"):
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(item)
    
    return sorted(images)


def audit_single_image(img_path: Path) -> Dict:
    """Audit a single image for multi-face detection."""
    try:
        # Get relative path for reporting
        rel_path = img_path.relative_to(DATASET_ROOT)
        
        # Extract identity from path (assuming structure like train/n000020/image.jpg)
        parts = rel_path.parts
        if len(parts) >= 2:
            identity = parts[1]  # train/VAL -> identity
        else:
            identity = "unknown"
        
        # Get face detection details
        face_details = get_face_details(str(img_path), "retinaface")
        num_faces = len(face_details)
        
        result = {
            "image_path": str(rel_path),
            "identity": identity,
            "num_faces": num_faces,
            "face_details": face_details,
            "is_multi_face": num_faces > 1,
            "has_detection_failure": num_faces == 0,
        }
        
        # Calculate area ratios for multi-face images
        if num_faces >= 2:
            areas = sorted([f['area'] for f in face_details], reverse=True)
            result["largest_face_area"] = areas[0]
            result["second_largest_area"] = areas[1]
            result["area_ratio"] = areas[1] / areas[0] if areas[0] > 0 else 0
            result["is_ambiguous"] = result["area_ratio"] >= (1.0 / 1.5)  # Within 1.5x tolerance
        
        if num_faces > 0:
            logger.debug(f"✓ {rel_path}: {num_faces} face(s)")
        else:
            logger.warning(f"✗ {rel_path}: No faces detected")
            
        return result
        
    except Exception as e:
        logger.error(f"Error processing {img_path}: {e}")
        return {
            "image_path": str(img_path.relative_to(DATASET_ROOT)),
            "identity": "error",
            "num_faces": -1,
            "error": str(e),
            "is_multi_face": False,
            "has_detection_failure": True,
        }


def audit_dataset_parallel(dataset_dir: Path, max_workers: int = 4) -> List[Dict]:
    """Audit all images in a dataset directory using parallel processing."""
    if not dataset_dir.exists():
        logger.warning(f"Dataset directory not found: {dataset_dir}")
        return []
    
    # Get all images
    images = get_images_in_directory(dataset_dir)
    logger.info(f"Found {len(images)} images in {dataset_dir}")
    
    if not images:
        return []
    
    # Process images in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_image = {executor.submit(audit_single_image, img): img for img in images}
        
        # Collect results as they complete
        for future in as_completed(future_to_image):
            try:
                result = future.result()
                results.append(result)
                
                # Progress logging every 50 images
                if len(results) % 50 == 0:
                    logger.info(f"Processed {len(results)}/{len(images)} images...")
                    
            except Exception as e:
                img_path = future_to_image[future]
                logger.error(f"Failed to process {img_path}: {e}")
    
    return results


def generate_audit_statistics(results: List[Dict]) -> Dict:
    """Generate summary statistics from audit results."""
    total_images = len(results)
    if total_images == 0:
        return {}
    
    # Basic counts
    multi_face_images = [r for r in results if r.get("is_multi_face", False)]
    detection_failures = [r for r in results if r.get("has_detection_failure", False)]
    ambiguous_images = [r for r in results if r.get("is_ambiguous", False)]
    successful_single_face = [r for r in results if r.get("num_faces", 0) == 1]
    
    # Per-identity statistics
    identity_stats = {}
    for result in results:
        identity = result.get("identity", "unknown")
        if identity not in identity_stats:
            identity_stats[identity] = {
                "total_images": 0,
                "single_face": 0,
                "multi_face": 0,
                "detection_failures": 0,
                "ambiguous": 0
            }
        
        stats = identity_stats[identity]
        stats["total_images"] += 1
        
        num_faces = result.get("num_faces", 0)
        if num_faces == 1:
            stats["single_face"] += 1
        elif num_faces > 1:
            stats["multi_face"] += 1
            if result.get("is_ambiguous", False):
                stats["ambiguous"] += 1
        elif num_faces == 0:
            stats["detection_failures"] += 1
    
    # Problematic identities (high failure rate)
    problematic_identities = []
    for identity, stats in identity_stats.items():
        if stats["total_images"] >= 3:  # Only consider identities with enough images
            problem_rate = (stats["multi_face"] + stats["detection_failures"]) / stats["total_images"]
            if problem_rate >= 0.3:  # 30% or more problematic images
                problematic_identities.append({
                    "identity": identity,
                    "problem_rate": problem_rate,
                    "stats": stats
                })
    
    problematic_identities.sort(key=lambda x: x["problem_rate"], reverse=True)
    
    return {
        "summary": {
            "total_images": total_images,
            "successful_single_face": len(successful_single_face),
            "multi_face_images": len(multi_face_images),
            "detection_failures": len(detection_failures),
            "ambiguous_multi_face": len(ambiguous_images),
            "clean_rate": len(successful_single_face) / total_images,
            "multi_face_rate": len(multi_face_images) / total_images,
            "failure_rate": len(detection_failures) / total_images,
        },
        "per_identity_stats": identity_stats,
        "problematic_identities": problematic_identities,
    }


def main():
    """Main audit workflow."""
    logger.info("=" * 80)
    logger.info("DATASET MULTI-FACE AUDIT")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # Audit both train and validation sets
    all_results = []
    
    logger.info("\n" + "="*50)
    logger.info("AUDITING TRAIN SET")
    logger.info("="*50)
    train_results = audit_dataset_parallel(TRAIN_DIR)
    all_results.extend(train_results)
    
    logger.info("\n" + "="*50)
    logger.info("AUDITING VALIDATION SET")
    logger.info("="*50)
    val_results = audit_dataset_parallel(VAL_DIR)
    all_results.extend(val_results)
    
    # Generate statistics
    statistics = generate_audit_statistics(all_results)
    
    # Separate results by category for easier review
    multi_face_images = [r for r in all_results if r.get("is_multi_face", False)]
    detection_failures = [r for r in all_results if r.get("has_detection_failure", False)]
    ambiguous_images = [r for r in all_results if r.get("is_ambiguous", False)]
    
    # Create comprehensive report
    report = {
        "audit_metadata": {
            "timestamp": datetime.now().isoformat(),
            "dataset_root": str(DATASET_ROOT),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
        },
        "statistics": statistics,
        "multi_face_images": multi_face_images,
        "detection_failures": detection_failures,
        "ambiguous_multi_face": ambiguous_images,
        "all_results": all_results,  # Full detailed results
    }
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"dataset_audit_report_{timestamp}.json"
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    stats = statistics.get("summary", {})
    logger.info("\n" + "="*80)
    logger.info("AUDIT COMPLETE")
    logger.info("="*80)
    logger.info(f"Total images processed: {stats.get('total_images', 0)}")
    logger.info(f"Clean single-face images: {stats.get('successful_single_face', 0)} ({stats.get('clean_rate', 0)*100:.1f}%)")
    logger.info(f"Multi-face images: {stats.get('multi_face_images', 0)} ({stats.get('multi_face_rate', 0)*100:.1f}%)")
    logger.info(f"  - Ambiguous (similar size faces): {len(ambiguous_images)}")
    logger.info(f"Detection failures: {stats.get('detection_failures', 0)} ({stats.get('failure_rate', 0)*100:.1f}%)")
    
    # Highlight problematic identities
    problematic = statistics.get("problematic_identities", [])
    if problematic:
        logger.info(f"\nProblematic identities (≥30% failure rate):")
        for item in problematic[:10]:  # Show top 10
            identity = item["identity"]
            rate = item["problem_rate"]
            stats = item["stats"]
            logger.info(f"  {identity}: {rate*100:.1f}% failure rate ({stats['multi_face']}M + {stats['detection_failures']}F / {stats['total_images']}T)")
    
    logger.info(f"\nDetailed report saved: {report_path}")
    
    return report_path


if __name__ == "__main__":
    main()