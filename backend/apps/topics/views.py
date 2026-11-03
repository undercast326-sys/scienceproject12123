from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.quizzes.models import QuizAnswer, QuizSession

from .models import Subject, Topic, Paragraph, ParagraphProgress
from .serializers import SubjectSerializer, TopicSerializer, ParagraphSerializer


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.annotate(
        topic_count=Count('topics', distinct=True),
        mock_test_count=Count('mock_tests', distinct=True, filter=Q(mock_tests__is_published=True)),
    )
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


def user_topic_progress_maps(user, topic_ids):
    """Per-topic progress for one user, in three grouped queries regardless of topic count."""
    if not topic_ids:
        return {}, {}, {}

    paragraph_rows = (
        ParagraphProgress.objects.filter(user=user, paragraph__topic_id__in=topic_ids)
        .values('paragraph__topic_id')
        .annotate(count=Count('id'))
    )
    paragraphs_read_map = {row['paragraph__topic_id']: row['count'] for row in paragraph_rows}

    question_rows = (
        QuizAnswer.objects.filter(session__user=user, question__topic_id__in=topic_ids)
        .values('question__topic_id')
        .annotate(count=Count('question_id', distinct=True))
    )
    questions_solved_map = {row['question__topic_id']: row['count'] for row in question_rows}

    score_rows = (
        QuizSession.objects.filter(user=user, topic_id__in=topic_ids, finished_at__isnull=False)
        .values('topic_id')
        .annotate(best=Max('score'))
    )
    best_score_map = {row['topic_id']: row['best'] for row in score_rows}

    return paragraphs_read_map, questions_solved_map, best_score_map


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated]
    # The curriculum is small and the progress screen needs every topic at once.
    pagination_class = None

    def get_queryset(self):
        queryset = Topic.objects.select_related('subject').annotate(
            paragraph_count=Count('paragraphs', distinct=True),
            question_count=Count('questions', distinct=True),
        )
        subject_id = self.request.query_params.get('subject')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        return queryset

    def _context_for(self, topics):
        context = self.get_serializer_context()
        paragraphs_read_map, questions_solved_map, best_score_map = user_topic_progress_maps(
            self.request.user, [t.id for t in topics],
        )
        context['paragraphs_read_map'] = paragraphs_read_map
        context['questions_solved_map'] = questions_solved_map
        context['best_score_map'] = best_score_map
        return context

    def list(self, request, *args, **kwargs):
        # Evaluate the queryset once and derive the progress maps from those rows.
        topics = list(self.filter_queryset(self.get_queryset()))
        serializer = self.get_serializer(topics, many=True, context=self._context_for(topics))
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        topic = self.get_object()
        serializer = self.get_serializer(topic, context=self._context_for([topic]))
        return Response(serializer.data)


class ParagraphListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        paragraphs = topic.paragraphs.all()
        read_ids = set(
            ParagraphProgress.objects.filter(user=request.user, paragraph__topic_id=topic_id)
            .values_list('paragraph_id', flat=True)
        )
        serializer = ParagraphSerializer(paragraphs, many=True, context={'read_paragraph_ids': read_ids})
        return Response(serializer.data)


class MarkParagraphReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, topic_id, paragraph_id):
        paragraph = get_object_or_404(Paragraph, id=paragraph_id, topic_id=topic_id)
        ParagraphProgress.objects.get_or_create(user=request.user, paragraph=paragraph)
        return Response({'is_read': True})


class TopicProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        user = request.user

        paragraphs_total = topic.paragraphs.count()
        paragraphs_read = ParagraphProgress.objects.filter(user=user, paragraph__topic_id=topic_id).count()

        questions_total = topic.questions.count()
        answers = QuizAnswer.objects.filter(session__user=user, question__topic_id=topic_id)
        questions_solved = answers.values('question_id').distinct().count()
        questions_correct = answers.filter(is_correct=True).values('question_id').distinct().count()
        best_score = (
            QuizSession.objects.filter(user=user, topic_id=topic_id, finished_at__isnull=False)
            .aggregate(best=Max('score'))['best'] or 0
        )

        return Response({
            'paragraphs_total': paragraphs_total,
            'paragraphs_read': paragraphs_read,
            'questions_total': questions_total,
            'questions_solved': questions_solved,
            'questions_correct': questions_correct,
            'best_score': best_score,
        })
