import pandas as pd
from django.http import HttpResponse

EXPORT_FIELDS = [
    "id", "title", "description", "category__name", "address",
    "latitude", "longitude", "author__username",
    "avg_rating", "reviews_count", "views_7d", "popularity",
    "created_at", "updated_at",
]

COLUMN_NAMES = {
    "category__name": "category",
    "author__username": "author",
}

SUPPORTED_FORMATS = ("json", "csv")


def _safe_cell(value):
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def build_dataframe(queryset) -> pd.DataFrame:
    df = pd.DataFrame.from_records(queryset.values(*EXPORT_FIELDS))
    if df.empty:
        return pd.DataFrame(columns=[COLUMN_NAMES.get(f, f) for f in EXPORT_FIELDS])

    df = df.rename(columns=COLUMN_NAMES)
    df[["latitude", "longitude"]] = df[["latitude", "longitude"]].astype(float)
    for col in ("created_at", "updated_at"):
        df[col] = df[col].dt.tz_localize(None)
    return df


def export_response(queryset, file_format: str) -> HttpResponse:
    df = build_dataframe(queryset)

    if file_format == "csv":
        for col in ("title", "description", "address", "category", "author"):
            if col in df.columns:
                df[col] = df[col].map(_safe_cell)
        content = df.to_csv(index=False).encode("utf-8-sig")
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    else:
        content = df.to_json(orient="records", force_ascii=False, date_format="iso")
        response = HttpResponse(content, content_type="application/json; charset=utf-8")

    response["Content-Disposition"] = f'attachment; filename="locations.{file_format}"'
    return response