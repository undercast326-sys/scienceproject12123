from django.contrib import admin

from .models import Subject, Grade, Topic, TheoryMaterial, TheoryProgress


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'icon')
    search_fields = ('name',)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'label')
    ordering = ('number',)


class TheoryMaterialInline(admin.TabularInline):
    model = TheoryMaterial
    extra = 0


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'subject', 'grade', 'difficulty', 'order')
    list_filter = ('subject', 'grade', 'difficulty')
    search_fields = ('name',)
    inlines = [TheoryMaterialInline]


@admin.register(TheoryMaterial)
class TheoryMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'topic', 'order')
    list_filter = ('topic__subject', 'topic__grade')
    search_fields = ('title',)


@admin.register(TheoryProgress)
class TheoryProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'theory', 'read_at')
