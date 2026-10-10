import numpy as np
from face_utils import extract_primary_face_embedding


def get_embedding(image_path, detector):
    return extract_primary_face_embedding(
        img_path=image_path,
        model_name="ArcFace",
        detector_backend=detector,
        normalize=False,
        dtype=float
    )


def cosine_distance(a, b):
    similarity = np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )
    return 1 - similarity


for detector in ["retinaface", "opencv"]:
    person1 = get_embedding("person1.jpg", detector)
    person2 = get_embedding("person2.png", detector)

    distance = cosine_distance(person1, person2)

    print(f"{detector}: {distance}")