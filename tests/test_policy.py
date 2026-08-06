import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.domain.models import AssetClass, Instrument, PortfolioConstraints, Sleeve


def test_cash_is_first_class_and_weights_sum_to_one():
    instruments = {
        "EQ": Instrument("EQ", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "BTC": Instrument("BTC", AssetClass.DIGITAL_ASSET, Sleeve.ALTERNATIVE, "USD", "GLOBAL"),
        "CASH": Instrument("CASH", AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
    }
    base = pd.Series({"EQ": 0.6, "BTC": 0.02, "CASH": 0.38})
    constraints = PortfolioConstraints(
        max_weights={"BTC": 0.03}, min_weights={"CASH": 0.05}, max_turnover=1.0
    )
    policy = VTRAllocationPolicy(instruments, base, constraints, "CASH")
    signals = pd.DataFrame({"EQ": [1, 1], "BTC": [0, 2], "CASH": [0, 0]}, index=["value", "trend"])
    weights = policy.generate_target_weights(
        pd.Timestamp("2024-01-01"), base, signals, pd.Series({"EQ": 0.2, "BTC": 0.7, "CASH": 0})
    )
    assert abs(weights.sum() - 1) < 1e-9
    assert weights["CASH"] >= 0.05
    assert weights["BTC"] <= 0.03
