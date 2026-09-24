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


def find_closest_match(query_image_data: Union[str, bytes], threshold: float = 0.60) -> Tuple[Optional[Employee], float]:
    """
    Finds the closest enrolled employee matching the query image using the local FR microservice.
    Returns (Employee, distance) or (None, best_distance) if no match under threshold.
    """
    b64_image = _to_base64_string(query_image_data)
    
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
        payload = {
            "image": b64_image,
            "candidates": candidates,
            "threshold": threshold
        }
        response = requests.post(f"{settings.FACE_SERVICE_URL}/recognize", json=payload, timeout=60)
    except requests.RequestException as e:
        logger.error(f"FR Service connection error: {e}")
        raise FaceExtractionError("Facial Recognition service is currently unavailable.")
        
    if response.status_code != 200:
        error_msg = response.json().get("error", "Unknown FR service error")
        raise FaceExtractionError(error_msg)
        
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
