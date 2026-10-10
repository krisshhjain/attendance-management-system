import numpy as np
from pathlib import Path
import time
import json
from datetime import datetime
from face_utils import extract_primary_face_embedding, FaceExtractionError


DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"
VAL_DIR = DATASET_ROOT / "val"

# Original 20 identities from the experiment
ORIGINAL_IDENTITIES = [
    'n000002', 'n000003', 'n000004', 'n000005', 'n000006', 'n000007', 'n000008', 
    'n000010', 'n000011', 'n000012', 'n000013', 'n000014', 'n000015', 'n000016', 
    'n000017', 'n000018', 'n000019', 'n000020', 'n000021', 'n000022'
]

# Identities to exclude due to data quality issues
EXCLUDED_IDENTITIES = {
    'n000006': 'duplicate_indices',  # 0004_01, 0004_02, 0004_03 (face crops)
    'n000012': 'duplicate_indices', # 0004_01, 0004_02 (face crops)  
    'n000017': 'duplicate_indices', # 0002_01, 0002_02 (face crops)
    'n000020': 'insufficient_usable', # ambiguous multi-face rejection
    'n000021': 'insufficient_usable'  # ambiguous multi-face rejection
}

# Clean identities for evaluation
CLEAN_IDENTITIES = [id for id in ORIGINAL_IDENTITIES if id not in EXCLUDED_IDENTITIES]

# File mappings from the original experiment
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

ENROLLMENT_IMAGES = 3
QUERY_IMAGES = 3

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]


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


def safe_get_embedding(identity: str, filename: str) -> np.ndarray:
    """Safely extract embedding with proper error handling."""
    try:
        identity_dir = TRAIN_DIR / identity
        img_path = find_image_file(identity_dir, filename)
        
        embedding = extract_primary_face_embedding(
            img_path=str(img_path),
            model_name="ArcFace",
            detector_backend="retinaface",
            normalize=True,
            dtype=np.float32
        )
        
        return embedding
        
    except Exception as e:
        print(f"    ERROR extracting {identity}/{filename}: {e}")
        return None


def cosine_distance(embedding1, embedding2):
    return 1 - np.dot(embedding1, embedding2)


def evaluate_identity(identity: str, filenames: list) -> dict:
    """Evaluate a single identity and return results."""
    print(f"\nProcessing {identity}")
    
    # Try to extract all embeddings
    embeddings = {}
    failed_extractions = []
    
    for i, filename in enumerate(filenames):
        print(f"  Image {i+1}/6: {filename}")
        embedding = safe_get_embedding(identity, filename)
        
        if embedding is not None:
            embeddings[filename] = embedding
        else:
            failed_extractions.append(filename)
    
    successful_count = len(embeddings)
    print(f"  Successfully extracted: {successful_count}/6 embeddings")
    
    if len(failed_extractions) > 0:
        print(f"  Failed extractions: {failed_extractions}")
    
    # Check if we have enough for enrollment + query
    if successful_count < (ENROLLMENT_IMAGES + QUERY_IMAGES):
        print(f"  ⚠️  INSUFFICIENT IMAGES: {successful_count} < {ENROLLMENT_IMAGES + QUERY_IMAGES} required")
        return {
            'identity': identity,
            'status': 'insufficient_images',
            'successful_embeddings': successful_count,
            'failed_extractions': failed_extractions,
            'enrollment_embeddings': [],
            'queries': []
        }
    
    # Split into enrollment and query
    successful_files = list(embeddings.keys())
    enrollment_files = successful_files[:ENROLLMENT_IMAGES]
    query_files = successful_files[ENROLLMENT_IMAGES:ENROLLMENT_IMAGES + QUERY_IMAGES]
    
    print(f"  Enrollment: {enrollment_files}")
    print(f"  Query: {query_files}")
    
    # Create template from enrollment images
    enrollment_embeddings = [embeddings[f] for f in enrollment_files]
    template = np.mean(enrollment_embeddings, axis=0)
    template = template / np.linalg.norm(template)
    
    # Evaluate queries
    query_results = []
    for query_file in query_files:
        query_embedding = embeddings[query_file]
        distance = cosine_distance(template, query_embedding)
        
        query_results.append({
            'query_file': query_file,
            'distance': distance,
            'embedding': query_embedding
        })
        
        print(f"    Query {query_file}: distance = {distance:.4f}")
    
    return {
        'identity': identity,
        'status': 'evaluated',
        'successful_embeddings': successful_count,
        'failed_extractions': failed_extractions,
        'enrollment_files': enrollment_files,
        'query_files': query_files,
        'enrollment_embeddings': enrollment_embeddings,
        'template': template,
        'queries': query_results
    }


def main():
    print("=" * 80)
    print("FIXED VGGFace2 BENCHMARK - CLEAN DATA ONLY")
    print("=" * 80)
    print(f"Original experiment: {len(ORIGINAL_IDENTITIES)} identities")
    print(f"Excluded identities: {len(EXCLUDED_IDENTITIES)} ({list(EXCLUDED_IDENTITIES.keys())})")
    print(f"Clean identities for evaluation: {len(CLEAN_IDENTITIES)}")
    print(f"Required per identity: {ENROLLMENT_IMAGES} enrollment + {QUERY_IMAGES} query = {ENROLLMENT_IMAGES + QUERY_IMAGES} total")
    
    # Print exclusion reasons
    print(f"\nExclusion reasons:")
    for identity, reason in EXCLUDED_IDENTITIES.items():
        if reason == 'duplicate_indices':
            print(f"  {identity}: Face crops from same source image")
        elif reason == 'insufficient_usable':
            print(f"  {identity}: Ambiguous multi-face images rejected")
    
    # Track results
    all_results = []
    templates = {}
    all_queries = []
    excluded_identities = []
    
    total_start = time.time()
    
    # Evaluate each clean identity only
    for identity in CLEAN_IDENTITIES:
        filenames = ORIGINAL_FILES[identity]
        result = evaluate_identity(identity, filenames)
        all_results.append(result)
        
        if result['status'] == 'evaluated':
            templates[identity] = result['template']
            
            # Add queries for recognition evaluation
            for query_info in result['queries']:
                all_queries.append({
                    'true_identity': identity,
                    'query_file': query_info['query_file'],
                    'embedding': query_info['embedding']
                })
                
        else:
            excluded_identities.append(identity)
            print(f"  ❌ EXCLUDED from evaluation")
    
    print(f"\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    
    evaluated_identities = len(templates)
    total_queries = len(all_queries)
    
    print(f"Identities with sufficient images: {evaluated_identities}")
    print(f"Excluded identities: {excluded_identities}")
    print(f"Total queries to evaluate: {total_queries}")
    
    if evaluated_identities == 0:
        print("❌ NO IDENTITIES TO EVALUATE")
        return
    
    # Perform recognition evaluation
    print(f"\n" + "="*40)
    print("RECOGNITION RESULTS")
    print("="*40)
    
    correct_predictions = 0
    total_predictions = 0
    detailed_results = []
    
    for query in all_queries:
        query_embedding = query['embedding']
        true_identity = query['true_identity']
        
        # Find best match
        best_distance = float('inf')
        predicted_identity = None
        
        for template_identity, template_embedding in templates.items():
            distance = cosine_distance(query_embedding, template_embedding)
            
            if distance < best_distance:
                best_distance = distance
                predicted_identity = template_identity
        
        # Check if correct
        is_correct = (predicted_identity == true_identity)
        if is_correct:
            correct_predictions += 1
        
        total_predictions += 1
        
        # Store detailed result
        detailed_results.append({
            'query_file': query['query_file'],
            'true_identity': true_identity,
            'predicted_identity': predicted_identity,
            'distance': float(best_distance),  # Cast to Python float
            'correct': is_correct
        })
        
        status = "✓" if is_correct else "✗"
        print(f"{status} Query {query['query_file']} (true: {true_identity}) -> predicted: {predicted_identity} (dist: {best_distance:.4f})")
    
    # Final accuracy
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
    
    print(f"\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Evaluated identities: {evaluated_identities}/{len(ORIGINAL_IDENTITIES)}")
    print(f"Correct predictions: {correct_predictions}")
    print(f"Total predictions: {total_predictions}")
    print(f"Accuracy: {accuracy:.1%} ({correct_predictions}/{total_predictions})")
    
    # Compare with original results
    print(f"\n" + "="*60)
    print("COMPARISON WITH ORIGINAL RESULTS")
    print("="*60)
    print(f"Original (with bugs): 95.0% accuracy (57/60) on 20 identities")
    print(f"Fixed (clean data): {accuracy:.1%} accuracy ({correct_predictions}/{total_predictions}) on {evaluated_identities} identities")
    
    if excluded_identities:
        print(f"\nExcluded identities due to insufficient usable images:")
        for identity in excluded_identities:
            print(f"  - {identity}")
    
    duration = time.time() - total_start
    print(f"\nTotal evaluation time: {duration:.2f} seconds")
    
    # Save results to JSON (strip embeddings to avoid bloat)
    clean_per_identity_results = []
    for result in all_results:
        clean_result = {
            'identity': result['identity'],
            'status': result['status'],
            'successful_embeddings': result['successful_embeddings'],
            'failed_extractions': result['failed_extractions']
        }
        
        # Add enrollment/query file lists for metadata
        if result['status'] == 'evaluated':
            clean_result['enrollment_files'] = result['enrollment_files']
            clean_result['query_files'] = result['query_files']
        
        clean_per_identity_results.append(clean_result)
    results_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'evaluated_identities': evaluated_identities,
            'total_original_identities': len(ORIGINAL_IDENTITIES),
            'excluded_identities': excluded_identities,
            'correct_predictions': correct_predictions,
            'total_predictions': total_predictions,
            'accuracy': accuracy,
            'evaluation_time_seconds': duration
        },
        'comparison': {
            'original_accuracy': 0.95,
            'original_correct': 57,
            'original_total': 60,
            'original_identities': 20,
            'fixed_accuracy': accuracy,
            'fixed_correct': correct_predictions,
            'fixed_total': total_predictions,
            'fixed_identities': evaluated_identities
        },
        'detailed_results': detailed_results,
        'per_identity_results': clean_per_identity_results
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = f"benchmark_results_fixed_{timestamp}.json"
    
    with open(results_path, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved: {results_path}")


if __name__ == "__main__":
    main()