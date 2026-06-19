from abc import ABC, abstractmethod
from typing import Any


class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class StubExecutor(BaseExecutor):
    execution_mode = "stub"

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "message": "stub execution",
            "tool_id": tool.id,
        }


class ExecutorRegistry:
    def __init__(self, default_executor: BaseExecutor | None = None) -> None:
        self.default_executor = default_executor or StubExecutor()
        self._tool_executors: dict[str, BaseExecutor] = {}
        self._skill_executors: dict[str, BaseExecutor] = {}
        self.register_skill("weather", self._build_weather_executor())
        self.register_skill("travel", self._build_travel_executor())

    def register_tool(self, tool_id: str, executor: BaseExecutor) -> None:
        self._tool_executors[tool_id] = executor

    def register_skill(self, skill_id: str, executor: BaseExecutor) -> None:
        self._skill_executors[skill_id] = executor

    def get_executor(
        self, tool_id: str, skill_id: str | None = None
    ) -> BaseExecutor:
        if tool_id in self._tool_executors:
            return self._tool_executors[tool_id]
        if skill_id is not None and skill_id in self._skill_executors:
            return self._skill_executors[skill_id]
        return self.default_executor

    def _build_weather_executor(self) -> BaseExecutor:
        from .weather_executor import WeatherExecutor

        return WeatherExecutor()

    def _build_travel_executor(self) -> BaseExecutor:
        from .travel_executor import TravelExecutor

        return TravelExecutor()
