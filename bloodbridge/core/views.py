from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import DonorProfile
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    BloodRequestCreateSerializer,
    DonorPledgeSerializer,
    DonationCompletionSerializer,
)


class DonorRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        user.is_donor = True
        user.save()

        DonorProfile.objects.get_or_create(
            user=user,
            defaults={
                "blood_group": "O+",
                "date_of_birth": "2000-01-01",
                "weight": 50.0,
            }
        )


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


class CreateBloodRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BloodRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        blood_request = serializer.save(requester=request.user, is_verified=False, status="Pending")
        return Response(
            {
                "message": "Blood request created successfully.",
                "request_id": blood_request.id,
                "status": blood_request.status,
            },
            status=status.HTTP_201_CREATED,
        )


class PledgeDonationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = {
            "donor_id": request.user.id,
            "request_id": request.data.get("request_id"),
        }

        serializer = DonorPledgeSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        donor = serializer.validated_data["donor"]
        blood_request = serializer.validated_data["request"]

        blood_request.pledged_units += 1
        blood_request.save()

        donor_profile = donor.donorprofile
        donor_profile.is_available = False
        donor_profile.save()

        return Response(
            {
                "message": "Donation pledge accepted.",
                "request_id": blood_request.id,
                "pledged_units": blood_request.pledged_units,
                "hospital_contact": blood_request.hospital.contact,
            },
            status=status.HTTP_200_OK,
        )


class CompleteDonationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DonationCompletionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        blood_request = serializer.validated_data["blood_request"]
        donor = request.user

        try:
            donor_profile = donor.donorprofile
        except DonorProfile.DoesNotExist:
            return Response({"error": "Donor profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        blood_request.confirmed_units += 1
        if blood_request.confirmed_units >= blood_request.quantity:
            blood_request.is_fulfilled = True
            blood_request.status = "Fulfilled"
            blood_request.is_active = False

        blood_request.save()

        donor_profile.last_donation_date = request.user.date_joined  # placeholder if you want to replace later
        donor_profile.is_available = False
        donor_profile.save()

        return Response(
            {
                "message": "Donation completed successfully. Donor cooldown enforced.",
                "request_id": blood_request.id,
                "confirmed_units": blood_request.confirmed_units,
                "status": blood_request.status,
            },
            status=status.HTTP_200_OK,
        )