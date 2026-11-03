from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'xp', 'level', 'solved', 'correct', 'wrong')
    list_select_related = ('user',)
