# Frontend E2E — test isolation

Playwright **không** được mặc định gọi backend development (`localhost:8001`).

| Biến | Mặc định | Dùng cho |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:3012` | Next.js test server |
| `E2E_API_URL` | `http://localhost:8011` | Backend test |
| `E2E_GAZE_URL` | `http://localhost:8010` | Gaze test |

Chạy backend test ở cổng 8011 với DB `eyelearning_refactor_test` trước:

```bash
./scripts/test_db.sh
# terminal riêng: chạy backend test với DATABASE_URL trỏ DB test
cd frontend && npm run test:e2e
```

Nếu backend test chưa chạy, E2E phải fail rõ ràng; không fallback sang backend
development.
