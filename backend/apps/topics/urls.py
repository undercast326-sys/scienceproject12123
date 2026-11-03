from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SubjectViewSet, TopicViewSet,
    ParagraphListView, MarkParagraphReadView, TopicProgressView,
)

router = DefaultRouter()
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'topics', TopicViewSet, basename='topic')

urlpatterns = [
    path('topics/<int:topic_id>/paragraphs/', ParagraphListView.as_view(), name='topic-paragraph-list'),
    path('topics/<int:topic_id>/paragraphs/<int:paragraph_id>/read/', MarkParagraphReadView.as_view(), name='topic-paragraph-read'),
    path('topics/<int:topic_id>/progress/', TopicProgressView.as_view(), name='topic-progress'),
    path('', include(router.urls)),
]
