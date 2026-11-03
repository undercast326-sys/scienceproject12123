from rest_framework import serializers

from .models import Question, answer_key_errors


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'topic', 'type', 'prompt', 'options', 'correct_answer', 'explanation', 'order']

    def validate(self, attrs):
        # Fall back to stored values so partial updates are checked as a whole.
        def current(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, default)

        errors = answer_key_errors(current('type', 'single'), current('options', []), current('correct_answer'))
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class QuestionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'topic', 'type', 'prompt', 'options']
