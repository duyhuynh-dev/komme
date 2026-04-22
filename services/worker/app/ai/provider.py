from __future__ import annotations

from importlib import import_module
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

ResultT = TypeVar("ResultT", bound=BaseModel)


class StructuredModelProvider:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run(
        self,
        *,
        instructions: str,
        prompt: str,
        output_type: type[ResultT],
    ) -> ResultT:
        if not self.settings.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured.")

        try:
            module = import_module("pydantic_ai")
            agent_cls = getattr(module, "Agent")
            agent = agent_cls(
                self.settings.gemini_model,
                instructions=instructions,
                output_type=output_type,
            )
            result = await agent.run(prompt)
            return output_type.model_validate(result.output)
        except Exception as error:  # pragma: no cover - runtime integration boundary
            raise RuntimeError("Structured model execution failed.") from error


def safe_model_dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")

