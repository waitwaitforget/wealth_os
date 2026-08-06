# Wealth OS

A cash-aware, event-driven, explainable multi-asset wealth operating system for long-term personal investing.

> Current status: research prototype. Synthetic demo results are not real investment performance.

## Documentation

- [Documentation index](docs/index.md)
- [Vision](docs/00_vision.md)
- [Architecture](docs/01_architecture.md)
- [Roadmap](docs/17_roadmap.md)
- [Validation system](docs/09_validation_governance.md)
- [Git governance](docs/19_git_governance.md)

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
git clone <repo-url> && cd wealth_os_v1
make setup
make test
make demo
```

Or step by step:

```bash
uv sync --all-groups
uv run pytest -q
uv run python examples/run_demo.py
```

## Development

```bash
make lint       # ruff check + format
make typecheck  # mypy
make test       # pytest
make coverage   # pytest with coverage report
make ci         # full CI gate (lint + typecheck + test)
make docs       # build documentation
make docs-serve # serve documentation locally
make demo       # run demo pipeline
```

## Dependency groups

```bash
uv sync                   # core only
uv sync --group dev       # core + dev tools
uv sync --group docs      # core + docs
uv sync --group research  # core + VectorBT + cvxpy
uv sync --all-groups      # everything
```

## Current prototype capabilities

- Cash as a first-class investable asset
- Core / satellite / alternative sleeves
- Valuation, trend and volatility factor prototypes
- Event-driven rebalance triggers
- External contributions and unit-NAV accounting
- TWR, XIRR, drawdown and risk-adjusted analytics
- Native deterministic backtester
- Optional VectorBT adapter boundary
- Data, accounting, constraint and no-lookahead validation

The domain, factor, allocation and validation packages must remain independent of VectorBT and Qlib.
