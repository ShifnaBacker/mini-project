from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Phone number is required")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)   # login field
    username = models.CharField(max_length=150, blank=True, null=True)

    is_donor = models.BooleanField(default=False)
    is_hospital = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # only for Django admin

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "phone_number"]

    objects = UserManager()

    def __str__(self):
        return self.username or self.email or self.phone_number




class DonorProfile(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    date_of_birth = models.DateField()
    weight = models.FloatField()
    last_donation_date = models.DateTimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    last_location_updated = models.DateTimeField(auto_now=True)

    def on_cooldown(self):
        """Return True if donor is within 90-day cooldown."""
        from datetime import timedelta
        import datetime
        if self.last_donation_date:
            return (datetime.datetime.now() - self.last_donation_date) < timedelta(days=90)
        return False

    def __str__(self):
        return f"{self.user.phone_number} ({self.blood_group})"

class Hospital(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    address = models.TextField()
    contact = models.CharField(max_length=15)
    licence_number = models.CharField(max_length=50, unique=True)
    licence_photo = models.ImageField(upload_to='licences/')
    is_verified = models.BooleanField(default=False)  # AI verification step

    def __str__(self):
        return self.name


class BloodRequest(models.Model):
    BLOOD_GROUP_CHOICES = DonorProfile.BLOOD_GROUP_CHOICES

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)  # always required
    requester = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # optional for general users

    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    quantity = models.IntegerField()
    pledged_units = models.IntegerField(default=0)   # donors pledged
    confirmed_units = models.IntegerField(default=0) # donations completed

    doctor_slip = models.ImageField(upload_to='doctor_slips/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=[('Pending', 'Pending'), ('Fulfilled', 'Fulfilled'), ('Expired', 'Expired')],
        default='Pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_fulfilled = models.BooleanField(default=False)

    def __str__(self):
        if self.requester:
            return f"User {self.requester.username} → {self.hospital.name} ({self.blood_group})"
        return f"Hospital {self.hospital.name} ({self.blood_group})"


