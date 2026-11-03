from django.conf import settings
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=20, blank=True, default='')
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Topic(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['subject', 'order']),
        ]

    def __str__(self):
        return f'{self.name} ({self.subject.name})'


class Paragraph(models.Model):
    """One theory section (§) inside a topic. Tasks live on the topic and cover all of them."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='paragraphs')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['topic', 'order']),
        ]

    def __str__(self):
        return self.title


class ParagraphProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paragraph_progress')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='progress')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'paragraph')

    def __str__(self):
        return f'{self.user.username} read {self.paragraph_id}'


class ContentImport(models.Model):
    """Which content file was last loaded for a subject, so deploys skip unchanged imports."""
    source = models.CharField(max_length=100, unique=True)
    sha256 = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.source} @ {self.sha256[:10]}'
