# Tài liệu nghiên cứu pipeline gaze

Báo cáo và số đo của nghiên cứu gốc (repo `EyetrackingResearch`, commit `f8bf481`),
dùng làm chuẩn so sánh cho pipeline trong `services/gaze/`. Pipeline torch gốc và
công cụ thu/chấm **không** nằm trong repo này; chúng vẫn còn trong lịch sử repo
nghiên cứu.

| File | Nội dung |
|---|---|
| `architecture.md` | Kiến trúc pipeline, hợp đồng dữ liệu, chọn detector/UniGaze/precision |
| `accuracy_report.md` | Độ chính xác theo precision (fp32/fp16) và detector |
| `benchmark_report.md` | FPS/latency/VRAM theo độ phân giải, fp32/fp16 |
| `models/accuracy_report.md` | Độ chính xác theo 4 kích thước UniGaze (B16/L16/H14/H14-cross) |
| `models/benchmark_report.md` | FPS/latency/VRAM của 4 kích thước UniGaze |
| `figures/`, `models/figures/` | Biểu đồ CDF, scatter, FPS, latency breakdown |

Dữ liệu và kết quả thô:

- Ảnh mặt 100 target / 800 frame: `benchmarks/gaze/testdata/20261124_175802_frontal/`
  (gitignored, không commit vì là dữ liệu khuôn mặt thật).
- JSON kết quả từng cấu hình: `benchmarks/gaze/research-results/`.

Số đo của pipeline hiện tại (ONNX, không MediaPipe/torch) nằm ở
`benchmarks/baseline/{pre-onnx,post-onnx,post-landmarker-onnx}/` và được tổng hợp
trong `services/gaze/README.md`.
