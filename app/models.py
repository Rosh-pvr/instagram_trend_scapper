from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TrendItem:
    title: str
    source: str
    url: str = ""
    keyword: str = ""
    engagement: float = 0.0
    observed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
