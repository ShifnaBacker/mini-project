from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserRegistrationSerializer, UserLoginSerializer

class DonorRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    def perform_create(self, serializer):
        user = serializer.save()
        user.is_donor = True
        user.save()

class HospitalRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    def perform_create(self, serializer):
        user = serializer.save()
        user.is_hospital = True
        user.save()

class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        role = "donor" if user.is_donor else "hospital" if user.is_hospital else "user"

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": role
        })
