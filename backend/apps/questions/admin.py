from django.contrib import admin

from .forms import AnswerKeyForm
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = AnswerKeyForm
    list_display = ('id', 'topic', 'type', 'prompt', 'order')
    list_select_related = ('topic', 'topic__subject')
    list_filter = ('topic__subject', 'type')
    search_fields = ('prompt',)
