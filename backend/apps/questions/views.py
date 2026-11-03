from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from .models import Question
from .serializers import QuestionSerializer


class QuestionViewSet(viewsets.ModelViewSet):
    """Content-management endpoint: exposes correct_answer, so staff only.

    Students get questions through /api/quizzes/start/ (public serializer).
    """
    serializer_class = QuestionSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Question.objects.select_related('topic')
        topic_id = self.request.query_params.get('topic')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        return queryset
