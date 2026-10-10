import numpy as np
from pathlib import Path
import time
from face_utils import extract_primary_face_embedding


DATASET_ROOT = Path(r"D:\dataset\archive")
TRAIN_DIR = DATASET_ROOT / "train"

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


def normalize(embedding):
    return embedding / np.linalg.norm(embedding)


def average_template(embeddings):
    return normalize(np.mean(embeddings, axis=0))


def evaluate(templates, queries):
    correct = 0
    total = 0
    errors = []

    for query in queries:
        actual = query["identity"]
        query_embedding = query["embedding"]

        distances = {
            identity: cosine_distance(
                query_embedding,
                template,
            )
            for identity, template in templates.items()
        }

        predicted = min(
            distances,
            key=distances.get,
        )

        best_distance = distances[predicted]

        total += 1

        if predicted == actual:
            correct += 1
        else:
            errors.append(
                {
                    "image": query["image"].name,
                    "actual": actual,
                    "predicted": predicted,
                    "distance": best_distance,
                }
            )

    return correct / total, errors


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
        f"Only {len(train_identities)} identities have enough images."
    )


selected_identities = train_identities[:NUM_IDENTITIES]

print(f"Selected identities: {len(selected_identities)}")
print(
    f"Images per identity: "
    f"{ENROLLMENT_IMAGES} enrollment + {QUERY_IMAGES} query"
)

embeddings = {}
queries = []

total_start = time.time()

for identity, images in selected_identities:
    enrollment = images[:ENROLLMENT_IMAGES]

    query_images = images[
        ENROLLMENT_IMAGES:
        ENROLLMENT_IMAGES + QUERY_IMAGES
    ]

    print(f"\nProcessing {identity}")

    identity_embeddings = []

    for image in enrollment:
        print(f"  Enrollment: {image.name}")

        identity_embeddings.append(
            get_embedding(image)
        )

    embeddings[identity] = identity_embeddings

    for image in query_images:
        print(f"  Query: {image.name}")

        queries.append(
            {
                "identity": identity,
                "image": image,
                "embedding": get_embedding(image),
            }
        )


print("\nEmbeddings complete.")
print(
    f"Embedding extraction time: "
    f"{time.time() - total_start:.2f} seconds"
)


strategies = {}


average_templates = {}

for identity, identity_embeddings in embeddings.items():
    average_templates[identity] = average_template(
        identity_embeddings
    )

strategies["3-image average"] = average_templates


individual_templates = {}

for identity, identity_embeddings in embeddings.items():
    individual_templates[identity] = identity_embeddings

individual_correct = 0
individual_total = 0
individual_errors = []

for query in queries:
    actual = query["identity"]
    query_embedding = query["embedding"]

    distances = {}

    for identity, identity_templates in individual_templates.items():
        distances[identity] = min(
            cosine_distance(
                query_embedding,
                template,
            )
            for template in identity_templates
        )

    predicted = min(
        distances,
        key=distances.get,
    )

    if predicted == actual:
        individual_correct += 1
    else:
        individual_errors.append(
            {
                "image": query["image"].name,
                "actual": actual,
                "predicted": predicted,
                "distance": distances[predicted],
            }
        )

    individual_total += 1


leave_one_out_templates = {}

for identity, identity_embeddings in embeddings.items():
    templates_for_identity = []

    for excluded_index in range(ENROLLMENT_IMAGES):
        remaining = [
            embedding
            for index, embedding in enumerate(identity_embeddings)
            if index != excluded_index
        ]

        templates_for_identity.append(
            average_template(remaining)
        )

    leave_one_out_templates[identity] = templates_for_identity


leave_one_out_correct = 0
leave_one_out_total = 0
leave_one_out_errors = []

for query in queries:
    actual = query["identity"]
    query_embedding = query["embedding"]

    distances = {}

    for identity, identity_templates in leave_one_out_templates.items():
        distances[identity] = min(
            cosine_distance(
                query_embedding,
                template,
            )
            for template in identity_templates
        )

    predicted = min(
        distances,
        key=distances.get,
    )

    if predicted == actual:
        leave_one_out_correct += 1
    else:
        leave_one_out_errors.append(
            {
                "image": query["image"].name,
                "actual": actual,
                "predicted": predicted,
                "distance": distances[predicted],
            }
        )

    leave_one_out_total += 1


average_accuracy, average_errors = evaluate(
    average_templates,
    queries,
)


individual_accuracy = (
    individual_correct / individual_total
)


leave_one_out_accuracy = (
    leave_one_out_correct / leave_one_out_total
)


print("\n")
print("=" * 70)
print("ENROLLMENT STRATEGY RESULTS")
print("=" * 70)


print(
    f"\n3-image average template:"
    f" {average_accuracy:.4f}"
)


print(
    f"Individual enrollment matching:"
    f" {individual_accuracy:.4f}"
)


print(
    f"Leave-one-out average:"
    f" {leave_one_out_accuracy:.4f}"
)


print("\nErrors")
print("-" * 70)


print("\n3-image average errors:")

if average_errors:
    for error in average_errors:
        print(
            f"  {error['image']:15} "
            f"actual={error['actual']:8} "
            f"predicted={error['predicted']:8} "
            f"distance={error['distance']:.4f}"
        )
else:
    print("  None")


print("\nIndividual enrollment errors:")

if individual_errors:
    for error in individual_errors:
        print(
            f"  {error['image']:15} "
            f"actual={error['actual']:8} "
            f"predicted={error['predicted']:8} "
            f"distance={error['distance']:.4f}"
        )
else:
    print("  None")


print("\nLeave-one-out errors:")

if leave_one_out_errors:
    for error in leave_one_out_errors:
        print(
            f"  {error['image']:15} "
            f"actual={error['actual']:8} "
            f"predicted={error['predicted']:8} "
            f"distance={error['distance']:.4f}"
        )
else:
    print("  None")


print("\n" + "=" * 70)
print(
    f"Total processing time: "
    f"{time.time() - total_start:.2f} seconds"
)
print("=" * 70)