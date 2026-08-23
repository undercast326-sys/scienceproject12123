from django.urls import path

from .views import RegisterView, MyProgressView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('progress/me/', MyProgressView.as_view(), name='progress-me'),
]
