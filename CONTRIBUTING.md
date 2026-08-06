# Contributing to Wealth OS

## Getting Started

```bash
git clone <repo-url> && cd wealth_os_v1
make setup    # install deps + pre-commit hooks
make test     # verify everything works
make demo     # run the demo pipeline
```

## Development Workflow

1. Create a feature branch from `main`: `git checkout -b feature/<issue>-<name>`
2. Make changes with [conventional commits](https://www.conventionalcommits.org/)
3. Run `make ci` locally before pushing
4. Open a PR against `main`
5. Ensure all CI checks pass

## Code Standards

- **Python 3.12+** only
- **Ruff** for formatting and linting (run `make lint` / `make lint-fix`)
- **mypy** for type checking (run `make typecheck`)
- Follow existing patterns in `src/wealth_os/domain/`
- Domain code must NOT depend on VectorBT, Qlib, or data source SDKs
- Cash must always be treated as an explicit asset
- All weights must sum to 1 (including cash)

## Testing

- Write tests for new features and bug fixes
- Place unit tests in `tests/unit/`, integration in `tests/integration/`
- Use pytest with Hypothesis for property-based tests
- Run `make coverage` to check coverage

## Pull Requests

- Each PR should be small (<500 lines substantive code)
- One verifiable goal per PR
- Financial semantic changes must be in their own PR
- Include a clear description of what changed and why
- Link related Issues and ADRs

## Architecture Decision Records (ADR)

Create an ADR under `docs/adr/` when introducing:
- Architecture style changes
- Data format or timing semantics changes
- Backtest execution order changes
- Return calculation methodology changes
- Risk management or capital governance changes
- Third-party framework adoption
- Live trading permissions or security changes

## Documentation

- Update relevant docs when changing behavior
- Docs are built with MkDocs Material (`make docs-serve` for local preview)
- All documentation changes are verified in CI

## Questions?

Open an issue or discuss in the relevant GitHub Discussion.
