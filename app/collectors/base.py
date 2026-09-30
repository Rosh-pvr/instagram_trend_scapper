from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import TrendItem


class Collector(ABC):
    name = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def collect(self) -> list[TrendItem]:
        raise NotImplementedError
