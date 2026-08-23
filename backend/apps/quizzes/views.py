import random

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.topics.models import Topic
from apps.questions.serializers import QuestionPublicSerializer
from apps.users.models import UserProfile

from .models import QuizSession, QuizAnswer

QUESTIONS_PER_QUIZ = 5
XP_PER_CORRECT_ANSWER = 10
XP_PER_LEVEL = 100


def is_answer_correct(question, user_answer):
    correct = question.correct_answer
    if question.type == 'multiple':
        try:
            return sorted(user_answer) == sorted(correct)
        except TypeError:
            return user_answer == correct
    if question.type == 'text':
        return str(user_answer).strip().lower() == str(correct).strip().lower()
    return user_answer == correct


class StartQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        topic_id = request.data.get('topic_id')
        if not topic_id:
            return Response({'detail': 'topic_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        topic = get_object_or_404(Topic.objects.select_related('subject', 'grade'), id=topic_id)

        all_questions = list(topic.questions.all())
        if not all_questions:
            return Response({'detail': 'No questions available for this topic'}, status=status.HTTP_400_BAD_REQUEST)

        count = min(QUESTIONS_PER_QUIZ, len(all_questions))
        selected = random.sample(all_questions, count)

        session = QuizSession.objects.create(user=request.user, topic=topic)
        session.questions.set(selected)

        return Response({
            'session_id': session.id,
            'topic': {
                'id': topic.id,
                'name': topic.name,
                'subject': topic.subject.name,
                'grade': topic.grade.label,
            },
            'questions': QuestionPublicSerializer(selected, many=True).data,
        }, status=status.HTTP_201_CREATED)


class SubmitAnswerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(QuizSession, id=session_id, user=request.user)
        if session.finished_at is not None:
            return Response({'detail': 'Quiz session already finished'}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get('question_id')
        user_answer = request.data.get('answer')
        if question_id is None:
            return Response({'detail': 'question_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(session.questions, id=question_id)
        correct = is_answer_correct(question, user_answer)

        QuizAnswer.objects.update_or_create(
            session=session,
            question=question,
            defaults={'user_answer': user_answer, 'is_correct': correct},
        )

        return Response({'is_correct': correct, 'explanation': question.explanation})


class FinishQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(QuizSession, id=session_id, user=request.user)

        answers = session.answers.all()
        total = answers.count()
        correct_count = answers.filter(is_correct=True).count()
        wrong_count = total - correct_count

        session.score = correct_count
        session.finished_at = timezone.now()
        session.save()

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.solved += total
        profile.correct += correct_count
        profile.wrong += wrong_count
        profile.xp += correct_count * XP_PER_CORRECT_ANSWER
        profile.level = profile.xp // XP_PER_LEVEL + 1
        profile.save()

        return Response({
            'score': session.score,
            'total': total,
            'correct': correct_count,
            'wrong': wrong_count,
            'xp': profile.xp,
            'level': profile.level,
        })
