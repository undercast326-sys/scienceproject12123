from django.conf import settings
from django.db import models

from apps.questions.models import BaseQuestion
from apps.topics.models import Subject


class MockTest(models.Model):
    """An authored, timed exam variant for a subject (like a real ЕНТ paper)."""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='mock_tests')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=60)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['subject', 'order', 'id']

    def __str__(self):
        return f'{self.title} ({self.subject.name})'


class MockQuestion(BaseQuestion):
    mock_test = models.ForeignKey(MockTest, on_delete=models.CASCADE, related_name='questions')

    class Meta(BaseQuestion.Meta):
        indexes = [
            models.Index(fields=['mock_test', 'order']),
        ]


class MockAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mock_attempts')
    mock_test = models.ForeignKey(MockTest, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    xp_earned = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'mock_test', 'finished_at']),
        ]

    def __str__(self):
        return f'Attempt {self.id} ({self.user.username} / {self.mock_test.title})'


class MockAnswer(models.Model):
    attempt = models.ForeignKey(MockAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(MockQuestion, on_delete=models.CASCADE, related_name='answers')
    user_answer = models.JSONField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attempt', 'question')
