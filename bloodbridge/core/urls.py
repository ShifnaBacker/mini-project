from django.urls import path
from .views import DonorRegistrationView, HospitalRegistrationView, UserLoginView


urlpatterns = [
    path("api/register/donor/", DonorRegistrationView.as_view(), name="donor-register"),
    path("api/register/hospital/", HospitalRegistrationView.as_view(), name="hospital-register"),
    path("api/login/", UserLoginView.as_view(), name="login"),
]

