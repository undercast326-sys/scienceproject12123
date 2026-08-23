from django.conf import settings
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=20, blank=True, default='')
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Grade(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        ordering = ['number']

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = f'{self.number} класс'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class Topic(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['grade__number', 'order', 'id']
        indexes = [
            models.Index(fields=['subject', 'grade', 'order']),
        ]

    def __str__(self):
        return f'{self.name} ({self.subject.name}, {self.grade.label})'


class TheoryMaterial(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='theory_materials')
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


class TheoryProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='theory_progress')
    theory = models.ForeignKey(TheoryMaterial, on_delete=models.CASCADE, related_name='progress')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'theory')

    def __str__(self):
        return f'{self.user.username} read {self.theory_id}'
