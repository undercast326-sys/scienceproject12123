from django.contrib import admin

from .models import QuizSession, QuizAnswer


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'topic', 'started_at', 'finished_at', 'score')


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'question', 'is_correct')
