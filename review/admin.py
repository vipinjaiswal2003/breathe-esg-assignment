"""Django admin for review models."""

from django.contrib import admin
from review.models import ReviewAction, ReviewComment


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ('emission', 'action', 'previous_status', 'performed_by', 'performed_at')
    list_filter = ('action',)
    readonly_fields = ('performed_at',)


@admin.register(ReviewComment)
class ReviewCommentAdmin(admin.ModelAdmin):
    list_display = ('emission', 'author', 'created_at')
    readonly_fields = ('created_at',)
