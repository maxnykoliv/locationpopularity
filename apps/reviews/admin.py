from django.contrib import admin

from .models import Review, ReviewVote


class ReviewVoteInline(admin.TabularInline):
    model = ReviewVote
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "location__title", "author__username")
    autocomplete_fields = ("author",)
    raw_id_fields = ("location",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ReviewVoteInline]


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ("review", "user", "value")
    list_filter = ("value",)
    raw_id_fields = ("review", "user")