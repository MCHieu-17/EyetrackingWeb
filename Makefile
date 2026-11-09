# Lệnh thường dùng cho repo EyeLearning.
#
#   make check        # gate nhanh (ruff, lint, typecheck, compose config)
#   make check-full   # gate đầy đủ trước khi merge
#   make test-frontend
#   make test-backend
#   make build
#   make up / make down / make smoke
#   make bundle-report / make loadtest / make e2e

.PHONY: check check-full test-backend test-frontend build up down smoke bundle-report loadtest e2e

check:
	./scripts/check.sh

check-full:
	./scripts/check.sh --full

test-backend:
	./scripts/test_backend.sh

test-frontend:
	cd frontend && npm run test

build:
	cd frontend && npm run build

up:
	docker compose up -d --build

down:
	docker compose down

smoke:
	./scripts/smoke.sh

bundle-report:
	node scripts/bundle-report.mjs

loadtest:
	./scripts/loadtest.sh

e2e:
	./scripts/e2e.sh
