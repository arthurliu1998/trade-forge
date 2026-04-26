import pytest
from quantforge.factors.base import Factor
from quantforge.core.models import FactorScore


def test_factor_is_abstract():
    with pytest.raises(TypeError):
        Factor("test", 0.35)


class DummyFactor(Factor):
    def compute(self, symbol, data):
        return FactorScore(name=self.name, raw=0.75, normalized=0.75, weight=self.weight)


def test_factor_subclass():
    f = DummyFactor("dummy", weight=0.35)
    score = f.compute("AAPL", {})
    assert score.name == "dummy"
    assert score.weight == 0.35
    assert score.clamped == 0.75
