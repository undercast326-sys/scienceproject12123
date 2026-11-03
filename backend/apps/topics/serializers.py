from rest_framework import serializers

from .models import Subject, Topic, Paragraph


class SubjectSerializer(serializers.ModelSerializer):
    topic_count = serializers.IntegerField(read_only=True)
    mock_test_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'icon', 'description', 'order', 'topic_count', 'mock_test_count']


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    paragraph_count = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    paragraphs_read_count = serializers.SerializerMethodField()
    questions_solved_count = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'subject_name', 'name', 'description', 'difficulty', 'order',
            'paragraph_count', 'question_count', 'paragraphs_read_count', 'questions_solved_count', 'best_score',
        ]

    def get_paragraphs_read_count(self, obj):
        return self.context.get('paragraphs_read_map', {}).get(obj.id, 0)

    def get_questions_solved_count(self, obj):
        return self.context.get('questions_solved_map', {}).get(obj.id, 0)

    def get_best_score(self, obj):
        return self.context.get('best_score_map', {}).get(obj.id, 0)


class ParagraphSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Paragraph
        fields = ['id', 'topic', 'title', 'content', 'order', 'is_read']

    def get_is_read(self, obj):
        read_ids = self.context.get('read_paragraph_ids')
        if read_ids is None:
            return False
        return obj.id in read_ids
