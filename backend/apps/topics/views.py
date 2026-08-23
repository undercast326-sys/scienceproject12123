from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subject, Grade, Topic, TheoryMaterial, TheoryProgress
from .serializers import SubjectSerializer, GradeSerializer, TopicSerializer, TheoryMaterialSerializer


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]


class GradeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Grade.objects.all()
        subject_id = self.request.query_params.get('subject')
        if subject_id:
            queryset = queryset.filter(topics__subject_id=subject_id).distinct()
        return queryset


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Topic.objects.select_related('subject', 'grade').annotate(
            theory_count=Count('theory_materials', distinct=True),
            question_count=Count('questions', distinct=True),
        )
        subject_id = self.request.query_params.get('subject')
        grade_id = self.request.query_params.get('grade')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'retrieve':
            pk = self.kwargs.get('pk')
            topic_ids = [int(pk)] if pk else None
        elif self.action == 'list':
            topic_ids = list(self.filter_queryset(self.get_queryset()).values_list('id', flat=True))
        else:
            topic_ids = None
        user = self.request.user
        theory_read_map = {}
        questions_solved_map = {}
        best_score_map = {}
        if topic_ids and user.is_authenticated:
            theory_rows = (
                TheoryProgress.objects.filter(user=user, theory__topic_id__in=topic_ids)
                .values('theory__topic_id')
                .annotate(count=Count('id'))
            )
            theory_read_map = {row['theory__topic_id']: row['count'] for row in theory_rows}

            from apps.quizzes.models import QuizAnswer, QuizSession
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
        context['theory_read_map'] = theory_read_map
        context['questions_solved_map'] = questions_solved_map
        context['best_score_map'] = best_score_map
        return context


class TheoryMaterialListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        materials = topic.theory_materials.all()
        read_ids = set(
            TheoryProgress.objects.filter(user=request.user, theory__topic_id=topic_id)
            .values_list('theory_id', flat=True)
        )
        serializer = TheoryMaterialSerializer(materials, many=True, context={'read_theory_ids': read_ids})
        return Response(serializer.data)


class MarkTheoryReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, topic_id, theory_id):
        theory = get_object_or_404(TheoryMaterial, id=theory_id, topic_id=topic_id)
        TheoryProgress.objects.get_or_create(user=request.user, theory=theory)
        return Response({'is_read': True})


class TopicProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        user = request.user

        theory_total = topic.theory_materials.count()
        theory_read = TheoryProgress.objects.filter(user=user, theory__topic_id=topic_id).count()

        from apps.quizzes.models import QuizAnswer, QuizSession
        questions_total = topic.questions.count()
        answers = QuizAnswer.objects.filter(session__user=user, question__topic_id=topic_id)
        questions_solved = answers.values('question_id').distinct().count()
        questions_correct = answers.filter(is_correct=True).values('question_id').distinct().count()
        best_score = (
            QuizSession.objects.filter(user=user, topic_id=topic_id, finished_at__isnull=False)
            .aggregate(best=Max('score'))['best'] or 0
        )

        return Response({
            'theory_total': theory_total,
            'theory_read': theory_read,
            'questions_total': questions_total,
            'questions_solved': questions_solved,
            'questions_correct': questions_correct,
            'best_score': best_score,
        })
