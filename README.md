# Location Popularity API

[![CI](https://github.com/maxnykoliv/locationpopularity/actions/workflows/ci.yml/badge.svg)](https://github.com/maxnykoliv/locationpopularity/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/Django-6.1-092E20)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)

A Django REST Framework API for a catalogue of places. Users add locations,
review and rate them, vote on each other's reviews and subscribe to updates.
Every location gets a **popularity score** built from its ratings, its number of
reviews and its unique views over the last 7 days.

## Highlights

- **Popularity ranking in a single query.** Average rating, review count and 7-day views are computed with annotations and a correlated subquery, with no N+1 queries and no denormalized counters to keep in sync. Results can be sorted and filtered by any of them.
- **Deduplicated view tracking.** A view counts once per viewer per hour. Viewers are identified by user, session or IP, using an atomic `cache.add`, so refreshing a page doesn't inflate the score.
- **Versioned list cache.** List responses are cached in Redis under a version key that is bumped in `transaction.on_commit`, so a rolled-back write never invalidates and a committed one can't leave the list stale. If Redis is down, responses are served uncached instead of failing.
- **Soft delete** with a default manager that hides deleted rows, `all_objects` for admin, and a restore action.
- **CSV/JSON export** with pandas, protected against CSV formula injection (`=`, `+`, `-`, `@`).
- **Session auth done properly:** CSRF enforcement, Django's password validators, case-insensitive unique emails, and password reset that doesn't reveal whether an email is registered.
- **Email notifications** to the location's author and subscribers when a new review is posted, sent after commit.
- **CI on real PostgreSQL and Redis:** 52 tests at 96% coverage, plus checks that migrations are in sync and the OpenAPI schema is valid, and a Docker build.

## Tech stack

| | |
|---|---|
| API | Django 6.1, Django REST Framework, django-filter, drf-spectacular |
| Data | PostgreSQL 16 (psycopg 3), Redis (django-redis) |
| Export | pandas |
| Serving | gunicorn + whitenoise |
| Tooling | Docker Compose, GitHub Actions, ruff, coverage.py |

## Quick start

```bash
cp .env.example .env      # set SECRET_KEY
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

| URL | |
|---|---|
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/admin/ | Admin: categories, locations with live stats, soft-delete restore |

Emails (password reset, review notifications) are printed to the `web` container
logs by the console email backend.

## API overview

Authentication is session-based. Call `GET /api/auth/csrf/` once and send the
`csrftoken` cookie back as an `X-CSRFToken` header on unsafe requests. Lists
are paginated (`?page=`, 20 per page).

| Method | Path | |
|---|---|---|
| POST | `/api/auth/register/` · `/login/` · `/logout/` | Account and session |
| GET | `/api/auth/me/` | Current user |
| POST | `/api/auth/password-reset/` · `/password-reset/confirm/` | Reset by email: `uid` + `token` |
| GET / POST* | `/api/categories/` | *Staff only for writes; a category in use can't be deleted (`409`) |
| GET / POST | `/api/locations/` | `?search=`, `?category=`, `?author=`, `?min_rating=`, `?max_rating=`, `?ordering=-popularity` (also `avg_rating`, `created_at`) |
| GET / PATCH / DELETE | `/api/locations/{id}/` | Reading registers a view; only the author or staff can modify; delete is soft |
| GET | `/api/locations/export/?file_format=csv\|json` | Export, with the same filters as the list |
| POST / DELETE | `/api/locations/{id}/subscribe/` | Get emailed about new reviews |
| GET / POST | `/api/locations/{id}/reviews/` | Reviews for a location: rating 1–5, one per user |
| GET / PATCH / DELETE | `/api/reviews/{id}/` | `?rating__gte=`, `?ordering=-likes` |
| POST / DELETE | `/api/reviews/{id}/vote/` | `{"value": 1}` or `{"value": -1}`; you can't vote on your own review |

Example location in a list:

```json
{
  "id": 1, "title": "High Castle", "category": 2, "category_name": "Parks",
  "address": "Lviv", "latitude": 49.848, "longitude": 24.039,
  "author": "alice", "avg_rating": 4.5, "reviews_count": 2, "views_7d": 17,
  "popularity": 57.5, "created_at": "...", "updated_at": "..."
}
```

## How popularity works

```
popularity = 10 × avg_rating + 2 × reviews_count + 0.5 × views_7d
```

The weights live in `apps/locations/querysets.py`. Rating dominates, so a place
can't win on views alone, while review count and recent views break ties and
reward places that are active right now.

Views older than the window are only needed for history.
`python manage.py cleanup_location_views` deletes them; run it daily from cron.

## Design decisions

- **Compute instead of denormalize.** Stats are annotated at query time, so they are always consistent. The trade-off is query cost on large tables; the indexes on `(location, viewed_at)` and `viewed_at` keep the subquery cheap. With much more traffic, the next step would be a periodically refreshed materialized view.
- **Version-key cache invalidation.** Instead of deleting every cached list variant (one per combination of query params), writes bump a version number that is part of each key. Old entries simply expire. The bump runs in `on_commit`, so it can't race with the transaction that triggered it.
- **Admin bulk actions bump the cache explicitly.** Bulk soft-delete and restore use `QuerySet.update()`, which doesn't fire model signals. The admin calls the invalidation itself; a test covers it.
- **Deduplicating views with `cache.add`** is atomic in Redis, so two concurrent requests from the same viewer can't both count. If the database insert fails, the key is removed so that the view can be counted on retry.
- **Session auth over JWT.** The API is meant to be consumed by a browser frontend on the same site. httpOnly session cookies with CSRF protection are safer there than tokens in `localStorage`.
- **`X-Forwarded-For` is ignored by default.** The header is client-controlled unless a trusted proxy sets it, so trusting it is opt-in via `TRUST_X_FORWARDED_FOR`.

## Known limitations

- The list cache is shared across users, so any per-user fields added to locations later would need the user in the cache key.
- Notifications are sent synchronously after commit. At scale they belong in a task queue such as Celery or RQ.
- A category with only soft-deleted locations still can't be deleted, because `PROTECT` sees the hidden rows.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                      # set SECRET_KEY, or keep DEBUG=true
docker compose up -d db redis

python manage.py migrate
python manage.py runserver
```

Checks (the same ones CI runs):

```bash
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
coverage run manage.py test && coverage report
```

## Project layout

```
config/           settings and URLs
apps/accounts/    registration, session login, password reset
apps/categories/  categories (staff-managed)
apps/locations/   locations, popularity querysets, view counter, list cache, export, subscriptions
apps/reviews/     reviews, votes, new-review notifications
apps/common/      timestamp/soft-delete base models, permissions, test helpers
```
