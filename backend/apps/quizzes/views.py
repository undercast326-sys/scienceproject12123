import random

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.topics.models import Topic
from apps.questions.models import Question
from apps.questions.serializers import QuestionPublicSerializer
from apps.users.models import UserProfile
from apps.users.services import credit_result, lock_profile

from .models import QuizSession, QuizAnswer

QUESTIONS_PER_QUIZ = 5


class StartQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        topic_id = request.data.get('topic_id')
        if not topic_id:
            return Response({'detail': 'Не указан topic_id'}, status=status.HTTP_400_BAD_REQUEST)
        topic = get_object_or_404(Topic.objects.select_related('subject'), id=topic_id)

        # Sample ids first so we only load the handful of rows we actually serve.
        question_ids = list(topic.questions.values_list('id', flat=True))
        if not question_ids:
            return Response({'detail': 'В этой теме пока нет заданий'}, status=status.HTTP_400_BAD_REQUEST)

        selected_ids = random.sample(question_ids, min(QUESTIONS_PER_QUIZ, len(question_ids)))
        by_id = Question.objects.in_bulk(selected_ids)
        selected = [by_id[qid] for qid in selected_ids]

        with transaction.atomic():
            session = QuizSession.objects.create(user=request.user, topic=topic)
            session.questions.set(selected)

        return Response({
            'session_id': session.id,
            'topic': {
                'id': topic.id,
                'name': topic.name,
                'subject': topic.subject.name,
            },
            'questions': QuestionPublicSerializer(selected, many=True).data,
        }, status=status.HTTP_201_CREATED)


class SubmitAnswerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(QuizSession, id=session_id, user=request.user)
        if session.finished_at is not None:
            return Response({'detail': 'Практика уже завершена'}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get('question_id')
        user_answer = request.data.get('answer')
        if question_id is None:
            return Response({'detail': 'Не указан question_id'}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(session.questions, id=question_id)
        correct = question.is_correct(user_answer)

        # One answer per question: feedback reveals whether it was right, so a
        # second try would let anyone flip every answer to correct.
        _, created = QuizAnswer.objects.get_or_create(
            session=session,
            question=question,
            defaults={'user_answer': user_answer, 'is_correct': correct},
        )
        if not created:
            return Response({'detail': 'На этот вопрос уже дан ответ'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'is_correct': correct, 'explanation': question.explanation})


def first_time_correct_count(session):
    """Questions answered correctly in this session and in no earlier finished session."""
    correct_ids = set(session.answers.filter(is_correct=True).values_list('question_id', flat=True))
    if not correct_ids:
        return 0
    solved_before = set(
        QuizAnswer.objects.filter(
            session__user_id=session.user_id, session__finished_at__isnull=False,
            is_correct=True, question_id__in=correct_ids,
        ).exclude(session=session).values_list('question_id', flat=True)
    )
    return len(correct_ids - solved_before)


class FinishQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        with transaction.atomic():
            # Lock the row so two concurrent finish calls can't both credit XP.
            session = get_object_or_404(
                QuizSession.objects.select_for_update(), id=session_id, user=request.user,
            )

            total = session.questions.count()
            correct_count = session.answers.filter(is_correct=True).count()

            if session.finished_at is None:
                profile = lock_profile(request.user)
                session.xp_earned = credit_result(
                    profile, total, correct_count, first_time_correct_count(session),
                )
                session.score = correct_count
                session.finished_at = timezone.now()
                session.save(update_fields=['score', 'xp_earned', 'finished_at'])
            else:
                # Already finished: report the stored result, don't credit again.
                correct_count = session.score
                profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # Every served question counts: skipped ones are wrong.
        return Response({
            'score': session.score,
            'total': total,
            'correct': correct_count,
            'wrong': total - correct_count,
            'xp_gained': session.xp_earned,
            'xp': profile.xp,
            'level': profile.level,
        })
