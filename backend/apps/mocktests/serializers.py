from rest_framework import serializers

from .models import MockTest, MockQuestion, MockAttempt


class MockTestSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    attempts_count = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = MockTest
        fields = [
            'id', 'subject', 'subject_name', 'title', 'description', 'duration_minutes', 'order',
            'question_count', 'attempts_count', 'best_score',
        ]

    def get_attempts_count(self, obj):
        return self.context.get('attempts_map', {}).get(obj.id, 0)

    def get_best_score(self, obj):
        return self.context.get('best_map', {}).get(obj.id, 0)


class MockQuestionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = MockQuestion
        fields = ['id', 'type', 'prompt', 'options', 'order']


class MockQuestionReviewSerializer(serializers.ModelSerializer):
    """Full question incl. the answer key — only sent after an attempt is finished."""
    class Meta:
        model = MockQuestion
        fields = ['id', 'type', 'prompt', 'options', 'correct_answer', 'explanation', 'order']


class MockAttemptSerializer(serializers.ModelSerializer):
    mock_test_title = serializers.CharField(source='mock_test.title', read_only=True)
    subject_name = serializers.CharField(source='mock_test.subject.name', read_only=True)

    class Meta:
        model = MockAttempt
        fields = ['id', 'mock_test', 'mock_test_title', 'subject_name', 'started_at', 'finished_at', 'score', 'total']
