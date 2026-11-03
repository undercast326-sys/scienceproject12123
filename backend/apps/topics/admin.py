from django.contrib import admin

from apps.questions.forms import AnswerKeyForm
from apps.questions.models import Question

from .models import Subject, Topic, Paragraph, ParagraphProgress


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'icon', 'order')
    list_editable = ('order',)
    search_fields = ('name',)


class ParagraphInline(admin.StackedInline):
    model = Paragraph
    extra = 0
    fields = ('order', 'title', 'content')


class QuestionInline(admin.StackedInline):
    model = Question
    form = AnswerKeyForm
    extra = 0
    fields = ('order', 'type', 'prompt', 'options', 'correct_answer', 'explanation')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'subject', 'difficulty', 'order')
    list_select_related = ('subject',)
    list_filter = ('subject', 'difficulty')
    list_editable = ('order',)
    search_fields = ('name',)
    inlines = [ParagraphInline, QuestionInline]


@admin.register(Paragraph)
class ParagraphAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'topic', 'order')
    list_select_related = ('topic', 'topic__subject')
    list_filter = ('topic__subject',)
    search_fields = ('title',)


@admin.register(ParagraphProgress)
class ParagraphProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'paragraph', 'read_at')
    list_select_related = ('user', 'paragraph')
