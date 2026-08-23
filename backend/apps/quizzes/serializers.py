from rest_framework import serializers

from .models import QuizSession, QuizAnswer


class QuizSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizSession
        fields = ['id', 'user', 'topic', 'started_at', 'finished_at', 'score']
        read_only_fields = fields


class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ['id', 'session', 'question', 'user_answer', 'is_correct']
        read_only_fields = fields
