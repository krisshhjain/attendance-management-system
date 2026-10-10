import numpy as np
from pathlib import Path
import json
import time
from face_utils import extract_primary_face_embedding


DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"
VAL_DIR = DATASET_ROOT / "val"

CACHE_DIR = Path("embeddings")
TRAIN_CACHE = CACHE_DIR / "train"
VAL_CACHE = CACHE_DIR / "val"

NUM_IDENTITIES = 20
ENROLLMENT_IMAGES = 3
QUERY_IMAGES = 3
UNKNOWN_IDENTITIES = 20
UNKNOWN_IMAGES_PER_IDENTITY = 3

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def get_images(directory):
    return sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
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


def load_or_create_embedding(image_path, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_name = (
        image_path.parent.name
        + "_"
        + image_path.stem
        + ".npy"
    )

    cache_path = cache_dir / cache_name

    if cache_path.exists():
        return np.load(cache_path)

    print(f"Embedding: {image_path}")

    embedding = get_embedding(image_path)

    np.save(cache_path, embedding)

    return embedding


def cosine_distance(embedding1, embedding2):
    return 1 - np.dot(embedding1, embedding2)


CACHE_DIR.mkdir(exist_ok=True)


train_identities = []

for identity_dir in sorted(TRAIN_DIR.iterdir()):
    if not identity_dir.is_dir():
        continue

    images = get_images(identity_dir)

    if len(images) >= ENROLLMENT_IMAGES + QUERY_IMAGES:
        train_identities.append(
            (identity_dir.name, images)
        )


if len(train_identities) < NUM_IDENTITIES:
    raise RuntimeError(
        f"Only {len(train_identities)} suitable identities found."
    )


selected_identities = train_identities[:NUM_IDENTITIES]

print(f"Selected known identities: {len(selected_identities)}")


templates = {}
known_queries = []

start = time.time()

for identity, images in selected_identities:
    enrollment_images = images[:ENROLLMENT_IMAGES]
    query_images = images[
        ENROLLMENT_IMAGES:
        ENROLLMENT_IMAGES + QUERY_IMAGES
    ]

    print(f"\nKnown identity: {identity}")

    enrollment_embeddings = []

    for image in enrollment_images:
        embedding = load_or_create_embedding(
            image,
            TRAIN_CACHE,
        )

        enrollment_embeddings.append(embedding)

    template = np.mean(
        enrollment_embeddings,
        axis=0,
    )

    template = template / np.linalg.norm(template)

    templates[identity] = template

    for image in query_images:
        embedding = load_or_create_embedding(
            image,
            TRAIN_CACHE,
        )

        known_queries.append(
            {
                "identity": identity,
                "image": str(image),
                "embedding": embedding,
            }
        )


print("\nKnown-person recognition")


known_correct = 0
known_total = 0
known_results = []

for query in known_queries:
    distances = {
        identity: cosine_distance(
            query["embedding"],
            template,
        )
        for identity, template in templates.items()
    }

    ranked_matches = sorted(
    distances.items(),
    key=lambda item: item[1],
)

    predicted_identity, best_distance = ranked_matches[0]

    second_identity, second_distance = ranked_matches[1]

    margin = second_distance - best_distance

    actual_identity = query["identity"]

    correct = predicted_identity == actual_identity

    if correct:
        known_correct += 1

    known_total += 1

    known_results.append(
    {
        "actual": actual_identity,
        "predicted": predicted_identity,
        "distance": float(best_distance),
        "second_distance": float(second_distance),
        "margin": float(margin),
        "correct": correct,
    }
)

    print(
    f"{Path(query['image']).name:20} "
    f"actual={actual_identity:8} "
    f"predicted={predicted_identity:8} "
    f"best={best_distance:.4f} "
    f"second={second_distance:.4f} "
    f"margin={margin:.4f}"
)


known_accuracy = known_correct / known_total

print("\nKnown-person results")
print("--------------------")
print(f"Queries: {known_total}")
print(f"Correct: {known_correct}")
print(f"Accuracy: {known_accuracy:.4f}")


val_identities = [
    directory
    for directory in sorted(VAL_DIR.iterdir())
    if directory.is_dir()
]

if len(val_identities) < UNKNOWN_IDENTITIES:
    raise RuntimeError(
        f"Only {len(val_identities)} validation identities found."
    )


unknown_queries = []

selected_unknowns = val_identities[:UNKNOWN_IDENTITIES]

print(
    f"\nSelected unknown identities: "
    f"{len(selected_unknowns)}"
)


for identity_dir in selected_unknowns:
    images = get_images(identity_dir)

    if len(images) < UNKNOWN_IMAGES_PER_IDENTITY:
        continue

    query_images = images[:UNKNOWN_IMAGES_PER_IDENTITY]

    print(f"\nUnknown identity: {identity_dir.name}")

    for image in query_images:
        embedding = load_or_create_embedding(
            image,
            VAL_CACHE,
        )

        unknown_queries.append(
            {
                "identity": identity_dir.name,
                "image": str(image),
                "embedding": embedding,
            }
        )


print("\nUnknown-person recognition")


unknown_results = []

for query in unknown_queries:
    distances = {
        identity: cosine_distance(
            query["embedding"],
            template,
        )
        for identity, template in templates.items()
    }

    ranked_matches = sorted(
    distances.items(),
    key=lambda item: item[1],
)

    predicted_identity, best_distance = ranked_matches[0]

    second_identity, second_distance = ranked_matches[1]

    margin = second_distance - best_distance    

    unknown_results.append(
        {
            "identity": query["identity"],
            "predicted": predicted_identity,
            "distance": float(best_distance),
            "second_distance": float(second_distance),
            "margin": float(margin),
        }
    )

    print(
    f"{Path(query['image']).name:20} "
    f"unknown={query['identity']:8} "
    f"nearest={predicted_identity:8} "
    f"best={best_distance:.4f} "
    f"second={second_distance:.4f} "
    f"margin={margin:.4f}"
)


print("\nUnknown-person results")
print("----------------------")
print(f"Unknown queries: {len(unknown_results)}")

unknown_distances = [
    result["distance"]
    for result in unknown_results
]

print(
    f"Nearest-match minimum: "
    f"{min(unknown_distances):.4f}"
)

print(
    f"Nearest-match maximum: "
    f"{max(unknown_distances):.4f}"
)

print(
    f"Nearest-match mean: "
    f"{np.mean(unknown_distances):.4f}"
)


output = {
    "known_accuracy": known_accuracy,
    "known_results": known_results,
    "unknown_results": unknown_results,
}

with open(
    "vggface2_open_set_results.json",
    "w",
) as file:
    json.dump(
        output,
        file,
        indent=2,
    )


print(
    f"\nTotal runtime: "
    f"{time.time() - start:.2f} seconds"
)