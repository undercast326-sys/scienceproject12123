from django.conf import settings
from django.db import models

from apps.topics.models import Topic
from apps.questions.models import Question


class QuizSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_sessions')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='quiz_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    questions = models.ManyToManyField(Question, related_name='quiz_sessions', blank=True)

    def __str__(self):
        return f'Session {self.id} ({self.user.username} / {self.topic.name})'


class QuizAnswer(models.Model):
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    user_answer = models.JSONField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('session', 'question')

    def __str__(self):
        return f'Answer {self.id} for session {self.session_id}'
