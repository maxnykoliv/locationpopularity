from django.contrib import admin, messages

from apps.reviews.models import Review

from .models import Location, LocationView, Subscription


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ("author", "rating", "comment", "created_at")
    readonly_fields = ("author", "rating", "comment", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "author", "rating", "reviews_total",
        "views_week", "popularity_score", "is_deleted", "created_at",
    )
    list_filter = ("is_deleted", "category", "created_at")
    search_fields = ("title", "description", "address", "author__username")
    autocomplete_fields = ("author",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    date_hierarchy = "created_at"
    inlines = [ReviewInline]
    actions = ["restore_locations"]

    def get_queryset(self, request):
        return Location.all_objects.with_stats().select_related("category", "author")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("author", request.user.pk)
        return initial

    @admin.display(description="Рейтинг", ordering="avg_rating")
    def rating(self, obj):
        return round(obj.avg_rating, 2)

    @admin.display(description="Відгуків", ordering="reviews_count")
    def reviews_total(self, obj):
        return obj.reviews_count

    @admin.display(description="Перегляди (7 дн.)", ordering="views_7d")
    def views_week(self, obj):
        return obj.views_7d

    @admin.display(description="Популярність", ordering="popularity")
    def popularity_score(self, obj):
        return round(obj.popularity, 1)

    @admin.action(description="Відновити вибрані локації")
    def restore_locations(self, request, queryset):
        updated = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_at=None)
        self.message_user(request, f"Відновлено: {updated}", messages.SUCCESS)


@admin.register(LocationView)
class LocationViewAdmin(admin.ModelAdmin):
    list_display = ("location", "user", "viewed_at")
    list_filter = ("viewed_at",)
    raw_id_fields = ("location", "user")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "created_at")
    raw_id_fields = ("location", "user")