import random
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone_number=None, email=None, password=None, **extra_fields):
        if not phone_number and not email:
            raise ValueError("Phone number or email is required")

        if email:
            email = self.normalize_email(email)

        user = self.model(phone_number=phone_number, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "hospital")
        return self.create_user(phone_number=phone_number, email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_GENERAL = "general"
    ROLE_DONOR = "donor"
    ROLE_HOSPITAL = "hospital"

    ROLE_CHOICES = [
        (ROLE_GENERAL, "General User"),
        (ROLE_DONOR, "Donor"),
        (ROLE_HOSPITAL, "Hospital"),
    ]

    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, null=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_GENERAL)
    is_phone_verified = models.BooleanField(default=False)
    is_hospital_verified = models.BooleanField(default=False)
    is_donor = models.BooleanField(default=False)
    is_hospital = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.role == self.ROLE_DONOR:
            self.is_donor = True
        if self.role == self.ROLE_HOSPITAL:
            self.is_hospital = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username or self.email or self.phone_number or "User"


class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=15)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def generate_for(cls, phone_number):
        otp_code = str(random.randint(100000, 999999))
        otp = cls.objects.create(
            phone_number=phone_number,
            otp_code=otp_code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        return otp

    def __str__(self):
        return f"{self.phone_number} - {self.otp_code}"


class DonorProfile(models.Model):
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("O+", "O+"), ("O-", "O-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    date_of_birth = models.DateField()
    weight = models.FloatField()
    last_donation_date = models.DateTimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    last_location_updated = models.DateTimeField(auto_now=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def on_cooldown(self):
        """Return True if donor is within 90-day cooldown."""
        if self.last_donation_date:
            return (timezone.now() - self.last_donation_date) < timedelta(days=90)
        return False

    def __str__(self):
        return f"{self.user.phone_number} ({self.blood_group})"


class Hospital(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Approval"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    address = models.TextField()
    contact = models.CharField(max_length=15)
    licence_number = models.CharField(max_length=50, unique=True)
    licence_photo = models.ImageField(upload_to="licences/")
    verification_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.verification_status == self.STATUS_APPROVED:
            self.is_verified = True
        else:
            self.is_verified = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BloodRequest(models.Model):
    BLOOD_GROUP_CHOICES = DonorProfile.BLOOD_GROUP_CHOICES

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    requester = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    quantity = models.IntegerField()
    pledged_units = models.IntegerField(default=0)
    confirmed_units = models.IntegerField(default=0)

    doctor_slip = models.ImageField(upload_to="doctor_slips/", null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=[
            ("Pending", "Pending"),
            ("Verified", "Verified"),
            ("Pending_Human", "Pending Human Review"),
            ("Rejected", "Rejected"),
            ("Fulfilled", "Fulfilled"),
            ("Expired", "Expired"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_fulfilled = models.BooleanField(default=False)

    def __str__(self):
        if self.requester:
            return f"User {self.requester.username} → {self.hospital.name} ({self.blood_group})"
        return f"Hospital {self.hospital.name} ({self.blood_group})"


