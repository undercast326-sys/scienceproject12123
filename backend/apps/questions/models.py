from django.db import models

from apps.topics.models import Topic


class Question(models.Model):
    TYPE_CHOICES = [
        ('single', 'Single choice'),
        ('multiple', 'Multiple choice'),
        ('text', 'Text answer'),
    ]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='single')
    prompt = models.TextField()
    options = models.JSONField(blank=True, default=list)
    correct_answer = models.JSONField()
    explanation = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['topic', 'order']),
        ]

    def __str__(self):
        return self.prompt[:50]
