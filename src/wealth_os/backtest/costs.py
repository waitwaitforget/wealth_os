from __future__ import annotations

from dataclasses import dataclass

from wealth_os.domain.models import TransactionCostConfig


@dataclass
class TransactionCostModel:
    config: TransactionCostConfig

    def estimate(self, notional: float, is_sell: bool, is_fx_trade: bool = False) -> float:
        bps = (
            self.config.commission_bps
            + self.config.spread_bps
            + self.config.slippage_bps
            + self.config.market_impact_bps
        )
        if is_sell:
            bps += self.config.sell_tax_bps
        if is_fx_trade:
            bps += self.config.fx_bps
        return abs(notional) * bps / 10_000.0
