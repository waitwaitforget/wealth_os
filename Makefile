.PHONY: setup lint lint-fix typecheck test coverage ci docs demo clean api dashboard

setup:
	uv sync --all-groups
	uv run pre-commit install

# Backend
api:
	uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
dashboard:
	cd apps/web && npm run dev

dashboard-build:
	cd apps/web && npm run build

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/wealth_os/ --ignore-missing-imports

test:
	uv run pytest -q

coverage:
	uv run pytest --cov=wealth_os --cov-report=term --cov-report=html -q

ci: lint typecheck test
	@echo "CI: all checks passed"

docs:
	uv run mkdocs build --strict

docs-serve:
	uv run mkdocs serve

demo:
	uv run python examples/run_demo.py

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '.DS_Store' -delete 2>/dev/null || true
	rm -rf htmlcov/ site/ dist/ .mypy_cache/ .ruff_cache/
