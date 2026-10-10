"""
Step 3a: find the real image directory by scanning your own scripts for
path-like strings, and by searching common drive locations for a folder
containing n000020 (or similar VGGFace2-style identity folders).

Usage:
    python find_image_root.py
"""

import os
import re
import glob

SCRIPTS_TO_SCAN = [
    "vggface2_open_set.py",
    "vggface2_benchmark.py",
    "vggface2_enrollment_experiment.py",
    "evaluate_recognition.py",
    "threshold_sweep.py",
    "margin_analysis.py",
    "test_embeddings.py",
    "test_arcface.py",
    "test_detector_comparison.py",
]

PATH_PATTERN = re.compile(
    r"""["']([A-Za-z]:[\\/][^"']+|\.{1,2}[\\/][^"']+|/[^"']+)["']"""
)


def scan_scripts():
    print("=== Scanning your scripts for path-like strings ===")
    hits = {}
    for script in SCRIPTS_TO_SCAN:
        if not os.path.exists(script):
            continue
        with open(script, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        found = set()
        for m in PATH_PATTERN.finditer(content):
            p = m.group(1)
            # only interested in things that look like dataset/image paths
            if any(kw in p.lower() for kw in
                   ("vgg", "dataset", "image", "data", "face", "n0000", "train", "val", "gallery")):
                found.add(p)
        if found:
            hits[script] = sorted(found)
            print(f"\n{script}:")
            for p in sorted(found):
                exists = os.path.exists(p)
                print(f"    {p}   {'<-- EXISTS' if exists else '(not found relative to cwd)'}")
    if not hits:
        print("  No obvious dataset paths found in script text. Open these scripts "
              "yourself and look for the variable that gets passed as img_path to "
              "DeepFace.represent(...) or similar, near the top of the file.")
    return hits


def search_for_identity_folders():
    print("\n=== Searching nearby drives/folders for an 'n000020'-style folder ===")
    # Search a handful of likely roots, shallow-first, without walking the whole C:\ drive
    # (that would take forever). Extend this list if your dataset lives elsewhere.
    candidate_roots = [
        ".", "..", "../..",
        "C:/", "D:/", "D:/attendance-management-system",
        os.path.expanduser("~"), os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
    ]
    found_any = False
    for root in candidate_roots:
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                full = os.path.join(root, entry)
                if os.path.isdir(full) and re.match(r"n0*20$|n000020$", entry, re.IGNORECASE):
                    print(f"  FOUND identity folder: {full}")
                    found_any = True
            # one level deeper, still shallow, to catch e.g. D:/datasets/vggface2/n000020
            for entry in os.listdir(root):
                sub = os.path.join(root, entry)
                if not os.path.isdir(sub):
                    continue
                try:
                    for entry2 in os.listdir(sub):
                        if re.match(r"n0*20$|n000020$", entry2, re.IGNORECASE):
                            print(f"  FOUND identity folder: {os.path.join(sub, entry2)}")
                            found_any = True
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue
    if not found_any:
        print("  Not found in the common locations checked. If your dataset lives "
              "somewhere unusual (external drive, cloud-synced folder, WSL path, etc.), "
              "just tell me the folder path directly and I'll wire it into the script.")


if __name__ == "__main__":
    scan_scripts()
    search_for_identity_folders()