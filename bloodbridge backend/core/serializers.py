from datetime import date

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import serializers

from core.models import BloodRequest, DonorProfile, Hospital, PhoneOTP, User

User = get_user_model()


class RequestOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

    def validate_phone_number(self, value):
        return value.strip()


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)

    def validate(self, data):
        otp = (
            PhoneOTP.objects.filter(phone_number=data["phone_number"], otp_code=data["otp_code"])
            .order_by("-created_at")
            .first()
        )

        if not otp or not otp.is_valid():
            raise serializers.ValidationError("Invalid or expired OTP.")

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user = User.objects.filter(phone_number=data["phone_number"]).first()
        data["user"] = user
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=["general", "donor"], required=False)

    class Meta:
        model = User
        fields = ["username", "email", "phone_number", "password", "role"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, data):
        phone_number = data.get("phone_number")
        email = data.get("email")
        role = data.get("role", "general")

        if not phone_number:
            raise serializers.ValidationError("Phone number is required.")
        if User.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        if role == "donor" and not email:
            raise serializers.ValidationError("Donor registration requires an email address.")

        return data

    def create(self, validated_data):
        role = validated_data.pop("role", "general")
        user = User.objects.create_user(
            phone_number=validated_data.get("phone_number"),
            email=validated_data.get("email"),
            password=validated_data.get("password"),
            username=validated_data.get("username"),
            role=role,
            is_phone_verified=False,
        )
        return user


class DonorApplicationSerializer(serializers.Serializer):
    blood_group = serializers.ChoiceField(choices=DonorProfile.BLOOD_GROUP_CHOICES)
    date_of_birth = serializers.DateField()
    weight = serializers.FloatField()

    def validate(self, data):
        today = date.today()
        date_of_birth = data["date_of_birth"]
        age = today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )

        if age < 18 or age > 65:
            raise serializers.ValidationError("Donors must be between 18 and 65 years old.")
        if data["weight"] <= 45:
            raise serializers.ValidationError("Donor weight must be greater than 45 kg.")

        return data


class HospitalRegistrationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True)
    address = serializers.CharField(write_only=True)
    contact = serializers.CharField(write_only=True)
    licence_number = serializers.CharField(write_only=True)
    licence_photo = serializers.ImageField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone_number",
            "password",
            "name",
            "address",
            "contact",
            "licence_number",
            "licence_photo",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        hospital_data = {
            field: validated_data.pop(field)
            for field in ["name", "address", "contact", "licence_number", "licence_photo"]
        }
        user = User.objects.create_user(
            phone_number=validated_data.get("phone_number"),
            email=validated_data.get("email"),
            password=validated_data.get("password"),
            username=validated_data.get("username"),
            role="hospital",
            is_hospital=True,
            is_hospital_verified=False,
        )
        Hospital.objects.create(user=user, **hospital_data, verification_status="pending")
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        return {"user": user}


class HospitalLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        if user.role != User.ROLE_HOSPITAL:
            raise serializers.ValidationError("This account is not a hospital account.")

        try:
            hospital = user.hospital
        except Hospital.DoesNotExist:
            raise serializers.ValidationError("Hospital profile not found.")

        if hospital.verification_status != Hospital.STATUS_APPROVED:
            raise serializers.ValidationError("Hospital account is still pending approval.")

        return {"user": user}


class BloodRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodRequest
        fields = [
            "hospital",
            "blood_group",
            "quantity",
            "doctor_slip",
            "expires_at",
        ]

    def validate(self, data):
        hospital = data.get("hospital")
        quantity = data.get("quantity")
        blood_group = data.get("blood_group")

        if not hospital:
            raise serializers.ValidationError("Hospital is required.")

        if quantity is None or quantity <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0.")

        if blood_group not in dict(DonorProfile.BLOOD_GROUP_CHOICES):
            raise serializers.ValidationError("Invalid blood group.")

        if data.get("expires_at") and data["expires_at"] <= timezone.now():
            raise serializers.ValidationError("Expiration time must be in the future.")

        return data


class DonorPledgeSerializer(serializers.Serializer):
    donor_id = serializers.IntegerField()
    request_id = serializers.IntegerField()

    def validate(self, data):
        donor = User.objects.filter(id=data["donor_id"], is_donor=True).first()
        if not donor:
            raise serializers.ValidationError("Donor user not found.")

        request = BloodRequest.objects.filter(id=data["request_id"]).first()
        if not request:
            raise serializers.ValidationError("Blood request not found.")

        try:
            donor_profile = donor.donorprofile
        except DonorProfile.DoesNotExist:
            raise serializers.ValidationError("Donor profile is missing.")

        if not donor_profile.is_available:
            raise serializers.ValidationError("Donor is currently unavailable.")

        if donor_profile.on_cooldown():
            raise serializers.ValidationError("Donor is still in cooldown period.")

        if donor_profile.blood_group != request.blood_group:
            raise serializers.ValidationError("Blood group does not match request.")

        if request.is_fulfilled or not request.is_active:
            raise serializers.ValidationError("This request is no longer active.")

        return {"donor": donor, "request": request}


class DonationCompletionSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()

    def validate(self, data):
        blood_request = BloodRequest.objects.filter(id=data["request_id"]).first()
        if not blood_request:
            raise serializers.ValidationError("Blood request not found.")

        if not blood_request.is_active:
            raise serializers.ValidationError("This blood request is no longer active.")

        return {"blood_request": blood_request}