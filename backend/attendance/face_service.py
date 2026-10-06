import logging
import requests
import base64
from typing import Union, Tuple, Optional, List

from employees.models import Employee, FaceProfile
from django.conf import settings

logger = logging.getLogger(__name__)


class FaceExtractionError(Exception):
    """Raised when face extraction fails or produces ambiguous results."""
    pass


class FaceLivenessError(FaceExtractionError):
    """A safe, machine-readable rejection from the FR liveness gate."""

    def __init__(self, status: str):
        self.status = status
        if status == "liveness_failed":
            message = "Liveness check failed. Please use a live camera image and try again."
        else:
            self.status = "liveness_error"
            message = "Liveness check is temporarily unavailable. Please try again."
        super().__init__(message)


def _raise_for_recognition_error(response):
    try:
        body = response.json()
    except (ValueError, requests.RequestException):
        body = {}
    if not isinstance(body, dict):
        body = {}

    service_status = body.get("status")
    if service_status in {"liveness_failed", "liveness_error"}:
        raise FaceLivenessError(service_status)

    error_msg = body.get("error", "Unknown FR service error")
    raise FaceExtractionError(str(error_msg))


def _to_base64_string(image_data: Union[str, bytes]) -> str:
    """Helper to ensure image data is a base64 encoded string for JSON transmission."""
    if isinstance(image_data, str):
        # Could be 'data:image/jpeg;base64,....'
        if image_data.startswith('data:image'):
            return image_data.split(',', 1)[1]
        return image_data
    elif isinstance(image_data, bytes):
        return base64.b64encode(image_data).decode('utf-8')
    else:
        raise FaceExtractionError("Unsupported image data type.")


def _recognize_payload(image_data, candidates, threshold, captured_at_ms=None):
    """Use the sequence gate for attendance captures; retain legacy single-image callers."""
    if isinstance(image_data, (list, tuple)):
        if not 3 <= len(image_data) <= 7:
            raise FaceExtractionError("A facial attendance check requires 3 to 7 camera frames.")
        if not isinstance(captured_at_ms, (list, tuple)) or len(captured_at_ms) != len(image_data):
            raise FaceExtractionError("Camera frame timestamps are missing or invalid.")
        payload = {
            "frames": [_to_base64_string(frame) for frame in image_data],
            "captured_at_ms": list(captured_at_ms),
            "candidates": candidates,
            "threshold": threshold,
        }
        endpoint = "/recognize-sequence"
        timeout = 90
    else:
        payload = {
            "image": _to_base64_string(image_data),
            "candidates": candidates,
            "threshold": threshold,
        }
        endpoint = "/recognize"
        timeout = 60
    return requests.post(f"{settings.FACE_SERVICE_URL}{endpoint}", json=payload, timeout=timeout)


def process_enrollment(images: List[Union[str, bytes]]) -> List[float]:
    """
    Extracts embeddings from 3 images using the local FR microservice.
    The service returns the 512-d averaged normalized template.
    """
    if len(images) != 3:
        raise ValueError("Enrollment requires exactly 3 images.")
        
    b64_images = [_to_base64_string(img) for img in images]
    
    try:
        response = requests.post(f"{settings.FACE_SERVICE_URL}/enroll", json={"images": b64_images}, timeout=90)
    except requests.RequestException as e:
        logger.error(f"FR Service connection error: {e}")
        raise FaceExtractionError("Facial Recognition service is currently unavailable.")
        
    if response.status_code != 200:
        error_msg = response.json().get("error", "Unknown FR service error")
        raise FaceExtractionError(error_msg)
        
    return response.json().get("template")


def find_closest_match(query_image_data, threshold: float = 0.60, captured_at_ms=None) -> Tuple[Optional[Employee], float]:
    """
    Finds the closest enrolled employee matching the query image using the local FR microservice.
    Returns (Employee, distance) or (None, best_distance) if no match under threshold.
    """
    profiles = FaceProfile.objects.select_related('employee').filter(
        employee__is_active=True, 
        status="ACTIVE"
    )
    
    if not profiles.exists():
        return None, float('inf')
        
    # Build candidate list
    candidates = []
    # Create a fast lookup dict by ID
    profile_dict = {}
    
    for profile in profiles:
        emp_emb = profile.face_template
        if not emp_emb:
            continue
        candidates.append({"id": profile.employee.id, "template": emp_emb})
        profile_dict[profile.employee.id] = profile.employee
        
    if not candidates:
        return None, float('inf')
    
    try:
        response = _recognize_payload(query_image_data, candidates, threshold, captured_at_ms)
    except requests.RequestException as e:
        logger.error(f"FR Service connection error: {e}")
        raise FaceExtractionError("Facial Recognition service is currently unavailable.")
        
    if response.status_code != 200:
        _raise_for_recognition_error(response)
        
    result = response.json()
    status = result.get("status")
    distance = result.get("distance", float('inf'))
    
    if status == "match":
        emp_id = result.get("employee_id")
        matched_employee = profile_dict.get(emp_id)
        return matched_employee, distance
    else:
        # status == "unknown"
        return None, distance


def verify_employee_face(employee: Employee, query_image_data, threshold: float = 0.60, captured_at_ms=None) -> Tuple[bool, float]:
    """
    Verifies if the face in the query image matches the specified employee (1:1 verification).
    Returns (True, distance) if it matches, or (False, distance) if it doesn't.
    """
    try:
        profile = FaceProfile.objects.get(employee=employee, status="ACTIVE")
    except FaceProfile.DoesNotExist:
        return False, float('inf')

    if not profile.face_template:
        return False, float('inf')

    candidates = [{"id": employee.id, "template": profile.face_template}]

    try:
        response = _recognize_payload(query_image_data, candidates, threshold, captured_at_ms)
    except requests.RequestException as e:
        logger.error(f"FR Service connection error: {e}")
        raise FaceExtractionError("Facial Recognition service is currently unavailable.")
        
    if response.status_code != 200:
        _raise_for_recognition_error(response)
        
    result = response.json()
    status = result.get("status")
    distance = result.get("distance", float('inf'))
    
    if status == "match":
        return True, distance
    else:
        return False, distance
