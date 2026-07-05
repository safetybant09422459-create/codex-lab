from typing import Any

from .domain_provider import DomainProvider, OperationContext, ProviderOperationSpec
from .executors import BaseExecutor
from .travel_repository import TravelRepository


class TravelProvider(DomainProvider):
    provider_id = "travel"

    def __init__(self, repository: TravelRepository | None = None) -> None:
        self.repository = repository or TravelRepository()

    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        read_ids = (
            "get_trips",
            "get_trip",
            "get_trip_timeline",
            "get_spot",
            "get_experience",
            "get_trip_photos",
            "get_spot_photos",
            "get_experience_photos",
            "get_experience_photo_search",
            "get_experience_photo_links",
        )
        write_ids = (
            "create_trip",
            "create_timeline_item",
            "create_experience",
            "update_experience",
            "archive_experience",
            "link_experience_photo",
            "archive_experience_photo_link",
            "set_trip_cover_image",
            "set_spot_cover_image",
        )
        specs = [
            ProviderOperationSpec(
                operation_id=operation_id,
                what_it_can_do=(
                    "Read canonical Travel data for the selected operation."
                ),
                what_it_cannot_do=(
                    "It cannot infer user intent, choose an entity, or modify "
                    "Travel data."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "Canonical IDs are required where declared by input_schema.",
                ),
            )
            for operation_id in read_ids
        ]
        specs.extend(
            ProviderOperationSpec(
                operation_id=operation_id,
                what_it_can_do=(
                    "Apply the selected deterministic change to the local Travel "
                    "repository."
                ),
                what_it_cannot_do=(
                    "It cannot execute without Runtime permission, confirmation, "
                    "and audit gates."
                ),
                examples=({"arguments": {}},),
                limitations=("Admin role and explicit confirmation are required.",),
            )
            for operation_id in write_ids
        )
        planned_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        for operation_id, subject in (
            ("search_trip", "trips"),
            ("search_experience", "experiences"),
        ):
            specs.append(
                ProviderOperationSpec(
                    operation_id=operation_id,
                    description=f"Search {subject} using structured search criteria.",
                    what_it_can_do=(
                        f"Planned: return candidate {subject} for later canonical "
                        "re-fetch."
                    ),
                    what_it_cannot_do=(
                        "It cannot currently execute or establish candidates as "
                        "verified evidence."
                    ),
                    input_schema=planned_schema,
                    output_schema={
                        "type": "object",
                        "properties": {"candidates": {"type": "array"}},
                    },
                    mode="read",
                    risk_level="low",
                    confirmation_required=False,
                    examples=({"arguments": {"query": "岡山"}},),
                    limitations=(
                        "Not implemented; visibility and pagination contracts are "
                        "undecided.",
                    ),
                    availability="planned",
                )
            )
        return tuple(specs)

    def execute(
        self, operation: OperationContext, params: dict[str, Any]
    ) -> dict[str, Any]:
        operation_id = operation.operation_id
        if operation_id == "get_trips":
            return {
                "tool_id": operation_id,
                "trips": self.repository.get_trips(),
                "source": "local_travel_read",
            }

        if operation_id == "get_trip":
            trip_id = self._trip_id(params)
            return {
                "tool_id": operation_id,
                "trip": self.repository.get_trip(trip_id),
                "source": "local_travel_read",
            }

        if operation_id == "get_trip_timeline":
            trip_id = self._trip_id(params)
            return {
                "tool_id": operation_id,
                "trip_id": trip_id,
                "items": self.repository.get_trip_timeline(trip_id),
                "source": "local_travel_read",
            }

        if operation_id == "get_spot":
            timeline_item_id = self._timeline_item_id(params)
            experience = self.repository.get_spot(timeline_item_id)
            return {
                "tool_id": operation_id,
                "experience_id": timeline_item_id,
                "experience_type": self._experience_type(experience),
                "timeline_item_id": timeline_item_id,
                "experience": experience,
                "spot": experience,
                "source": "local_travel_read",
            }

        if operation_id == "get_experience":
            experience_id = self._experience_id(params)
            return {
                "tool_id": operation_id,
                "experience_id": experience_id,
                "experience": (experience := self.repository.get_experience(experience_id)),
                "experience_type": self._experience_type(experience),
                "source": "local_travel_read",
            }

        if operation_id == "get_trip_photos":
            trip_id = self._trip_id(params)
            return {
                "tool_id": operation_id,
                **self.repository.get_trip_photos(
                    trip_id,
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if operation_id == "get_spot_photos":
            timeline_item_id = self._timeline_item_id(params)
            return {
                "tool_id": operation_id,
                **self.repository.get_spot_photos(
                    timeline_item_id,
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if operation_id == "get_experience_photos":
            experience_id = self._experience_id(params)
            return {
                "tool_id": operation_id,
                **self.repository.get_experience_photos(
                    experience_id,
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if operation_id == "get_experience_photo_search":
            experience_id = self._experience_id(params)
            return {
                "tool_id": operation_id,
                **self.repository.search_experience_photos(
                    experience_id,
                    from_at=params.get("from"),
                    to_at=params.get("to"),
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if operation_id == "get_experience_photo_links":
            experience_id = self._experience_id(params)
            return {
                "tool_id": operation_id,
                **self.repository.get_experience_photo_links(
                    experience_id,
                    status=params.get("status", "active"),
                ),
            }

        if operation_id == "create_trip":
            return {
                "tool_id": operation_id,
                "trip": self.repository.create_trip(
                    title=params.get("title"),
                    start_date=params.get("start_date"),
                    end_date=params.get("end_date"),
                    outing_type=params.get("outing_type"),
                    prefectures=params.get("prefectures"),
                    memo=params.get("memo"),
                    privacy_level=params.get("privacy_level"),
                    created_by=params.get("created_by"),
                ),
                "source": "local_travel_write",
            }

        if operation_id == "create_timeline_item":
            item = self.repository.create_timeline_item(
                trip_id=params.get("trip_id"),
                item_type=params.get("item_type"),
                display_title=params.get("display_title"),
                place_name=params.get("place_name"),
                place_id=params.get("place_id"),
                category=params.get("category"),
                start_at=params.get("start_at"),
                end_at=params.get("end_at"),
                time_kind=params.get("time_kind"),
                memo=params.get("memo"),
                order_no=params.get("order_no"),
                status=params.get("status"),
            )
            return {
                "tool_id": operation_id,
                "experience": item,
                "item": item,
                "experience_id": item.get("experience_id"),
                "experience_type": item.get("experience_type"),
                "timeline_item_id": item.get("timeline_item_id"),
                "source": "local_travel_write",
            }

        if operation_id == "create_experience":
            experience = self.repository.create_experience(
                trip_id=params.get("trip_id"),
                experience_type=params.get("experience_type"),
                display_title=params.get("display_title"),
                place_name=params.get("place_name"),
                place_id=params.get("place_id"),
                category=params.get("category"),
                start_at=params.get("start_at"),
                end_at=params.get("end_at"),
                time_kind=params.get("time_kind"),
                memo=params.get("memo"),
                order_no=params.get("order_no"),
                status=params.get("status"),
            )
            return {
                "tool_id": operation_id,
                "experience": experience,
                "experience_id": experience.get("experience_id"),
                "experience_type": experience.get("experience_type"),
                "timeline_item_id": experience.get("timeline_item_id"),
                "source": "local_travel_write",
            }

        if operation_id == "update_experience":
            experience = self.repository.update_experience(
                experience_id=self._experience_id(params),
                experience_type=params.get("experience_type"),
                display_title=params.get("display_title"),
                place_name=params.get("place_name"),
                place_id=params.get("place_id"),
                category=params.get("category"),
                start_at=params.get("start_at"),
                end_at=params.get("end_at"),
                time_kind=params.get("time_kind"),
                memo=params.get("memo"),
                order_no=params.get("order_no"),
                status=params.get("status"),
                cover_image_id=params.get("cover_image_id"),
            )
            return {
                "tool_id": operation_id,
                "experience": experience,
                "experience_id": experience.get("experience_id"),
                "experience_type": experience.get("experience_type"),
                "timeline_item_id": experience.get("timeline_item_id"),
                "source": "local_travel_write",
            }

        if operation_id == "archive_experience":
            experience = self.repository.archive_experience(
                experience_id=self._experience_id(params)
            )
            return {
                "tool_id": operation_id,
                "experience": experience,
                "experience_id": experience.get("experience_id"),
                "experience_type": experience.get("experience_type"),
                "timeline_item_id": experience.get("timeline_item_id"),
                "source": "local_travel_write",
            }

        if operation_id == "link_experience_photo":
            result = self.repository.link_experience_photo(
                experience_id=self._experience_id(params),
                photo_asset_id=params.get("photo_asset_id"),
                link_type=params.get("link_type", "linked"),
                created_by=params.get("created_by"),
            )
            return {
                "tool_id": operation_id,
                **result,
            }

        if operation_id == "archive_experience_photo_link":
            result = self.repository.archive_experience_photo_link(
                experience_id=self._experience_id(params),
                link_id=params.get("link_id"),
            )
            return {
                "tool_id": operation_id,
                **result,
            }

        if operation_id == "set_trip_cover_image":
            return {
                "tool_id": operation_id,
                **self.repository.set_trip_cover_image(
                    trip_id=params.get("trip_id"),
                    asset_id=params.get("asset_id"),
                    selected_by="admin",
                ),
            }

        if operation_id == "set_spot_cover_image":
            return {
                "tool_id": operation_id,
                **self.repository.set_spot_cover_image(
                    timeline_item_id=params.get("timeline_item_id"),
                    asset_id=params.get("asset_id"),
                    selected_by="admin",
                ),
            }

        raise ValueError(f"Unsupported travel operation: {operation_id}")

    @property
    def execution_mode(self) -> str:
        return "local_travel_read"

    def get_execution_mode(self, operation: OperationContext) -> str:
        if operation.operation_id in {
            "create_trip",
            "create_experience",
            "update_experience",
            "archive_experience",
            "create_timeline_item",
            "set_trip_cover_image",
            "set_spot_cover_image",
            "link_experience_photo",
            "archive_experience_photo_link",
        }:
            return "local_travel_write"
        return "local_travel_read"

    def _trip_id(self, params: dict[str, Any]) -> str:
        trip_id = params.get("trip_id")
        if isinstance(trip_id, str) and trip_id.strip():
            return trip_id.strip()
        raise ValueError("trip_id is required")

    def _timeline_item_id(self, params: dict[str, Any]) -> str:
        timeline_item_id = params.get("timeline_item_id")
        if isinstance(timeline_item_id, str) and timeline_item_id.strip():
            return timeline_item_id.strip()
        raise ValueError("timeline_item_id is required")

    def _experience_id(self, params: dict[str, Any]) -> str:
        experience_id = params.get("experience_id")
        if isinstance(experience_id, str) and experience_id.strip():
            return experience_id.strip()
        timeline_item_id = params.get("timeline_item_id")
        if isinstance(timeline_item_id, str) and timeline_item_id.strip():
            return timeline_item_id.strip()
        raise ValueError("experience_id is required")

    def _experience_type(self, experience: dict[str, Any] | None) -> str | None:
        if experience is None:
            return None
        experience_type = experience.get("experience_type")
        if isinstance(experience_type, str) and experience_type.strip():
            return experience_type.strip()
        return None


class TravelExecutor(BaseExecutor):
    """Runtime adapter; Travel operation dispatch belongs to TravelProvider."""

    def __init__(
        self,
        provider: TravelProvider | None = None,
        repository: TravelRepository | None = None,
    ) -> None:
        if provider is not None and repository is not None:
            raise ValueError("provider and repository are mutually exclusive")
        self.provider = provider or TravelProvider(repository=repository)

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        return self.provider.execute(self._operation(tool), params)

    def get_execution_mode(self, tool: Any) -> str:
        return self.provider.get_execution_mode(self._operation(tool))

    @staticmethod
    def _operation(tool: Any) -> OperationContext:
        return OperationContext(
            operation_id=tool.id,
            skill_id=getattr(tool, "skill_id", "travel"),
            mode=getattr(tool, "mode", "read"),
            risk_level=getattr(tool, "risk_level", "low"),
        )
