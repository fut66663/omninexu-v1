.PHONY: install dev-up dev-down seed api test lint format clean

install:
	uv sync

dev-up:
	docker compose -f .docker/docker-compose.yml up -d

dev-down:
	docker compose -f .docker/docker-compose.yml down

seed:
	uv run python scripts/seed_snp500.py

api:
	uv run uvicorn src.omninexu.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest

lint:
	uv run ruff check src tests scripts

format:
	uv run ruff format src tests scripts

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
