"""Abstract base class for edge factors."""
from abc import ABC, abstractmethod
from quantforge.core.models import FactorScore


class Factor(ABC):
    def __init__(self, name: str, weight: float):
        self.name = name
        self.weight = weight

    @abstractmethod
    def compute(self, symbol: str, data: dict) -> FactorScore:
        ...
