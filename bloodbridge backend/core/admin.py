from django.contrib import admin
from .models import User, DonorProfile, Hospital, BloodRequest

admin.site.register(User)
admin.site.register(DonorProfile)
admin.site.register(Hospital)
admin.site.register(BloodRequest)
