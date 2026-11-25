# Báo cáo benchmark kiến trúc pipeline eye tracking

> **Nguồn:** báo cáo này được chuyển từ repo nghiên cứu `EyetrackingResearch`
> (commit `f8bf481`) sang `docs/`. Pipeline torch gốc và các công cụ thu/chấm
> (`tools/collect.py`, `tools/evaluate.py`, `benchmark/*.py`) **không** còn trong
> repo này; lệnh `python tools/...` bên dưới chỉ chạy trong repo nghiên cứu đó.
> Dữ liệu ảnh mặt và kết quả thô nằm ở `benchmarks/gaze/testdata/` (gitignored)
> và `benchmarks/gaze/research-results/`.

- Thời điểm đo: `2026-11-24T20:19:03`
- Mã lần chạy: `20261124_200814`
- Ảnh đầu vào: `benchmarks/gaze/testdata/20261124_175802_frontal/frames/0001/00.jpg` (resize về từng độ phân giải bên dưới)
- Số vòng đo: 100 vòng/cấu hình trên CUDA

## Tóm tắt

- Cấu hình nhanh nhất ở 640x480: **MediaPipe / CUDA / UniGaze-B16 / fp16** – **67.8 FPS** (14.7 ms/frame).
- Trên GPU, MediaPipe đạt 54 FPS còn FAN đạt 27 FPS (chậm hơn 2.0 lần).
- VRAM ổn định tối đa 2775 MB; riêng lần suy luận đầu, FAN có thể tạo đỉnh VRAM tạm thời rất lớn (xem mục Nhận xét).

## 1. Môi trường đo

| Thành phần | Giá trị |
| --- | --- |
| OS | Linux 7.0.0-43-generic (hieuserver) |
| CPU | x86_64 / 12 luồng |
| RAM | 30.7 GB |
| GPU | NVIDIA GeForce RTX 3060 / 11.6 GB |
| Python | 3.13.18 |
| PyTorch | 2.15.0+cu132 |
| CUDA / cuDNN | 13.2 / 92600 |
| OpenCV | 5.1.0 |
| MediaPipe | 1.2.3 |
| face_alignment | 1.5.0 |
| UniGaze | 0.1.3 |

## 2. Cách chạy lại

```bash
# Chạy toàn bộ cấu hình (mediapipe/face_alignment x cuda/cpu), ghi JSON + báo cáo
python benchmark/benchmark.py

# Chỉ đo một số cấu hình / độ phân giải
python benchmark/benchmark.py --detectors mediapipe --devices cuda --resolutions 640x480

# So sánh fp16 vs fp32 cho UniGaze (fp16 chỉ chạy trên cuda)
python benchmark/benchmark.py --devices cuda --precisions fp32,fp16
```

Kết quả thô (JSON từng cấu hình + `aggregate.json`) nằm trong `benchmarks/gaze/research-results/results/20261124_200814/`, bản mới nhất ở `benchmarks/gaze/research-results/results/latest.json`.

## 3. Kết quả tổng hợp

### Độ phân giải 640x480

| Bộ phát hiện | Thiết bị | FPS | Mean (ms) | p50 (ms) | p95 (ms) | Khởi tạo (s) | VRAM ổn định (MB) | VRAM đỉnh (MB) | RAM (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe | CUDA | 54.3 | 18.4 | 18.0 | 19.6 | 0.62 | 345 | 345 | 1388 |
| MediaPipe | CUDA | 67.8 | 14.7 | 14.4 | 15.0 | 0.63 | 189 | 189 | 1620 |
| MediaPipe | CUDA | 27.9 | 35.9 | 35.7 | 36.6 | 2.15 | 1178 | 1178 | 1384 |
| MediaPipe | CUDA | 49.0 | 20.4 | 19.7 | 22.7 | 2.12 | 594 | 594 | 1595 |
| MediaPipe | CUDA | 13.0 | 77.2 | 76.9 | 77.6 | 4.39 | 2496 | 2496 | 1384 |
| MediaPipe | CUDA | 26.6 | 37.6 | 37.5 | 38.1 | 4.40 | 1245 | 1245 | 1594 |
| MediaPipe | CUDA | 13.0 | 77.0 | 76.8 | 77.4 | 4.43 | 2496 | 2496 | 1384 |
| MediaPipe | CUDA | 26.6 | 37.6 | 37.2 | 38.1 | 4.41 | 1245 | 1245 | 1594 |
| FAN (face_alignment) | CUDA | 27.2 | 36.8 | 36.7 | 37.0 | 0.89 | 552 | 8997 | 1917 |
| FAN (face_alignment) | CUDA | 30.2 | 33.1 | 32.6 | 33.0 | 0.91 | 395 | 8841 | 2167 |
| FAN (face_alignment) | CUDA | 18.0 | 55.7 | 55.7 | 56.3 | 2.41 | 1385 | 9828 | 1918 |
| FAN (face_alignment) | CUDA | 25.5 | 39.3 | 38.7 | 39.4 | 2.40 | 803 | 9249 | 2173 |
| FAN (face_alignment) | CUDA | 10.3 | 97.1 | 97.1 | 97.5 | 4.67 | 2697 | 11142 | 1921 |
| FAN (face_alignment) | CUDA | 17.6 | 56.8 | 56.7 | 57.0 | 4.67 | 1448 | 9894 | 2187 |
| FAN (face_alignment) | CUDA | 10.3 | 97.3 | 97.2 | 97.6 | 4.69 | 2697 | 11142 | 1953 |
| FAN (face_alignment) | CUDA | 17.6 | 56.9 | 56.7 | 57.0 | 4.69 | 1448 | 9894 | 2203 |

### Độ phân giải 1280x720

| Bộ phát hiện | Thiết bị | FPS | Mean (ms) | p50 (ms) | p95 (ms) | Khởi tạo (s) | VRAM ổn định (MB) | VRAM đỉnh (MB) | RAM (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe | CUDA | 53.6 | 18.7 | 18.4 | 19.7 | 0.63 | 345 | 345 | 1395 |
| MediaPipe | CUDA | 66.8 | 15.0 | 14.3 | 15.6 | 0.62 | 189 | 189 | 1628 |
| MediaPipe | CUDA | 27.7 | 36.1 | 35.6 | 36.7 | 2.11 | 1178 | 1178 | 1392 |
| MediaPipe | CUDA | 47.9 | 20.9 | 20.2 | 23.1 | 2.15 | 594 | 594 | 1602 |
| MediaPipe | CUDA | 13.0 | 76.7 | 76.4 | 77.0 | 4.40 | 2496 | 2496 | 1393 |
| MediaPipe | CUDA | 26.8 | 37.2 | 36.7 | 37.9 | 4.40 | 1245 | 1245 | 1603 |
| MediaPipe | CUDA | 13.1 | 76.6 | 76.3 | 76.9 | 4.40 | 2496 | 2496 | 1392 |
| MediaPipe | CUDA | 26.9 | 37.2 | 36.7 | 37.3 | 4.40 | 1245 | 1245 | 1603 |
| FAN (face_alignment) | CUDA | 20.5 | 48.7 | 48.6 | 48.9 | 0.88 | 630 | 9261 | 1962 |
| FAN (face_alignment) | CUDA | 22.2 | 45.0 | 44.6 | 45.2 | 0.92 | 474 | 9104 | 2158 |
| FAN (face_alignment) | CUDA | 14.7 | 67.9 | 67.5 | 68.5 | 2.43 | 1461 | 10091 | 1923 |
| FAN (face_alignment) | CUDA | 19.7 | 50.7 | 50.6 | 50.9 | 2.42 | 882 | 9513 | 2173 |
| FAN (face_alignment) | CUDA | 9.2 | 109.1 | 109.1 | 109.7 | 4.65 | 2775 | 11161 | 1929 |
| FAN (face_alignment) | CUDA | 14.6 | 68.5 | 68.5 | 68.8 | 4.68 | 1528 | 10158 | 2207 |
| FAN (face_alignment) | CUDA | 9.1 | 109.6 | 109.3 | 109.7 | 4.65 | 2775 | 11161 | 1957 |
| FAN (face_alignment) | CUDA | 14.6 | 68.6 | 68.5 | 68.8 | 4.71 | 1528 | 10158 | 2207 |

### So sánh precision fp16 vs fp32

| Bộ phát hiện | Độ phân giải | Precision | FPS | Mean (ms) | p95 (ms) | UniGaze (ms) | Detect (ms) | VRAM (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe | 640x480 | fp32 | 54.3 | 18.4 | 19.6 | 8.4 | 8.6 | 345 |
| MediaPipe | 640x480 | fp16 | 67.8 | 14.7 | 15.0 | 4.5 | 8.9 | 189 |
| MediaPipe | 640x480 | fp32 | 27.9 | 35.9 | 36.6 | 26.4 | 8.0 | 1178 |
| MediaPipe | 640x480 | fp16 | 49.0 | 20.4 | 22.7 | 10.4 | 8.6 | 594 |
| MediaPipe | 640x480 | fp32 | 13.0 | 77.2 | 77.6 | 67.5 | 8.2 | 2496 |
| MediaPipe | 640x480 | fp16 | 26.6 | 37.6 | 38.1 | 28.2 | 8.1 | 1245 |
| MediaPipe | 640x480 | fp32 | 13.0 | 77.0 | 77.4 | 67.6 | 8.3 | 2496 |
| MediaPipe | 640x480 | fp16 | 26.6 | 37.6 | 38.1 | 28.3 | 8.1 | 1245 |
| FAN (face_alignment) | 640x480 | fp32 | 27.2 | 36.8 | 37.0 | 8.2 | 27.5 | 552 |
| FAN (face_alignment) | 640x480 | fp16 | 30.2 | 33.1 | 33.0 | 4.1 | 27.5 | 395 |
| FAN (face_alignment) | 640x480 | fp32 | 18.0 | 55.7 | 56.3 | 25.8 | 29.1 | 1385 |
| FAN (face_alignment) | 640x480 | fp16 | 25.5 | 39.3 | 39.4 | 10.1 | 27.4 | 803 |
| FAN (face_alignment) | 640x480 | fp32 | 10.3 | 97.1 | 97.5 | 66.7 | 29.3 | 2697 |
| FAN (face_alignment) | 640x480 | fp16 | 17.6 | 56.8 | 57.0 | 27.9 | 27.7 | 1448 |
| FAN (face_alignment) | 640x480 | fp32 | 10.3 | 97.3 | 97.6 | 66.8 | 29.4 | 2697 |
| FAN (face_alignment) | 640x480 | fp16 | 17.6 | 56.9 | 57.0 | 27.9 | 27.7 | 1448 |
| MediaPipe | 1280x720 | fp32 | 53.6 | 18.7 | 19.7 | 8.4 | 9.2 | 345 |
| MediaPipe | 1280x720 | fp16 | 66.8 | 15.0 | 15.6 | 4.5 | 8.9 | 189 |
| MediaPipe | 1280x720 | fp32 | 27.7 | 36.1 | 36.7 | 26.3 | 8.1 | 1178 |
| MediaPipe | 1280x720 | fp16 | 47.9 | 20.9 | 23.1 | 10.6 | 8.9 | 594 |
| MediaPipe | 1280x720 | fp32 | 13.0 | 76.7 | 77.0 | 67.4 | 7.8 | 2496 |
| MediaPipe | 1280x720 | fp16 | 26.8 | 37.2 | 37.9 | 28.0 | 7.4 | 1245 |
| MediaPipe | 1280x720 | fp32 | 13.1 | 76.6 | 76.9 | 67.5 | 7.6 | 2496 |
| MediaPipe | 1280x720 | fp16 | 26.9 | 37.2 | 37.3 | 28.0 | 7.5 | 1245 |
| FAN (face_alignment) | 1280x720 | fp32 | 20.5 | 48.7 | 48.9 | 8.2 | 39.5 | 630 |
| FAN (face_alignment) | 1280x720 | fp16 | 22.2 | 45.0 | 45.2 | 4.1 | 39.3 | 474 |
| FAN (face_alignment) | 1280x720 | fp32 | 14.7 | 67.9 | 68.5 | 25.8 | 40.7 | 1461 |
| FAN (face_alignment) | 1280x720 | fp16 | 19.7 | 50.7 | 50.9 | 10.2 | 39.3 | 882 |
| FAN (face_alignment) | 1280x720 | fp32 | 9.2 | 109.1 | 109.7 | 66.7 | 41.3 | 2775 |
| FAN (face_alignment) | 1280x720 | fp16 | 14.6 | 68.5 | 68.8 | 28.0 | 39.3 | 1528 |
| FAN (face_alignment) | 1280x720 | fp32 | 9.1 | 109.6 | 109.7 | 66.8 | 41.8 | 2775 |
| FAN (face_alignment) | 1280x720 | fp16 | 14.6 | 68.6 | 68.8 | 27.9 | 39.4 | 1528 |

- Chỉ **UniGaze** chạy theo precision này; bước detect (MediaPipe TFLite / FAN) giữ nguyên nên chênh lệch FPS nằm ở cột **UniGaze**.
- fp16 chỉ hợp lệ trên CUDA; cấu hình CPU luôn fp32.

### So sánh kích thước UniGaze

| Model | Bộ phát hiện | Độ phân giải | FPS fp32 | FPS fp16 | UniGaze fp32 (ms) | UniGaze fp16 (ms) | VRAM fp32 (MB) | VRAM fp16 (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UniGaze-B16 | MediaPipe | 640x480 | 54.3 | 67.8 | 8.4 | 4.5 | 345 | 189 |
| UniGaze-L16 | MediaPipe | 640x480 | 27.9 | 49.0 | 26.4 | 10.4 | 1178 | 594 |
| UniGaze-H14 | MediaPipe | 640x480 | 13.0 | 26.6 | 67.5 | 28.2 | 2496 | 1245 |
| UniGaze-H14-cross | MediaPipe | 640x480 | 13.0 | 26.6 | 67.6 | 28.3 | 2496 | 1245 |
| UniGaze-B16 | FAN (face_alignment) | 640x480 | 27.2 | 30.2 | 8.2 | 4.1 | 552 | 395 |
| UniGaze-L16 | FAN (face_alignment) | 640x480 | 18.0 | 25.5 | 25.8 | 10.1 | 1385 | 803 |
| UniGaze-H14 | FAN (face_alignment) | 640x480 | 10.3 | 17.6 | 66.7 | 27.9 | 2697 | 1448 |
| UniGaze-H14-cross | FAN (face_alignment) | 640x480 | 10.3 | 17.6 | 66.8 | 27.9 | 2697 | 1448 |
| UniGaze-B16 | MediaPipe | 1280x720 | 53.6 | 66.8 | 8.4 | 4.5 | 345 | 189 |
| UniGaze-L16 | MediaPipe | 1280x720 | 27.7 | 47.9 | 26.3 | 10.6 | 1178 | 594 |
| UniGaze-H14 | MediaPipe | 1280x720 | 13.0 | 26.8 | 67.4 | 28.0 | 2496 | 1245 |
| UniGaze-H14-cross | MediaPipe | 1280x720 | 13.1 | 26.9 | 67.5 | 28.0 | 2496 | 1245 |
| UniGaze-B16 | FAN (face_alignment) | 1280x720 | 20.5 | 22.2 | 8.2 | 4.1 | 630 | 474 |
| UniGaze-L16 | FAN (face_alignment) | 1280x720 | 14.7 | 19.7 | 25.8 | 10.2 | 1461 | 882 |
| UniGaze-H14 | FAN (face_alignment) | 1280x720 | 9.2 | 14.6 | 66.7 | 28.0 | 2775 | 1528 |
| UniGaze-H14-cross | FAN (face_alignment) | 1280x720 | 9.1 | 14.6 | 66.8 | 27.9 | 2775 | 1528 |

- Cùng bộ phát hiện và cùng độ phân giải, chỉ đổi weight UniGaze; cột **UniGaze** là thời gian riêng của tầng gaze (đã gồm tiền xử lý tensor → forward → lấy kết quả).

### Tải hệ thống lúc đo

| Độ phân giải | Bộ phát hiện | Thiết bị | Tải GPU (%) | Xung GPU (MHz) | CPU (%) |
| --- | --- | --- | --- | --- | --- |
| 640x480 | MediaPipe | CUDA | 44 | 1950 / 2130 | 3 |
| 640x480 | MediaPipe | CUDA | 30 | 1807 / 2130 | 2 |
| 640x480 | MediaPipe | CUDA | 71 | 1845 / 2130 | 1 |
| 640x480 | MediaPipe | CUDA | 52 | 1950 / 2130 | 2 |
| 640x480 | MediaPipe | CUDA | 80 | 1762 / 2130 | 2 |
| 640x480 | MediaPipe | CUDA | 79 | 1957 / 2130 | 2 |
| 640x480 | MediaPipe | CUDA | 81 | 1762 / 2130 | 4 |
| 640x480 | MediaPipe | CUDA | 76 | 1957 / 2130 | 1 |
| 640x480 | FAN (face_alignment) | CUDA | 90 | 1957 / 2130 | 1 |
| 640x480 | FAN (face_alignment) | CUDA | 89 | 1950 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 92 | 1950 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 86 | 1957 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 96 | 1762 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 94 | 1957 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 96 | 1762 / 2130 | 2 |
| 640x480 | FAN (face_alignment) | CUDA | 94 | 1957 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 47 | 1957 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 29 | 1807 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 73 | 1867 / 2130 | 4 |
| 1280x720 | MediaPipe | CUDA | 48 | 1957 / 2130 | 1 |
| 1280x720 | MediaPipe | CUDA | 86 | 1770 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 78 | 1957 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 91 | 1762 / 2130 | 2 |
| 1280x720 | MediaPipe | CUDA | 78 | 1957 / 2130 | 2 |
| 1280x720 | FAN (face_alignment) | CUDA | 91 | 1957 / 2130 | 2 |
| 1280x720 | FAN (face_alignment) | CUDA | 92 | 1950 / 2130 | 2 |
| 1280x720 | FAN (face_alignment) | CUDA | 83 | 1920 / 2130 | 2 |
| 1280x720 | FAN (face_alignment) | CUDA | 90 | 1950 / 2130 | 2 |
| 1280x720 | FAN (face_alignment) | CUDA | 97 | 1762 / 2130 | 4 |
| 1280x720 | FAN (face_alignment) | CUDA | 94 | 1957 / 2130 | 3 |
| 1280x720 | FAN (face_alignment) | CUDA | 95 | 1762 / 2130 | 1 |
| 1280x720 | FAN (face_alignment) | CUDA | 95 | 1957 / 2130 | 1 |

> Số đo trên frame tĩnh, chỉ tính phần xử lý của pipeline (không gồm đọc camera, vẽ giao diện và calibration). Số đo có thể bị ảnh hưởng nếu lúc chạy còn ứng dụng khác dùng GPU/CPU; xung GPU càng gần mức tối đa thì số đo càng đáng tin.

## 4. Phân rã thời gian từng tầng

Số liệu là trung bình ms và tỉ lệ % so với tổng thời gian các tầng.

### Độ phân giải 640x480

| Bộ phát hiện | Thiết bị | Chuyển RGB | Detect khuôn mặt | Tiền xử lý | UniGaze | De-normalize | Tổng (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe | CUDA | 0.1 (0%) | 8.6 (47%) | 1.2 (6%) | 8.4 (46%) | 0.1 (0%) | 18.3 |
| MediaPipe | CUDA | 0.1 (0%) | 8.9 (61%) | 1.2 (8%) | 4.5 (30%) | 0.1 (0%) | 14.7 |
| MediaPipe | CUDA | 0.1 (0%) | 8.0 (22%) | 1.2 (3%) | 26.4 (74%) | 0.1 (0%) | 35.9 |
| MediaPipe | CUDA | 0.1 (0%) | 8.6 (42%) | 1.2 (6%) | 10.4 (51%) | 0.1 (0%) | 20.3 |
| MediaPipe | CUDA | 0.1 (0%) | 8.2 (11%) | 1.2 (2%) | 67.5 (88%) | 0.1 (0%) | 77.1 |
| MediaPipe | CUDA | 0.1 (0%) | 8.1 (22%) | 1.2 (3%) | 28.2 (75%) | 0.1 (0%) | 37.7 |
| MediaPipe | CUDA | 0.1 (0%) | 8.3 (11%) | 1.2 (2%) | 67.6 (88%) | 0.1 (0%) | 77.2 |
| MediaPipe | CUDA | 0.1 (0%) | 8.1 (21%) | 1.2 (3%) | 28.3 (75%) | 0.1 (0%) | 37.8 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 27.5 (75%) | 1.1 (3%) | 8.2 (22%) | 0.1 (0%) | 36.8 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 27.5 (84%) | 1.1 (3%) | 4.1 (12%) | 0.1 (0%) | 32.8 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 29.1 (52%) | 1.1 (2%) | 25.8 (46%) | 0.1 (0%) | 56.2 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 27.4 (71%) | 1.1 (3%) | 10.1 (26%) | 0.1 (0%) | 38.7 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 29.3 (30%) | 1.1 (1%) | 66.7 (69%) | 0.1 (0%) | 97.2 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 27.7 (49%) | 1.1 (2%) | 27.9 (49%) | 0.1 (0%) | 56.8 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 29.4 (30%) | 1.1 (1%) | 66.8 (69%) | 0.1 (0%) | 97.4 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 27.7 (49%) | 1.1 (2%) | 27.9 (49%) | 0.1 (0%) | 56.8 |

### Độ phân giải 1280x720

| Bộ phát hiện | Thiết bị | Chuyển RGB | Detect khuôn mặt | Tiền xử lý | UniGaze | De-normalize | Tổng (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe | CUDA | 0.1 (1%) | 9.2 (48%) | 1.3 (7%) | 8.4 (44%) | 0.1 (0%) | 19.1 |
| MediaPipe | CUDA | 0.1 (1%) | 8.9 (60%) | 1.2 (8%) | 4.5 (31%) | 0.1 (0%) | 14.8 |
| MediaPipe | CUDA | 0.2 (0%) | 8.1 (23%) | 1.2 (3%) | 26.3 (73%) | 0.1 (0%) | 35.8 |
| MediaPipe | CUDA | 0.1 (1%) | 8.9 (42%) | 1.3 (6%) | 10.6 (50%) | 0.1 (0%) | 21.0 |
| MediaPipe | CUDA | 0.2 (0%) | 7.8 (10%) | 1.2 (2%) | 67.4 (88%) | 0.1 (0%) | 76.7 |
| MediaPipe | CUDA | 0.2 (0%) | 7.4 (20%) | 1.2 (3%) | 28.0 (76%) | 0.1 (0%) | 36.8 |
| MediaPipe | CUDA | 0.2 (0%) | 7.6 (10%) | 1.2 (2%) | 67.5 (88%) | 0.1 (0%) | 76.6 |
| MediaPipe | CUDA | 0.2 (0%) | 7.5 (20%) | 1.2 (3%) | 28.0 (76%) | 0.1 (0%) | 36.9 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 39.5 (81%) | 1.1 (2%) | 8.2 (17%) | 0.1 (0%) | 49.0 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 39.3 (88%) | 1.1 (2%) | 4.1 (9%) | 0.1 (0%) | 44.7 |
| FAN (face_alignment) | CUDA | 0.2 (0%) | 40.7 (60%) | 1.1 (2%) | 25.8 (38%) | 0.1 (0%) | 67.8 |
| FAN (face_alignment) | CUDA | 0.1 (0%) | 39.3 (77%) | 1.1 (2%) | 10.2 (20%) | 0.1 (0%) | 50.8 |
| FAN (face_alignment) | CUDA | 0.2 (0%) | 41.3 (38%) | 1.1 (1%) | 66.7 (61%) | 0.1 (0%) | 109.3 |
| FAN (face_alignment) | CUDA | 0.2 (0%) | 39.3 (57%) | 1.1 (2%) | 28.0 (41%) | 0.1 (0%) | 68.6 |
| FAN (face_alignment) | CUDA | 0.2 (0%) | 41.8 (38%) | 1.1 (1%) | 66.8 (61%) | 0.1 (0%) | 109.8 |
| FAN (face_alignment) | CUDA | 0.2 (0%) | 39.4 (57%) | 1.1 (2%) | 27.9 (41%) | 0.1 (0%) | 68.6 |

## 5. Biểu đồ

![fps_comparison](figures/fps_comparison.png)

![latency_breakdown_640x480](figures/latency_breakdown_640x480.png)

## 6. Nhận xét

- Ở 640x480 (độ phân giải webcam thường dùng), cấu hình nhanh nhất là **MediaPipe / CUDA / UniGaze-B16 / fp16** với **67.8 FPS** (trung bình 14.7 ms/frame).
- Cùng thiết bị tại 640x480: trên CUDA MediaPipe nhanh hơn FAN **2.0 lần**.
- Ở 640x480 / CUDA, MediaPipe: **Detect khuôn mặt** chiếm ~47% thời gian (8.6 ms/frame).
- Ở 640x480 / CUDA, FAN (face_alignment): **Detect khuôn mặt** chiếm ~75% thời gian (27.5 ms/frame).
- Tăng độ phân giải từ 640x480 lên 1280x720 (CUDA): MediaPipe chậm thêm **1%** và FAN (face_alignment) chậm thêm **32%**.
- VRAM ổn định cao nhất là **2775 MB** (FAN (face_alignment) / CUDA / UniGaze-H14 / fp32, 1280x720), tức ~23% của 11.6 GB VRAM.
- Lưu ý: lần suy luận đầu tiên của FAN (face_alignment) tạo đỉnh VRAM tạm thời **11161 MB** (do `torch.backends.cudnn.benchmark` được bật trong `face_alignment` để autotune), sau đó giảm còn khoảng 2775 MB. GPU dưới ~11 GB có thể bị OOM ở lần chạy đầu.
- Thời gian khởi tạo model khoảng 0.62–4.71 s tùy cấu hình (đã tính load weight lên thiết bị).
- Lúc đo, xung GPU thấp nhất chỉ đạt ~83% mức tối đa (MediaPipe / CUDA / UniGaze-H14 / fp32, tải GPU 80%), nên FPS thực tế có thể cao hơn số trong bảng. Nên tắt bớt ứng dụng nền rồi chạy lại benchmark để có số liệu sạch.
- Khuyến nghị: khi cần độ trễ thấp cho thời gian thực, dùng **MediaPipe FaceMesh + CUDA**. Cả hai backend đều dùng đúng 6 điểm chuẩn hóa của UniGaze (4 góc mắt + 2 cánh mũi), nên chỉ nên chọn FAN khi thực sự cần 68 điểm mốc iBUG đầy đủ.

## 7. Ghi chú phương pháp

- Mỗi cấu hình chạy trong một process riêng để số đo VRAM không bị cộng dồn giữa các cấu hình.
- Có làm nóng (warmup) trước khi đo để loại bỏ chi phí khởi tạo CUDA context và cache.
- VRAM lấy từ `torch.cuda.max_memory_allocated/reserved`, gồm cả lúc load model nhưng **không gồm** CUDA context của driver (thường vài trăm MB).
- Cột **VRAM ổn định** là đỉnh bộ nhớ trong lúc đo (sau warmup); cột **VRAM đỉnh** tính cả lần suy luận đầu tiên (có thể phát sinh autotune của cuDNN).
- MediaPipe luôn chạy trên CPU (delegate CPU), nên cột thiết bị chỉ ảnh hưởng tới UniGaze và bước chuẩn hóa ảnh; FAN chạy trên thiết bị được chọn.
- Cả hai backend dùng đúng 6 điểm chuẩn hóa của UniGaze (4 góc mắt + 2 cánh mũi): MediaPipe FaceMesh lấy index `[33, 133, 362, 263, 75, 290]`, FAN lấy iBUG `[36, 39, 42, 45, 31, 35]`, nên bước chuẩn hóa ảnh giống nhau về hình học.
- Đo trên ảnh tĩnh nên thời gian detect không phụ thuộc chuyển động; khi chạy webcam thật, FPS còn bị giới hạn bởi tốc độ camera và phần hiển thị.
- Bảng **Tải hệ thống lúc đo** là snapshot GPU/CPU ở cuối mỗi cấu hình; số đo sẽ nhiễu nếu lúc chạy còn ứng dụng nền dùng GPU/CPU.
