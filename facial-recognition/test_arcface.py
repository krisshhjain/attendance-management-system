from deepface import DeepFace

result = DeepFace.verify(
    img1_path="person1.jpg",
    img2_path="person1_2.jpg",
    model_name="ArcFace",
    detector_backend="retinaface",
    distance_metric="cosine",
)

print(result)