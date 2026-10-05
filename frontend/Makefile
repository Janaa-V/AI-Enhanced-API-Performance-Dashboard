SHELL := /bin/sh
.DEFAULT_GOAL := help

FRONTEND_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
BACKEND_DIR := $(FRONTEND_DIR)/../backend
NODE ?= node
NPM ?= npm

.PHONY: help check-node install sync env setup run build preview lint lint-css format format-check typecheck test test-watch audit api-types api-check contract check clean-build clean-cache clean

help:
	@printf '%s\n' \
	  'Frontend commands (run from frontend/):' \
	  '  make setup          Install dependencies and create .env if missing' \
	  '  make install        Install dependencies; create/update package-lock.json' \
	  '  make sync           Install dependencies exactly as locked (npm ci)' \
	  '  make env            Copy .env.example without replacing an existing .env' \
	  '  make run            Start the dev server on http://localhost:5173' \
	  '  make build          Type-check and build the production bundle into dist/' \
	  '  make preview        Serve the production build locally' \
	  '  make check          Run API-type, lint, format, type and test checks, as CI does' \
	  '  make lint           Run ESLint' \
	  '  make lint-css       Run Stylelint' \
	  '  make format         Format files with Prettier' \
	  '  make format-check   Check formatting with Prettier' \
	  '  make typecheck      Run TypeScript type checks' \
	  '  make test           Run the tests once' \
	  '  make test-watch     Rerun the tests on every save' \
	  '  make audit          Audit dependencies for known vulnerabilities' \
	  '  make api-types      Regenerate src/api/schema.gen.ts from openapi.json' \
	  '  make api-check      Fail if src/api/schema.gen.ts is out of date' \
	  '  make contract       Refresh openapi.json from the backend, then the types' \
	  '  make clean-build    Delete dist/ and coverage/' \
	  '  make clean-cache    Delete Vite, Vitest and TypeScript caches' \
	  '  make clean          Run both cleanup commands' \
	  '' \
	  'The dev server always uses port 5173: the backend'"'"'s default CORS_ORIGINS allows only it.' \
	  'Overrides: make install NPM=/absolute/path/to/npm' \
	  'Cleanup preserves .env, node_modules and package-lock.json.'

check-node:
	@command -v "$(NODE)" >/dev/null 2>&1 && command -v "$(NPM)" >/dev/null 2>&1 || { \
	  printf '%s\n' 'Node.js and npm are unavailable. Install Node.js 20.19 or later.' >&2; \
	  exit 1; \
	}
	@"$(NODE)" -e 'const [a, b] = process.versions.node.split(".").map(Number); if (a < 20 || (a === 20 && b < 19)) { console.error(`Node.js 20.19 or later is required; found $${process.versions.node}.`); process.exit(1) }'

install: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" install

sync: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" ci

env:
	@if [ -e "$(FRONTEND_DIR)/.env" ] || [ -L "$(FRONTEND_DIR)/.env" ]; then \
	  printf '%s\n' 'Existing frontend/.env preserved.'; \
	else \
	  cp -n "$(FRONTEND_DIR)/.env.example" "$(FRONTEND_DIR)/.env" && \
	  printf '%s\n' 'Created frontend/.env from the example; it points at the local backend.'; \
	fi

setup: install env

run: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run dev

build: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run build

preview: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run preview

lint: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run lint

lint-css: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run lint:css

format: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run format

format-check: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run format:check

typecheck: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run typecheck

test: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" test

test-watch: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run test:watch

audit: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" audit

api-types: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run generate:api

api-check: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run check:api

# The backend writes openapi.json (it needs uv, not a database); the frontend turns it into types.
contract:
	$(MAKE) -C "$(BACKEND_DIR)" openapi
	$(MAKE) -C "$(FRONTEND_DIR)" api-types

check: check-node
	cd "$(FRONTEND_DIR)" && "$(NPM)" run check

clean-build:
	@rm -rf -- "$(FRONTEND_DIR)/dist" "$(FRONTEND_DIR)/coverage"
	@printf '%s\n' 'Removed frontend build output.'

clean-cache:
	@rm -rf -- "$(FRONTEND_DIR)/node_modules/.vite" "$(FRONTEND_DIR)/node_modules/.vite-temp" \
	  "$(FRONTEND_DIR)/node_modules/.tmp"
	@printf '%s\n' 'Removed frontend tool caches.'

clean: clean-build clean-cache
