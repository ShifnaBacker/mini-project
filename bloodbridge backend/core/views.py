from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import DonorProfile, PhoneOTP, User
from .serializers import (
    BloodRequestCreateSerializer,
    DonationCompletionSerializer,
    DonorApplicationSerializer,
    DonorPledgeSerializer,
    HospitalLoginSerializer,
    HospitalRegistrationSerializer,
    RequestOTPSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    VerifyOTPSerializer,
)

User = get_user_model()


class RequestOTPView(APIView):
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        otp = PhoneOTP.generate_for(phone_number)

        return Response(
            {
                "message": "OTP generated successfully.",
                "phone_number": phone_number,
                "otp": otp.otp_code,
                "expires_at": otp.expires_at,
            },
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data.get("user")
        if user is None:
            return Response(
                {
                    "message": "OTP verified successfully.",
                    "phone_number": request.data.get("phone_number"),
                    "user_exists": False,
                },
                status=status.HTTP_200_OK,
            )

        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "message": "OTP verified successfully.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "role": user.role,
                "user_exists": True,
            },
            status=status.HTTP_200_OK,
        )


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def perform_create(self, serializer):
        serializer.save()


class DonorApplicationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.is_donor:
            return Response(
                {"error": "User is already registered as a donor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DonorApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        DonorProfile.objects.create(user=request.user, **serializer.validated_data)
        request.user.role = User.ROLE_DONOR
        request.user.is_donor = True
        request.user.save(update_fields=["role", "is_donor"])

        return Response(
            {"message": "Donor profile created successfully."},
            status=status.HTTP_201_CREATED,
        )


DonorRegistrationView = UserRegistrationView


class HospitalRegistrationView(generics.CreateAPIView):
    serializer_class = HospitalRegistrationSerializer

    def perform_create(self, serializer):
        serializer.save()


class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        role = user.role

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "role": role,
            }
        )


class HospitalLoginView(APIView):
    def post(self, request):
        serializer = HospitalLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "role": user.role,
                "hospital": user.hospital.name,
            }
        )


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

        donor_profile.last_donation_date = timezone.now()
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