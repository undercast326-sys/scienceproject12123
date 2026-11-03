from django.contrib import admin

from apps.questions.forms import AnswerKeyForm

from .models import MockTest, MockQuestion, MockAttempt, MockAnswer


class MockQuestionInline(admin.StackedInline):
    model = MockQuestion
    form = AnswerKeyForm
    extra = 0
    fields = ('order', 'type', 'prompt', 'options', 'correct_answer', 'explanation')


@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'subject', 'duration_minutes', 'order', 'is_published')
    list_select_related = ('subject',)
    list_filter = ('subject', 'is_published')
    list_editable = ('order', 'is_published')
    search_fields = ('title',)
    inlines = [MockQuestionInline]


@admin.register(MockQuestion)
class MockQuestionAdmin(admin.ModelAdmin):
    form = AnswerKeyForm
    list_display = ('id', 'mock_test', 'type', 'prompt', 'order')
    list_select_related = ('mock_test',)
    list_filter = ('mock_test__subject', 'type')
    search_fields = ('prompt',)


class MockAnswerInline(admin.TabularInline):
    model = MockAnswer
    extra = 0
    readonly_fields = ('question', 'user_answer', 'is_correct')
    can_delete = False


@admin.register(MockAttempt)
class MockAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'mock_test', 'started_at', 'finished_at', 'score', 'total')
    list_select_related = ('user', 'mock_test')
    list_filter = ('mock_test__subject',)
    inlines = [MockAnswerInline]
