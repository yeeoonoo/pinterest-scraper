from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Pin:
    pin_id: str
    source_url: str
    image_url: str
    keyword: str
    saves: int = 0
    hearts: int = 0
    scraped_at: date = field(default_factory=date.today)
    image_path: Optional[str] = None

    @property
    def score(self) -> int:
        """정렬 기준 점수: saves 우선, 없으면 hearts"""
        return self.saves if self.saves > 0 else self.hearts
