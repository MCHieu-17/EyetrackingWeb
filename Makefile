# Lệnh thường dùng cho repo EyeLearning.
#
#   make check        # gate nhanh (ruff, lint, typecheck, compose config)
#   make check-full   # thêm knip + frontend build
#   make build
#   make up / make down / make smoke

.PHONY: check check-full test-fast test-smoke build up down smoke clean

check:
	./scripts/check.sh

check-full:
	./scripts/check.sh --full

test-fast:
	./scripts/test_fast.sh

test-smoke:
	./scripts/test_smoke.sh

build:
	cd frontend && npm run build

up:
	docker compose up -d --build

down:
	docker compose down

smoke:
	./scripts/smoke.sh

# Chỉ xoá artifact tái tạo được. Không xoá .env, media, backups, weights,
# node_modules hoặc .venv.
clean:
	find backend services scripts -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache backend/.pytest_cache services/chatbot/.pytest_cache
	rm -rf frontend/.next frontend/test-results frontend/playwright-report
	rm -f frontend/tsconfig.tsbuildinfo frontend/next-env.d.ts
	rm -f frontend/public/pdf.worker.min.mjs
	rm -rf frontend/public/pdfjs
