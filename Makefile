.PHONY: install lint format format-check typecheck test check clean dev

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint format-check typecheck test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info

dev:
	uv run uvicorn vc_audit.api.server:app --reload
