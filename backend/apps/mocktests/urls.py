from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MockTestViewSet, StartMockTestView, MockAnswerView, FinishMockTestView,
    MockAttemptReviewView, MyMockAttemptsView,
)

router = DefaultRouter()
router.register(r'mock-tests', MockTestViewSet, basename='mock-test')

urlpatterns = [
    path('mock-tests/<int:test_id>/start/', StartMockTestView.as_view(), name='mock-test-start'),
    path('mock-attempts/mine/', MyMockAttemptsView.as_view(), name='mock-attempts-mine'),
    path('mock-attempts/<int:attempt_id>/answer/', MockAnswerView.as_view(), name='mock-attempt-answer'),
    path('mock-attempts/<int:attempt_id>/finish/', FinishMockTestView.as_view(), name='mock-attempt-finish'),
    path('mock-attempts/<int:attempt_id>/review/', MockAttemptReviewView.as_view(), name='mock-attempt-review'),
    path('', include(router.urls)),
]
