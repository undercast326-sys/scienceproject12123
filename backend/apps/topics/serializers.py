from rest_framework import serializers

from .models import Subject, Grade, Topic, TheoryMaterial


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'icon', 'description']


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'number', 'label']


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    grade_label = serializers.CharField(source='grade.label', read_only=True)
    theory_count = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    theory_read_count = serializers.SerializerMethodField()
    questions_solved_count = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'subject_name', 'grade', 'grade_label', 'name', 'description', 'difficulty', 'order',
            'theory_count', 'question_count', 'theory_read_count', 'questions_solved_count', 'best_score',
        ]

    def get_theory_read_count(self, obj):
        return self.context.get('theory_read_map', {}).get(obj.id, 0)

    def get_questions_solved_count(self, obj):
        return self.context.get('questions_solved_map', {}).get(obj.id, 0)

    def get_best_score(self, obj):
        return self.context.get('best_score_map', {}).get(obj.id, 0)


class TheoryMaterialSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = TheoryMaterial
        fields = ['id', 'topic', 'title', 'content', 'order', 'is_read']

    def get_is_read(self, obj):
        read_ids = self.context.get('read_theory_ids')
        if read_ids is None:
            return False
        return obj.id in read_ids
