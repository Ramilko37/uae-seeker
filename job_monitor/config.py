from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class SourceConfig(BaseModel):
    name: str
    type: str
    enabled: bool = True
    region: str | None = None
    country: str | None = None

    url: str | None = None
    queries: list[str] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)

    board_token: str | None = None
    site: str | None = None
    organization: str | None = None

    options: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    sources: list[SourceConfig]

    @property
    def enabled_sources(self) -> list[SourceConfig]:
        return [source for source in self.sources if source.enabled]


def load_config(path: str | Path) -> AppConfig:
    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    try:
        return AppConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid config {config_path}: {exc}") from exc
