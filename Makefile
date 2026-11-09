# Lệnh thường dùng cho repo EyeLearning.
#
#   make check        # gate nhanh (ruff, lint, typecheck, compose config)
#   make check-full   # gate đầy đủ trước khi merge
#   make test-frontend
#   make test-backend
#   make build
#   make up / make down / make smoke

.PHONY: check check-full test-backend test-frontend build up down smoke

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
