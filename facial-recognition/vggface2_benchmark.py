import numpy as np
from pathlib import Path
import random
import time
from face_utils import extract_primary_face_embedding


DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"
VAL_DIR = DATASET_ROOT / "val"

NUM_IDENTITIES = 20
ENROLLMENT_IMAGES = 3
QUERY_IMAGES = 3

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def get_images(directory):
    return sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
    )


def get_embedding(image_path):
    embedding = extract_primary_face_embedding(
        img_path=str(image_path),
        model_name="ArcFace",
        detector_backend="retinaface",
        normalize=True,
        dtype=np.float32
    )
    
    return embedding


def cosine_distance(embedding1, embedding2):
    return 1 - np.dot(embedding1, embedding2)


train_identities = []

for identity_dir in sorted(TRAIN_DIR.iterdir()):
    if not identity_dir.is_dir():
        continue

    images = get_images(identity_dir)

    if len(images) >= ENROLLMENT_IMAGES + QUERY_IMAGES:
        train_identities.append((identity_dir.name, images))


if len(train_identities) < NUM_IDENTITIES:
    raise RuntimeError(
        f"Only {len(train_identities)} identities have enough images."
    )


selected_identities = train_identities[:NUM_IDENTITIES]

print(f"Selected identities: {len(selected_identities)}")
print(
    f"Images per identity: "
    f"{ENROLLMENT_IMAGES} enrollment + {QUERY_IMAGES} query"
)

templates = {}
queries = []

total_start = time.time()

for identity, images in selected_identities:
    enrollment = images[:ENROLLMENT_IMAGES]
    query_images = images[
        ENROLLMENT_IMAGES:
        ENROLLMENT_IMAGES + QUERY_IMAGES
    ]

    print(f"\nProcessing {identity}")

    enrollment_embeddings = []

    for image in enrollment:
        print(f"  Enrollment: {image.name}")
        enrollment_embeddings.append(get_embedding(image))

    template = np.mean(enrollment_embeddings, axis=0)
    template = template / np.linalg.norm(template)

    templates[identity] = template

    for image in query_images:
        print(f"  Query: {image.name}")
        queries.append(
            {
                "identity": identity,
                "image": image,
                "embedding": get_embedding(image),
            }
        )


print("\nRunning 1:N recognition...\n")

correct = 0
total = 0
genuine_distances = []
impostor_distances = []

for query in queries:
    query_embedding = query["embedding"]
    actual_identity = query["identity"]

    distances = {
        identity: cosine_distance(
            query_embedding,
            template,
        )
        for identity, template in templates.items()
    }

    predicted_identity = min(
        distances,
        key=distances.get,
    )

    best_distance = distances[predicted_identity]

    genuine_distance = distances[actual_identity]

    impostor_distances.extend(
        distance
        for identity, distance in distances.items()
        if identity != actual_identity
    )

    genuine_distances.append(genuine_distance)

    total += 1

    if predicted_identity == actual_identity:
        correct += 1

    print(
        f"{query['image'].name:20} "
        f"actual={actual_identity:8} "
        f"predicted={predicted_identity:8} "
        f"distance={best_distance:.4f}"
    )


accuracy = correct / total

print("\nRecognition Results")
print("-------------------")

print(f"Queries: {total}")
print(f"Correct: {correct}")
print(f"Accuracy: {accuracy:.4f}")

print("\nGenuine distances")
print(f"Min:  {min(genuine_distances):.4f}")
print(f"Max:  {max(genuine_distances):.4f}")
print(f"Mean: {np.mean(genuine_distances):.4f}")

print("\nImpostor distances")
print(f"Min:  {min(impostor_distances):.4f}")
print(f"Max:  {max(impostor_distances):.4f}")
print(f"Mean: {np.mean(impostor_distances):.4f}")

print(
    f"\nTotal processing time: "
    f"{time.time() - total_start:.2f} seconds"
)
