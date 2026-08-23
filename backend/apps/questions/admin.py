from django.contrib import admin

from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'type', 'prompt', 'order')
    list_filter = ('topic__subject', 'topic__grade', 'type')
    search_fields = ('prompt',)
