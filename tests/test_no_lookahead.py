import numpy as np
import pandas as pd

from wealth_os.factors.trend import TrendFactor
from wealth_os.validation.checks import validate_no_lookahead


def test_trend_has_no_lookahead():
    idx = pd.bdate_range("2020-01-01", periods=500)
    prices = pd.DataFrame({"A": 100 * np.exp(np.linspace(0, 1, len(idx)))}, index=idx)
    factor = TrendFactor(periods=(20, 60, 120), weights=(.2, .3, .5), moving_average_window=100)
    issues = validate_no_lookahead(factor.compute, prices, idx[300])
    assert issues == []
