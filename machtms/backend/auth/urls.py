from django.urls import path
from machtms.backend.auth.views import (ObtainAPIKey, check_auth,
                            LoginView,
                            TMSLogoutView,)

urlpatterns = [
        path('auth', check_auth, name='auth.auth'),
        path('login', LoginView.as_view(), name='auth.login'),
        path('api_login', ObtainAPIKey.as_view(), name='auth.api_login'),
        path('logout', TMSLogoutView.as_view(), name='auth.logout')
]
