import numpy as np
from face_utils import extract_primary_face_embedding


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


person1_photo1 = get_embedding("person1.jpg")
person1_photo2 = get_embedding("person1_2.jpeg")
person2_photo1 = get_embedding("person2.png")

same_person_distance = cosine_distance(
    person1_photo1,
    person1_photo2,
)

different_person_distance = cosine_distance(
    person1_photo1,
    person2_photo1,
)

print("Same person distance:", same_person_distance)
print("Different person distance:", different_person_distance)