from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SubjectViewSet, GradeViewSet, TopicViewSet,
    TheoryMaterialListView, MarkTheoryReadView, TopicProgressView,
)

router = DefaultRouter()
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'grades', GradeViewSet, basename='grade')
router.register(r'topics', TopicViewSet, basename='topic')

urlpatterns = [
    path('topics/<int:topic_id>/theory/', TheoryMaterialListView.as_view(), name='topic-theory-list'),
    path('topics/<int:topic_id>/theory/<int:theory_id>/read/', MarkTheoryReadView.as_view(), name='topic-theory-read'),
    path('topics/<int:topic_id>/progress/', TopicProgressView.as_view(), name='topic-progress'),
    path('', include(router.urls)),
]
