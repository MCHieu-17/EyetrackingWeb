# Gaze artifacts — 20261122T1640Z-after-10phase

| File | Nguồn | Ghi chú |
|---|---|---|
| `stage-latency.json` | run này (`benchmarks/gaze/run.sh`) | Stage 480/720/1080 px, fp16 |
| `ws-load.json` | run này | Payload server mặc định (JPEG q0,90) |
| `ws-load-client.json` | run này | Payload client 480px/q0,78 |
| `capture-ab.json` | run này (`benchmarks/gaze/tools/compare_capture.py`) | A/B width×quality, không calibration → `px_delta_*` = null |
| `capture-ab-calibrated.json` | **chép từ run `20261122T062123Z-baseline`** | A/B có model calibration thật, đo trên cùng harness/cùng code capture (`9e60f53`); commit `d41d264` chỉ đổi đồng bộ layout chat AOI, không chạm capture. Run hiện tại không tái tạo được vì probe không có file calibration UBJ. |

Nếu cần số `px_delta` tuyệt đối, chạy lại `compare_capture` với
`--calibration <file.ubj>` như mô tả trong `docs/perf-results.md`.
