from django.core.exceptions import ValidationError
from django.db import models

from apps.topics.models import Topic


def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def answer_key_errors(qtype, options, correct_answer):
    """Check that options/correct_answer fit the question type. Returns {field: message}."""
    errors = {}

    if not _is_str_list(options):
        return {'options': 'Варианты должны быть списком строк.'}
    if any(not opt.strip() for opt in options):
        errors['options'] = 'Варианты не могут быть пустыми.'
    elif len(set(options)) != len(options):
        errors['options'] = 'Варианты не должны повторяться.'

    if qtype == 'text':
        if options:
            errors['options'] = 'У вопроса с текстовым ответом не должно быть вариантов.'
        if not isinstance(correct_answer, str) or not correct_answer.strip():
            errors['correct_answer'] = 'Укажите правильный ответ текстом.'
        return errors

    if len(options) < 2:
        errors.setdefault('options', 'Нужно минимум два варианта.')

    if qtype == 'single':
        if not isinstance(correct_answer, str) or correct_answer not in options:
            errors['correct_answer'] = 'Правильный ответ должен совпадать с одним из вариантов.'
    elif qtype == 'multiple':
        if not _is_str_list(correct_answer) or not correct_answer:
            errors['correct_answer'] = 'Укажите хотя бы один правильный вариант.'
        elif len(set(correct_answer)) != len(correct_answer):
            errors['correct_answer'] = 'Правильные варианты не должны повторяться.'
        elif not set(correct_answer) <= set(options):
            errors['correct_answer'] = 'Каждый правильный ответ должен совпадать с одним из вариантов.'

    return errors


class BaseQuestion(models.Model):
    """Shared shape for topic tasks and mock-test questions."""
    TYPE_CHOICES = [
        ('single', 'Single choice'),
        ('multiple', 'Multiple choice'),
        ('text', 'Text answer'),
    ]

    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='single')
    prompt = models.TextField()
    options = models.JSONField(blank=True, default=list)
    correct_answer = models.JSONField()
    explanation = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ['order', 'id']

    def __str__(self):
        return self.prompt[:50]

    def clean(self):
        super().clean()
        errors = answer_key_errors(self.type, self.options, self.correct_answer)
        if errors:
            raise ValidationError(errors)

    def is_correct(self, user_answer):
        correct = self.correct_answer
        if self.type == 'multiple':
            # Only a list of strings counts: a bare string like "AB" must not be
            # sorted into characters and match ["A", "B"].
            if not _is_str_list(user_answer) or not isinstance(correct, list):
                return False
            return sorted(user_answer) == sorted(correct)
        if not isinstance(user_answer, str):
            return False
        if self.type == 'text':
            return user_answer.strip().lower() == str(correct).strip().lower()
        return user_answer == correct


class Question(BaseQuestion):
    """A task attached to a topic; practice sessions sample from these."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')

    class Meta(BaseQuestion.Meta):
        indexes = [
            models.Index(fields=['topic', 'order']),
        ]
