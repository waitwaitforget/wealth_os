import pandas as pd

from wealth_os.domain.models import BacktestResult
from wealth_os.validation.checks import validate_accounting


def test_accounting_identity():
    idx = pd.date_range("2024-01-01", periods=2)
    result = BacktestResult(
        nav=pd.Series([100, 110], index=idx),
        unit_nav=pd.Series([1.0, 1.1], index=idx),
        units=pd.Series([100, 100], index=idx),
        cash=pd.Series([20, 20], index=idx),
        positions_value=pd.DataFrame({"A": [80, 90]}, index=idx),
        actual_weights=pd.DataFrame({"A": [.8, 90/110], "CASH": [.2, 20/110]}, index=idx),
        target_weights=pd.DataFrame({"A": [.8, .8], "CASH": [.2, .2]}, index=idx),
        external_cash_flows=pd.Series([0, 0], index=idx),
        transaction_costs=pd.Series([0, 0], index=idx),
        turnover=pd.Series([0, 0], index=idx),
        orders=pd.DataFrame(),
    )
    assert validate_accounting(result) == []
