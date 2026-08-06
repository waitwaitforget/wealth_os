from __future__ import annotations

import importlib.util


class VectorBTBacktestEngine:
    """Optional adapter boundary.

    The native engine remains the accounting reference implementation. This
    adapter is intentionally isolated so VectorBT can be added or replaced
    without changing domain or allocation code.
    """

    def __init__(self) -> None:
        if importlib.util.find_spec("vectorbt") is None:
            raise RuntimeError("vectorbt is not installed; install wealth-os[vectorbt]")
        import vectorbt as vbt  # type: ignore
        self.vbt = vbt

    def run_from_orders(self, close, size, fees=0.0):
        return self.vbt.Portfolio.from_orders(close=close, size=size, fees=fees)
