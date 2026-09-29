from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ChangePasswordSerializer, UserProfileSerializer
from system_logs.services import record_event


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=False)
            user = serializer.user
            if user:
                record_event(
                    event_type="LOGIN_SUCCESS",
                    category="AUTHENTICATION",
                    severity="INFO",
                    status="SUCCESS",
                    actor=user,
                    target=user,
                    message="User logged in successfully.",
                    source="API",
                    request=request,
                )
            return response
        except Exception as e:
            email = request.data.get("email", "unknown")
            record_event(
                event_type="LOGIN_FAILED",
                category="AUTHENTICATION",
                severity="WARNING",
                status="FAILED",
                message=f"Failed login attempt for {email}.",
                source="API",
                request=request,
            )
            raise e


class SystemAdminLoginView(TokenObtainPairView):
    """
    Manager login endpoint.
    Allows ONLY users with is_system_admin=True (Managers).
    SuperUsers must use the regular admin login.
    """
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Only allow is_system_admin users (Managers), NOT superusers
            if not serializer.user.is_system_admin:
                raise Exception("You do not have Manager privileges.")
            
            # Explicitly reject superusers from this endpoint
            if serializer.user.is_superuser:
                raise Exception("SuperUser accounts must use the admin login.")

            record_event(
                event_type="LOGIN_SUCCESS",
                category="AUTHENTICATION",
                severity="INFO",
                status="SUCCESS",
                actor=serializer.user,
                target=serializer.user,
                message="Manager logged in successfully.",
                source="API",
                request=request,
            )
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        except Exception as e:
            email = request.data.get("email", "unknown")
            record_event(
                event_type="LOGIN_FAILED",
                category="AUTHENTICATION",
                severity="WARNING",
                status="FAILED",
                message=f"Failed manager login attempt for {email}.",
                source="API",
                request=request,
            )
            # Re-raise the correct error depending on what happened
            from rest_framework.exceptions import ValidationError, AuthenticationFailed
            if str(e) in ["You do not have Manager privileges.", "SuperUser accounts must use the admin login."]:
                return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
            raise e


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        request.user.set_password(
            serializer.validated_data["new_password"]
        )
        request.user.save()

        # Clear the forced-change flag if set
        try:
            emp = request.user.employee
            if emp.must_change_password:
                emp.must_change_password = False
                emp.save(update_fields=["must_change_password"])
        except Exception:
            pass

        record_event(
            event_type="PASSWORD_CHANGED",
            category="AUTHENTICATION",
            severity="INFO",
            status="SUCCESS",
            actor=request.user,
            target=request.user,
            message="Account password changed.",
            source="API",
            request=request,
        )

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
