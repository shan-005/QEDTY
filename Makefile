.PHONY: sync install clean test test-unit test-integration coverage lint format typecheck security audit build package-check check tree validate demo

sync:
	uv sync --all-groups --all-extras

install: sync

test:
	uv run pytest -q

test-unit:
	uv run pytest -q -m unit

test-integration:
	uv run pytest -q -m integration

coverage:
	uv run pytest --cov=qedty --cov-report=term-missing --cov-report=xml --cov-fail-under=0

lint:
	uv run ruff check src tests

format:
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

security:
	uv run bandit -r src -ll

audit:
	uv run pip-audit

build:
	uv run python -m build

package-check: build
	uv run twine check dist/*

validate:
	uv run qedty validate

demo:
	uv run qedty demo

check: test lint format typecheck security audit package-check validate

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov build dist
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

tree:
	tree -a -I '__pycache__|.venv|.git|*.pyc|.pytest_cache|.mypy_cache|.ruff_cache|build|dist|htmlcov|.qedty*'
