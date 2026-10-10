#!/usr/bin/env python3
"""
Quick scan to detect identities with multiple files sharing the same 4-digit index.

This pattern (e.g. 0004_01, 0004_02, 0004_03) indicates potential face crops 
from the same source image rather than distinct photos of the same person.
"""

from collections import defaultdict

# Original file mappings from the experiment
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


def check_duplicate_indices():
    """Check for identities with multiple files sharing the same 4-digit index."""
    
    print("="*80)
    print("CHECKING FOR DUPLICATE 4-DIGIT INDICES")
    print("="*80)
    print("Looking for identities with multiple files like 0004_01, 0004_02, 0004_03")
    print("(indicates potential face crops from same source image)")
    print()
    
    problematic_identities = []
    clean_identities = []
    
    for identity, filenames in ORIGINAL_FILES.items():
        # Group filenames by their 4-digit prefix
        index_groups = defaultdict(list)
        
        for filename in filenames:
            # Extract 4-digit prefix (e.g. "0004" from "0004_01")
            if len(filename) >= 4:
                index_prefix = filename[:4]
                index_groups[index_prefix].append(filename)
        
        # Check for any prefix with multiple files
        duplicates_found = []
        for prefix, files in index_groups.items():
            if len(files) > 1:
                duplicates_found.append((prefix, files))
        
        if duplicates_found:
            print(f"⚠️  {identity}: DUPLICATE INDICES FOUND")
            for prefix, files in duplicates_found:
                print(f"    {prefix}_xx: {files}")
            problematic_identities.append(identity)
        else:
            print(f"✅ {identity}: All unique indices")
            clean_identities.append(identity)
    
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Clean identities (unique indices): {len(clean_identities)}")
    print(f"Problematic identities (duplicate indices): {len(problematic_identities)}")
    
    if problematic_identities:
        print(f"\nProblematic identities to exclude:")
        for identity in problematic_identities:
            print(f"  - {identity}")
    
    if clean_identities:
        print(f"\nClean identities safe for evaluation:")
        for identity in clean_identities:
            print(f"  - {identity}")
    
    print(f"\nRecommendation:")
    if len(clean_identities) >= 15:  # Reasonable sample size
        print(f"✅ Proceed with {len(clean_identities)} clean identities for evaluation")
    else:
        print(f"⚠️  Only {len(clean_identities)} clean identities - consider if sample size is sufficient")
    
    return clean_identities, problematic_identities


if __name__ == "__main__":
    clean, problematic = check_duplicate_indices()