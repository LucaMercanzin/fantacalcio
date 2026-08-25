from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlayerRecord:
    name: str
    team: str
    role_classic: str
    role_mantra: Optional[str]
    price_current: Optional[float]
    price_initial: Optional[float]
    status: Optional[str]
    fantamedia: Optional[float]
    avg_rating: Optional[float]
    appearances: Optional[int]
    photo_url: Optional[str]
    source: str
    detail_url: Optional[str] = None


class BaseScraper(ABC):
    @abstractmethod
    def fetch(self) -> list:
        ...
