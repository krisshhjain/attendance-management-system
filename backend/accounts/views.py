"""
Authentication and user management views for the accounts application.

Provides endpoints for JWT token acquisition (login), password updates with
automatic employee force-reset clearance, and current user profile inspection.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ChangePasswordSerializer, UserProfileSerializer


class LoginView(TokenObtainPairView):
    """
    JWT authentication endpoint.

    Subclasses SimpleJWT's TokenObtainPairView. Authenticates credentials
    (email and password, as defined by User.USERNAME_FIELD) and returns
    access and refresh JSON Web Tokens.
    """
    pass


class ChangePasswordView(APIView):
    """
    Authenticated view for updating user credentials.

    Validates old credentials, sets the new password hash, and resets
    the employee's mandatory password change flag when present.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Process password change request for the currently authenticated user.

        Requires valid current_password and new_password. Updates the password,
        saves the user, and clears must_change_password on the associated
        Employee model if one exists.
        """
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        request.user.set_password(
            serializer.validated_data["new_password"]
        )
        request.user.save()

        # Clear the forced-change flag if set on an associated employee profile.
        # Wrapped in try/except to tolerate administrative accounts lacking an Employee record.
        try:
            emp = request.user.employee
            if emp.must_change_password:
                emp.must_change_password = False
                emp.save(update_fields=["must_change_password"])
        except Exception:
            pass

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    Profile endpoint for the active session.

    Returns the authenticated user's email, permissions (is_staff, is_superuser),
    and whether a mandatory password change is pending.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Return serialized profile details for the authenticated user.
        """
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
