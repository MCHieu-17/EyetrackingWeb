# Lệnh thường dùng cho repo EyeLearning.
#
#   make check        # gate nhanh (ruff, lint, typecheck, compose config)
#   make check-full   # gate đầy đủ trước khi merge
#   make test-frontend
#   make test-backend
#   make build
#   make up / make down / make smoke
#   make bundle-report / make loadtest / make e2e

.PHONY: check check-full test-backend test-frontend build up down smoke bundle-report loadtest e2e clean

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

# Chỉ xoá artifact tái tạo được. Không xoá .env, media, backups, weights,
# node_modules hoặc .venv.
clean:
	find backend services scripts -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache backend/.pytest_cache services/chatbot/.pytest_cache
	rm -rf frontend/.next frontend/test-results frontend/playwright-report
	rm -f frontend/tsconfig.tsbuildinfo frontend/next-env.d.ts
	rm -f frontend/public/pdf.worker.min.mjs
	rm -rf frontend/public/pdfjs
