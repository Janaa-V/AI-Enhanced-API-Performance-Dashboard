SHELL := /bin/sh
.DEFAULT_GOAL := help

BACKEND_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
UV ?= $(shell command -v uv 2>/dev/null || ( [ -x "$$HOME/.local/bin/uv" ] && echo "$$HOME/.local/bin/uv" ) || echo "uv")
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help check-uv install sync env setup run serve lint format format-check typecheck audit pre-commit pre-commit-install check test migrate migration clean-logs clean-cache clean

help:
	@printf '%s\n' \
	  'Backend commands (run from backend/):' \
	  '  make setup               Install dependencies and create .env if missing' \
	  '  make install             Sync dependencies; create/update uv.lock' \
	  '  make sync                Sync dependencies using the existing lockfile' \
	  '  make env                 Copy .env.example without replacing an existing .env' \
	  '  make run                 Start the backend with automatic reload' \
	  '  make serve               Start the backend without reload' \
	  '  make check               Run lint, formatting, type checks, and tests' \
	  '  make lint                Run Ruff linter' \
	  '  make format              Format Python code with Ruff' \
	  '  make format-check        Check formatting with Ruff' \
	  '  make typecheck           Run static type checks with Pyright' \
	  '  make audit               Audit dependencies for CVEs with pip-audit' \
	  '  make test                Run backend tests with pytest' \
	  '  make migrate             Apply database migrations (alembic upgrade head)' \
	  '  make migration MSG=text  Generate a migration from model changes; review it' \
	  '  make pre-commit          Run pre-commit hooks on all files' \
	  '  make pre-commit-install  Install pre-commit Git hooks' \
	  '  make clean-logs          Delete backend .log and numbered rotated log files' \
	  '  make clean-cache         Delete project Python/tool caches' \
	  '  make clean               Run both cleanup commands' \
	  '' \
	  'Overrides: make run PORT=8001 HOST=0.0.0.0' \
	  '           make setup UV=/absolute/path/to/uv' \
	  'Cleanup preserves .env, database configuration, .venv, and uv.lock.'

check-uv:
	@command -v "$(UV)" >/dev/null 2>&1 || { \
	  printf '%s\n' 'uv is unavailable. Restart your terminal after installation or set UV=/path/to/uv.' >&2; \
	  exit 1; \
	}

install: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" sync

sync: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" sync --locked

env:
	@if [ -e "$(BACKEND_DIR)/.env" ] || [ -L "$(BACKEND_DIR)/.env" ]; then \
	  printf '%s\n' 'Existing backend/.env preserved.'; \
	else \
	  cp -n "$(BACKEND_DIR)/.env.example" "$(BACKEND_DIR)/.env" && \
	  printf '%s\n' 'Created backend/.env from the example; update settings as needed.'; \
	fi

setup: install env

run: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run uvicorn app.main:app --reload --host "$(HOST)" --port "$(PORT)"

serve: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run uvicorn app.main:app --host "$(HOST)" --port "$(PORT)"

lint: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run ruff check .

format: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run ruff format .

format-check: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run ruff format --check .

typecheck: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run pyright

audit: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run pip-audit

pre-commit: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run pre-commit run --all-files

pre-commit-install: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run pre-commit install

check: lint format-check typecheck test

test: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run pytest

migrate: check-uv
	cd "$(BACKEND_DIR)" && "$(UV)" run alembic upgrade head

migration: check-uv
	@test -n "$(MSG)" || { printf '%s\n' 'Usage: make migration MSG="describe the change"' >&2; exit 1; }
	cd "$(BACKEND_DIR)" && "$(UV)" run alembic revision --autogenerate -m "$(MSG)"

clean-logs:
	@find "$(BACKEND_DIR)" -type d \( -name .venv -o -name .git -o -name node_modules \) -prune -o \
	  -type f \( -name '*.log' -o -name '*.log.[0-9]*' \) -exec rm -f -- {} +
	@printf '%s\n' 'Removed backend log files.'

clean-cache:
	@find "$(BACKEND_DIR)/app" "$(BACKEND_DIR)/scripts" "$(BACKEND_DIR)/tests" \
	  -type d -name __pycache__ -prune -exec rm -rf -- {} +
	@rm -rf -- "$(BACKEND_DIR)/.pytest_cache" "$(BACKEND_DIR)/.ruff_cache" "$(BACKEND_DIR)/.mypy_cache" "$(BACKEND_DIR)/htmlcov"
	@rm -f -- "$(BACKEND_DIR)/.coverage" "$(BACKEND_DIR)"/.coverage.*
	@printf '%s\n' 'Removed backend Python and tool caches.'

clean: clean-logs clean-cache
