from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .search_engine import SearchDocument, SearchKeyword, normalize_search_text
from .travel_chat_adapter import (
    RUNTIME_SOURCE,
    TRAVEL_SKILL_ID,
    TRIP_ENTITY_TYPE,
)


class TravelDocumentBuilder:
    """Convert Runtime Trip values into the common SearchDocument contract."""

    def build(
        self,
        trip: Any,
        *,
        verified_at: datetime | None = None,
    ) -> SearchDocument | None:
        if not isinstance(trip, dict):
            return None
        trip_id = trip.get("id")
        if not isinstance(trip_id, str) or not trip_id.strip():
            return None
        title = trip.get("title")
        label = title.strip() if isinstance(title, str) and title.strip() else trip_id.strip()

        date_facets = _derive_date_facets(
            trip.get("start_date"),
            trip.get("end_date"),
            trip.get("outing_type"),
        )
        location_facets = _derive_location_facets(trip.get("prefectures"))
        fields = {
            "title": _normalize_field(title),
            "prefectures": _normalize_field(trip.get("prefectures")),
            "location_terms": location_facets["location_terms"],
            "regions": location_facets["regions"],
            "memo": _normalize_field(trip.get("memo")),
            "date": _normalize_field((trip.get("start_date"), trip.get("end_date"))),
            "calendar": date_facets["calendar"],
            "season": date_facets["season"],
            "duration": date_facets["duration"],
            "outing_type": _normalize_field(trip.get("outing_type")),
        }
        keywords = tuple(
            SearchKeyword(
                value=fields[name],
                matched_by=name,
                exact_matched_by=exact_matched_by,
                partial_matched_by=partial_matched_by,
                exact_score=exact_score,
                partial_score=partial_score,
            )
            for name, exact_score, partial_score, exact_matched_by, partial_matched_by in (
                ("title", 1.0, 0.86, "title_exact", "title_partial"),
                ("prefectures", 0.68, 0.68, None, None),
                ("location_terms", 0.68, 0.68, None, None),
                ("regions", 0.60, 0.60, None, None),
                ("memo", 0.58, 0.58, None, None),
                ("date", 0.42, 0.42, None, None),
                ("calendar", 0.42, 0.42, None, None),
                ("season", 0.42, 0.42, None, None),
                ("duration", 0.42, 0.42, None, None),
                ("outing_type", 0.40, 0.40, None, None),
            )
            if fields[name]
        )
        return SearchDocument(
            id=trip_id.strip(),
            label=label,
            document=" ".join(value for value in fields.values() if value),
            metadata={
                "skill_id": TRAVEL_SKILL_ID,
                "entity_type": TRIP_ENTITY_TYPE,
                "source": RUNTIME_SOURCE,
                "verified_at": verified_at,
                "trip": dict(trip),
            },
            keywords=keywords,
        )

    def build_many(
        self,
        trips: Any,
        *,
        verified_at: datetime | None = None,
    ) -> list[SearchDocument]:
        documents: list[SearchDocument] = []
        for trip in trips:
            document = self.build(trip, verified_at=verified_at)
            if document is not None:
                documents.append(document)
        return documents


def _normalize_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value if item is not None)
    return normalize_search_text(value)


_PREFECTURES_BY_REGION = (
    ("北海道", ("北海道",)),
    ("東北", ("青森", "岩手", "宮城", "秋田", "山形", "福島")),
    ("関東", ("茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川")),
    ("中部", ("新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知")),
    ("関西 近畿", ("滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山")),
    ("中国", ("鳥取", "島根", "岡山", "広島", "山口")),
    ("四国", ("徳島", "香川", "愛媛", "高知")),
    ("九州", ("福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄")),
)


def _derive_location_facets(value: Any) -> dict[str, str]:
    locations: list[str] = []
    for item in _text_values(value):
        normalized = normalize_search_text(item)
        if not normalized:
            continue
        locations.append(normalized)
        without_suffix = re.sub(r"[都道府県]$", "", normalized)
        if without_suffix and without_suffix not in locations:
            locations.append(without_suffix)

    location_terms: list[str] = []
    regions: list[str] = []
    for location in locations:
        location_terms.extend(
            (f"{location}の旅行", f"{location}の旅", f"{location}のおでかけ")
        )
        for region, prefectures in _PREFECTURES_BY_REGION:
            if location in prefectures and region not in regions:
                regions.append(region)

    return {
        "location_terms": _normalize_field(location_terms),
        "regions": _normalize_field(regions),
    }


def _derive_date_facets(
    start_value: Any,
    end_value: Any,
    outing_type: Any,
) -> dict[str, str]:
    start = _parse_date(start_value)
    end = _parse_date(end_value)
    if start is None:
        normalized_outing_type = normalize_search_text(outing_type)
        if normalized_outing_type == "daytrip":
            duration = "日帰り"
        elif normalized_outing_type == "overnight":
            duration = "宿泊"
        else:
            duration = ""
        return {"calendar": "", "season": "", "duration": duration}
    if end is None or end < start:
        end = start

    months = _covered_months(start, end)
    calendar_values = [
        f"{year}年" for year in dict.fromkeys(year for year, _ in months)
    ]
    calendar_values.extend(
        f"{month}月" for month in dict.fromkeys(month for _, month in months)
    )

    seasons = list(dict.fromkeys(_season_for_month(month) for _, month in months))
    day_count = (end - start).days + 1
    if day_count == 1:
        duration_values = ("日帰り", "1日", "1日間")
    else:
        duration_values = (f"{day_count - 1}泊{day_count}日", f"{day_count}日間", "宿泊")

    return {
        "calendar": _normalize_field(calendar_values),
        "season": _normalize_field(seasons),
        "duration": _normalize_field(duration_values),
    }


def _text_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if item is not None)
    if value is None:
        return ()
    return tuple(part for part in re.split(r"[,、;/]", str(value)) if part.strip())


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _covered_months(start: date, end: date) -> tuple[tuple[int, int], ...]:
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(months)


def _season_for_month(month: int) -> str:
    if month in (3, 4, 5):
        return "春"
    if month in (6, 7, 8):
        return "夏"
    if month in (9, 10, 11):
        return "秋"
    return "冬"
