"""
Step 3 diagnostic (auto-path version): test whether the 5 suspect source
images actually fail face detection with enforce_detection=True.

Dataset root confirmed as: D:\\dataset\\archive
This version auto-locates each identity's folder under that root (handling
common VGGFace2 layouts like archive/n000020/... or archive/train/n000020/...)
so you don't need to hand-edit paths.

Usage:
    python diagnose_step3_check_detection.py
"""

import os

DATASET_ROOT = r"D:\dataset\archive"

# identity -> filename (without extension guessing; we'll try common exts)
SUSPECT_FILES = [
    ("n000020", "0001_01"),
    ("n000020", "0002_02"),
    ("n000003", "0006_01"),
    ("n000008", "0004_01"),
    ("n000008", "0005_02"),
]

CONTROL_FILES = [
    ("n000003", "0001_01"),
    ("n000008", "0001_01"),
]

IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def find_identity_folder(root, identity):
    """Search under root for a folder named exactly `identity`, up to 3 levels deep."""
    if not os.path.isdir(root):
        return None
    direct = os.path.join(root, identity)
    if os.path.isdir(direct):
        return direct
    for level1 in os.listdir(root):
        p1 = os.path.join(root, level1)
        if not os.path.isdir(p1):
            continue
        cand = os.path.join(p1, identity)
        if os.path.isdir(cand):
            return cand
        try:
            for level2 in os.listdir(p1):
                p2 = os.path.join(p1, level2)
                if os.path.isdir(p2):
                    cand2 = os.path.join(p2, identity)
                    if os.path.isdir(cand2):
                        return cand2
        except (PermissionError, OSError):
            continue
    return None


def find_image_file(identity_folder, base_name):
    if identity_folder is None:
        return None
    for ext in IMAGE_EXTS:
        candidate = os.path.join(identity_folder, base_name + ext)
        if os.path.exists(candidate):
            return candidate
    try:
        for f in os.listdir(identity_folder):
            name, ext = os.path.splitext(f)
            if name.lower() == base_name.lower() and ext.lower() in IMAGE_EXTS:
                return os.path.join(identity_folder, f)
    except (PermissionError, OSError):
        pass
    return None


def resolve_all():
    resolved = {}
    identity_folder_cache = {}
    for identity, base_name in SUSPECT_FILES + CONTROL_FILES:
        if identity not in identity_folder_cache:
            identity_folder_cache[identity] = find_identity_folder(DATASET_ROOT, identity)
        folder = identity_folder_cache[identity]
        img = find_image_file(folder, base_name)
        resolved[f"{identity}_{base_name}"] = {
            "identity_folder": folder,
            "image_path": img,
        }
    return resolved


def test_image(label, path):
    from deepface import DeepFace
    print(f"\n--- {label} ---")
    print(f"path: {path}")
    if path is None or not os.path.exists(path):
        print("  !! Could not resolve this file on disk. See resolution details printed above.")
        return

    try:
        result = DeepFace.represent(
            img_path=path,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
        )
        n_faces = len(result)
        print(f"  enforce_detection=True: SUCCESS - {n_faces} face(s) detected")
        for i, face in enumerate(result):
            region = face.get("facial_area", {})
            conf = face.get("face_confidence", None)
            print(f"    face[{i}] region={region} confidence={conf}")
        if n_faces > 1:
            print("  !! MULTIPLE FACES DETECTED - if your original script just took "
                  "index [0] or the wrong face, this could embed the wrong person "
                  "entirely. Check which face index was actually used originally.")
    except Exception as e:
        print(f"  enforce_detection=True: FAILED - {type(e).__name__}: {e}")
        print("  >>> This confirms detection fails on this image. If your original "
              "embedding script used enforce_detection=False, it would have silently "
              "embedded a bad fallback region instead of raising this error. <<<")
        try:
            fallback = DeepFace.represent(
                img_path=path,
                model_name="ArcFace",
                detector_backend="retinaface",
                enforce_detection=False,
            )
            print(f"  enforce_detection=False: produced {len(fallback)} embedding(s) anyway "
                  f"(this is likely what silently happened during your original run).")
        except Exception as e2:
            print(f"  enforce_detection=False also failed: {e2}")


def main():
    print("=" * 70)
    print("STEP 3 DIAGNOSTIC: face detection test on suspect images")
    print("=" * 70)

    print(f"\nDataset root: {DATASET_ROOT}  (exists: {os.path.isdir(DATASET_ROOT)})")
    resolved = resolve_all()

    print("\n=== Path resolution results ===")
    for label, info in resolved.items():
        print(f"  {label}: identity_folder={info['identity_folder']}  image_path={info['image_path']}")

    print("\n\n### SUSPECT IMAGES (expected to show detection problems) ###")
    for identity, base_name in SUSPECT_FILES:
        label = f"{identity}_{base_name}"
        test_image(label, resolved[label]["image_path"])

    print("\n\n### CONTROL IMAGES (expected to detect cleanly, for comparison) ###")
    for identity, base_name in CONTROL_FILES:
        label = f"{identity}_{base_name}"
        test_image(label + "_control", resolved[label]["image_path"])

    print("\n" + "=" * 70)
    print("If the suspect images throw detection errors (or need the enforce_detection=False "
          "fallback) while the control images detect cleanly with one confident face, that "
          "confirms the root cause: silent enforce_detection=False fallbacks on poor-quality "
          "source photos.")
    print("FIX: regenerate embeddings with enforce_detection=True, catch the exception "
          "per-image, log/skip failed images instead of silently embedding garbage, and "
          "manually replace or re-shoot the underlying bad photos (especially n000020's "
          "enrollment images 0001_01 and 0002_02, which appear to be degenerate/attractor "
          "embeddings that other bad detections keep falsely matching).")
    print("=" * 70)


if __name__ == "__main__":
    main()