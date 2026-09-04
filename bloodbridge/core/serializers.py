from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from rest_framework import serializers

from core.models import BloodRequest, DonorProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "phone_number", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password")
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