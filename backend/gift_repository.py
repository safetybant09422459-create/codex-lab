from datetime import date
from typing import Any

from .gift_storage import SQLiteGiftStorage


class GiftRepository:
    ENTRY_TYPES = {"candidate", "given", "received"}

    def __init__(self, storage: SQLiteGiftStorage | None = None) -> None:
        self.storage = storage or SQLiteGiftStorage()

    def list_entries(
        self, entry_type: str | None = None, person: str | None = None, year: int | None = None
    ) -> list[dict[str, Any]]:
        normalized_type = self._entry_type(entry_type, required=False)
        normalized_person = self._text(person, "person", required=False, maximum=120)
        if year is not None and (isinstance(year, bool) or year < 1900 or year > 2100):
            raise ValueError("year must be between 1900 and 2100")
        return self.storage.list_entries(normalized_type, normalized_person, year)

    def create_entry(self, **values: Any) -> dict[str, Any]:
        entry_type = self._entry_type(values.get("entry_type"), required=True)
        giver = self._text(values.get("giver"), "giver", required=False, maximum=120)
        recipient = self._text(values.get("recipient"), "recipient", required=False, maximum=120)
        gift_date = self._date(values.get("gift_date"), "gift_date", required=False)
        if entry_type in {"given", "received"} and not all((giver, recipient, gift_date)):
            raise ValueError("given and received entries require giver, recipient, and gift_date")
        amount = values.get("amount_yen")
        if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
            raise ValueError("amount_yen must be a non-negative integer")
        return self.storage.create_entry(
            {
                "entry_type": entry_type,
                "title": self._text(values.get("title"), "title", required=True, maximum=200),
                "giver": giver,
                "recipient": recipient,
                "gift_date": gift_date,
                "amount_yen": amount,
                "memo": self._text(values.get("memo"), "memo", required=False, maximum=2000),
                "related_event": self._text(values.get("related_event"), "related_event", required=False, maximum=200),
                "occasion_date": self._date(values.get("occasion_date"), "occasion_date", required=False),
            }
        )

    def _entry_type(self, value: Any, *, required: bool) -> str | None:
        normalized = self._text(value, "entry_type", required=required, maximum=20)
        if normalized is not None and normalized not in self.ENTRY_TYPES:
            raise ValueError("entry_type must be candidate, given, or received")
        return normalized

    @staticmethod
    def _text(value: Any, field: str, *, required: bool, maximum: int) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                raise ValueError(f"{field} is required")
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ValueError(f"{field} must be at most {maximum} characters")
        return normalized

    @staticmethod
    def _date(value: Any, field: str, *, required: bool) -> str | None:
        normalized = GiftRepository._text(value, field, required=required, maximum=10)
        if normalized is None:
            return None
        try:
            date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"{field} must be YYYY-MM-DD") from exc
        return normalized
