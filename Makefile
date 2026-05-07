.PHONY: install lint format format-check typecheck test check clean dev ui examples

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

ui:
	uv run --extra ui streamlit run src/vc_audit/ui/app.py

examples:
	@mkdir -p examples/outputs
	@for f in examples/inputs/*.json; do \
		stem=$$(basename $$f .json); \
		uv run vc-audit value -i $$f --format json > examples/outputs/$$stem.json; \
		uv run vc-audit value -i $$f --format markdown > examples/outputs/$$stem.md; \
		echo "examples/outputs/$$stem.{json,md}"; \
	done
