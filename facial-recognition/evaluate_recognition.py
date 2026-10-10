import numpy as np
from itertools import combinations
from pathlib import Path
from face_utils import extract_primary_face_embedding


PEOPLE = {
    "person1": [
        "person1/person1.jpg",
        "person1/person1_2.jpeg",
    ],
    "person2": [
        "person2/person2_1.jpeg",
        "person2/person2.png",
    ],
    "person3": [
    "person 3/person3.jpg",
    "person 3/person3_2.jpg",
],
    "person4": [
        "person4/person4.jpg",
        "person4/person 4_2.jpg",
    ],
}


def get_embedding(image_path):
    return extract_primary_face_embedding(
        img_path=image_path,
        model_name="ArcFace",
        detector_backend="retinaface",
        normalize=False,
        dtype=float
    )


def cosine_distance(embedding1, embedding2):
    similarity = np.dot(embedding1, embedding2) / (
        np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
    )

    return 1 - similarity


embeddings = {}

print("\nGenerating embeddings...\n")

for person, images in PEOPLE.items():
    for image in images:
        print(f"Processing {image}")

        embeddings[image] = get_embedding(image)

print("\nCalculating pairwise distances...\n")

results = []

for image1, image2 in combinations(embeddings.keys(), 2):
    person1 = image1.split("/")[0]
    person2 = image2.split("/")[0]

    distance = cosine_distance(
        embeddings[image1],
        embeddings[image2],
    )

    pair_type = "GENUINE" if person1 == person2 else "IMPOSTOR"

    results.append(
        {
            "image1": image1,
            "image2": image2,
            "type": pair_type,
            "distance": distance,
        }
    )

for result in results:
    print(
        f"{result['type']:8} | "
        f"{result['distance']:.4f} | "
        f"{result['image1']} <-> {result['image2']}"
    )

genuine = [
    r["distance"]
    for r in results
    if r["type"] == "GENUINE"
]

impostor = [
    r["distance"]
    for r in results
    if r["type"] == "IMPOSTOR"
]

print("\nSummary")
print("-------")

print(f"Genuine pairs: {len(genuine)}")
print(f"Impostor pairs: {len(impostor)}")

print(f"\nGenuine min:  {min(genuine):.4f}")
print(f"Genuine max:  {max(genuine):.4f}")
print(f"Genuine mean: {np.mean(genuine):.4f}")

print(f"\nImpostor min:  {min(impostor):.4f}")
print(f"Impostor max:  {max(impostor):.4f}")
print(f"Impostor mean: {np.mean(impostor):.4f}")