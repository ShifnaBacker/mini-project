from django.urls import path
from .views import (
    CompleteDonationView,
    CreateBloodRequestView,
    DonorApplicationView,
    DonorRegistrationView,
    HospitalLoginView,
    HospitalRegistrationView,
    PledgeDonationView,
    RequestOTPView,
    UserLoginView,
    VerifyOTPView,
)

urlpatterns = [
    # Auth
    path("auth/request-otp/", RequestOTPView.as_view(), name="request-otp"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("register/donor/", DonorRegistrationView.as_view(), name="donor-register"),
    path("register/hospital/", HospitalRegistrationView.as_view(), name="hospital-register"),
    path("hospital/login/", HospitalLoginView.as_view(), name="hospital-login"),
    path("login/", UserLoginView.as_view(), name="login"),

    # Donor flow
    path("donor/apply/", DonorApplicationView.as_view(), name="donor-apply"),

    # Blood request flows
    path("blood-request/create/", CreateBloodRequestView.as_view(), name="create-blood-request"),
    path("blood-request/pledge/", PledgeDonationView.as_view(), name="pledge-donation"),
    path("blood-request/complete/", CompleteDonationView.as_view(), name="complete-donation"),
]
