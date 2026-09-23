from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ChangePasswordSerializer, UserProfileSerializer


class LoginView(TokenObtainPairView):
    pass


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

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)