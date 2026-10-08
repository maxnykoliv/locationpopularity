from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value

from .models import ReviewVote


def annotate_votes(queryset, user):
    if user.is_authenticated:
        my_vote = Subquery(
            ReviewVote.objects.filter(review=OuterRef("pk"), user=user).values("value")[:1],
            output_field=IntegerField(),
        )
    else:
        my_vote = Value(None, output_field=IntegerField())

    return queryset.annotate(
        likes=Count("votes", filter=Q(votes__value=ReviewVote.LIKE)),
        dislikes=Count("votes", filter=Q(votes__value=ReviewVote.DISLIKE)),
        my_vote=my_vote,
    )