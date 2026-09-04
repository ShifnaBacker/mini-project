from django.urls import path
from .views import (
    DonorRegistrationView,
    HospitalRegistrationView,
    UserLoginView,
    CreateBloodRequestView,
    PledgeDonationView,
    CompleteDonationView,
)

urlpatterns = [
    # User registration & login
    path("register/donor/", DonorRegistrationView.as_view(), name="donor-register"),
    path("register/hospital/", HospitalRegistrationView.as_view(), name="hospital-register"),
    path("login/", UserLoginView.as_view(), name="login"),

    # Blood request flows
    path("blood-request/create/", CreateBloodRequestView.as_view(), name="create-blood-request"),
    path("blood-request/pledge/", PledgeDonationView.as_view(), name="pledge-donation"),
    path("blood-request/complete/", CompleteDonationView.as_view(), name="complete-donation"),
]
