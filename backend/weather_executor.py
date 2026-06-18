from typing import Any

from .executors import BaseExecutor


class WeatherExecutor(BaseExecutor):
    execution_mode = "local_weather_stub"

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        location = self._location(params)

        if tool.id == "get_current_weather":
            return {
                "tool_id": tool.id,
                "location": location,
                "condition": "unknown",
                "temperature": None,
                "source": self.execution_mode,
            }

        if tool.id == "get_forecast":
            return {
                "tool_id": tool.id,
                "location": location,
                "forecast": self._forecast_items(params),
                "source": self.execution_mode,
            }

        if tool.id == "get_rain_probability":
            return {
                "tool_id": tool.id,
                "location": location,
                "rain_probability": None,
                "source": self.execution_mode,
            }

        raise ValueError(f"Unsupported weather tool: {tool.id}")

    def _location(self, params: dict[str, Any]) -> str:
        location = params.get("location")
        if isinstance(location, str) and location.strip():
            return location.strip()
        return "Okayama"

    def _forecast_items(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        days = params.get("days", 1)
        if not isinstance(days, int):
            days = 1
        days = min(max(days, 1), 7)

        return [
            {
                "date": "today" if index == 0 else f"day+{index}",
                "condition": "unknown",
                "rain_probability": None,
                "temperature": None,
            }
            for index in range(days)
        ]
