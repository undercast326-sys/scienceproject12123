from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import UserProfile
from apps.users.services import credit_result, lock_profile

from .models import MockTest, MockAttempt, MockAnswer
from .serializers import (
    MockTestSerializer, MockQuestionPublicSerializer, MockQuestionReviewSerializer, MockAttemptSerializer,
)

# Answers that arrive slightly after the deadline (network lag, auto-submit) are still accepted.
GRACE_SECONDS = 15


def attempt_payload(attempt):
    return {
        'attempt_id': attempt.id,
        'mock_test': {
            'id': attempt.mock_test.id,
            'title': attempt.mock_test.title,
            'subject': attempt.mock_test.subject.name,
            'duration_minutes': attempt.mock_test.duration_minutes,
        },
        'started_at': attempt.started_at,
        'expires_at': attempt.expires_at,
        'server_time': timezone.now(),
    }


class MockTestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MockTestSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = (
            MockTest.objects.filter(is_published=True)
            .select_related('subject')
            .annotate(question_count=Count('questions', distinct=True))
        )
        subject_id = self.request.query_params.get('subject')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        return queryset

    def _context_for(self, tests):
        context = self.get_serializer_context()
        ids = [t.id for t in tests]
        rows = (
            MockAttempt.objects.filter(user=self.request.user, mock_test_id__in=ids, finished_at__isnull=False)
            .values('mock_test_id')
            .annotate(count=Count('id'), best=Max('score'))
        )
        context['attempts_map'] = {r['mock_test_id']: r['count'] for r in rows}
        context['best_map'] = {r['mock_test_id']: r['best'] for r in rows}
        return context

    def list(self, request, *args, **kwargs):
        tests = list(self.filter_queryset(self.get_queryset()))
        serializer = self.get_serializer(tests, many=True, context=self._context_for(tests))
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        test = self.get_object()
        serializer = self.get_serializer(test, context=self._context_for([test]))
        return Response(serializer.data)


class StartMockTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, test_id):
        test = get_object_or_404(MockTest.objects.select_related('subject'), id=test_id, is_published=True)
        questions = list(test.questions.all())
        if not questions:
            return Response({'detail': 'В этом пробном тесте пока нет вопросов'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Lock the user's row so a double click can't open two attempts side by side.
            get_user_model().objects.select_for_update().only('pk').get(pk=request.user.pk)

            # Resume an unfinished, unexpired attempt instead of starting over (e.g. after a reload).
            now = timezone.now()
            attempt = (
                MockAttempt.objects.filter(user=request.user, mock_test=test, finished_at__isnull=True, expires_at__gt=now)
                .select_related('mock_test', 'mock_test__subject')
                .first()
            )
            created = attempt is None
            answered = {}
            if created:
                attempt = MockAttempt.objects.create(
                    user=request.user, mock_test=test, total=len(questions),
                    expires_at=now + timedelta(minutes=test.duration_minutes),
                )
            else:
                answered = {a.question_id: a.user_answer for a in attempt.answers.all()}

        payload = attempt_payload(attempt)
        payload['questions'] = MockQuestionPublicSerializer(questions, many=True).data
        payload['answers'] = answered
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MockAnswerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(MockAttempt, id=attempt_id, user=request.user)
        if attempt.finished_at is not None:
            return Response({'detail': 'Попытка уже завершена'}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() > attempt.expires_at + timedelta(seconds=GRACE_SECONDS):
            return Response({'detail': 'Время вышло'}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get('question_id')
        user_answer = request.data.get('answer')
        if question_id is None:
            return Response({'detail': 'Не указан question_id'}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(attempt.mock_test.questions, id=question_id)
        # No feedback during a mock test - correctness is revealed only on finish.
        MockAnswer.objects.update_or_create(
            attempt=attempt, question=question,
            defaults={'user_answer': user_answer, 'is_correct': question.is_correct(user_answer)},
        )
        return Response({'saved': True})


def review_payload(attempt):
    answers = {a.question_id: a for a in attempt.answers.all()}
    review = []
    for q in attempt.mock_test.questions.all():
        a = answers.get(q.id)
        item = MockQuestionReviewSerializer(q).data
        item['user_answer'] = a.user_answer if a else None
        item['is_correct'] = a.is_correct if a else False
        review.append(item)
    return review


def first_time_correct_count(attempt):
    """Questions answered correctly in this attempt and in no earlier finished attempt."""
    correct_ids = set(attempt.answers.filter(is_correct=True).values_list('question_id', flat=True))
    if not correct_ids:
        return 0
    solved_before = set(
        MockAnswer.objects.filter(
            attempt__user_id=attempt.user_id, attempt__finished_at__isnull=False,
            is_correct=True, question_id__in=correct_ids,
        ).exclude(attempt=attempt).values_list('question_id', flat=True)
    )
    return len(correct_ids - solved_before)


class FinishMockTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        with transaction.atomic():
            attempt = get_object_or_404(
                MockAttempt.objects.select_for_update().select_related('mock_test', 'mock_test__subject'),
                id=attempt_id, user=request.user,
            )
            total = attempt.mock_test.questions.count()
            correct = attempt.answers.filter(is_correct=True).count()

            if attempt.finished_at is None:
                profile = lock_profile(request.user)
                attempt.xp_earned = credit_result(profile, total, correct, first_time_correct_count(attempt))
                attempt.score = correct
                attempt.total = total
                attempt.finished_at = timezone.now()
                attempt.save(update_fields=['score', 'total', 'xp_earned', 'finished_at'])
            else:
                profile, _ = UserProfile.objects.get_or_create(user=request.user)

        return Response({
            'attempt': MockAttemptSerializer(attempt).data,
            'score': attempt.score,
            'total': attempt.total,
            'correct': attempt.score,
            'wrong': attempt.total - attempt.score,
            'xp_gained': attempt.xp_earned,
            'xp': profile.xp,
            'level': profile.level,
            'review': review_payload(attempt),
        })


class MockAttemptReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            MockAttempt.objects.select_related('mock_test', 'mock_test__subject'),
            id=attempt_id, user=request.user, finished_at__isnull=False,
        )
        return Response({
            'attempt': MockAttemptSerializer(attempt).data,
            'score': attempt.score,
            'total': attempt.total,
            'review': review_payload(attempt),
        })


class MyMockAttemptsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        attempts = (
            MockAttempt.objects.filter(user=request.user, finished_at__isnull=False)
            .select_related('mock_test', 'mock_test__subject')
            .order_by('-finished_at')[:50]
        )
        return Response(MockAttemptSerializer(attempts, many=True).data)
