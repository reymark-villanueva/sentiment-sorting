"""
Isabela State University - Cauayan Campus Library
Django Admin Registrations
"""

from django.contrib import admin

from .models import FeedbackLog, LibraryService


@admin.register(LibraryService)
class LibraryServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('name', 'description')


@admin.register(FeedbackLog)
class FeedbackLogAdmin(admin.ModelAdmin):
    list_display = ('service', 'sentiment', 'sentiment_priority', 'timestamp')
    list_filter = ('sentiment', 'service')
    search_fields = ('comment', 'service__name')
    date_hierarchy = 'timestamp'
    readonly_fields = ('sentiment', 'sentiment_priority', 'timestamp')
