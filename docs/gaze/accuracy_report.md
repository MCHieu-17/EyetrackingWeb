# Báo cáo độ chính xác pipeline eye tracking

> **Nguồn:** báo cáo này được chuyển từ repo nghiên cứu `EyetrackingResearch`
> (commit `f8bf481`) sang `docs/`. Pipeline torch gốc và các công cụ thu/chấm
> (`tools/collect.py`, `tools/evaluate.py`, `benchmark/*.py`) **không** còn trong
> repo này; lệnh `python tools/...` bên dưới chỉ chạy trong repo nghiên cứu đó.
> Dữ liệu ảnh mặt và kết quả thô nằm ở `benchmarks/gaze/testdata/` (gitignored)
> và `benchmarks/gaze/research-results/`.

- Thời điểm chấm: `2026-11-24T19:50:12+07:00`
- Thiết bị: `cuda`
- Độ chính xác số: `fp32, fp16`
- Dữ liệu: `benchmarks/gaze/testdata` (thu bằng `tools/collect.py` của repo nghiên cứu)

## Tóm tắt

- Dữ liệu: **100 target** / 800 frame từ **1 phiên**, tư thế: frontal.
- Giao thức chính: **within (k-fold theo target)**.
- MediaPipe FaceMesh · fp32: L2 trung vị **29.3 px** (CI 95% 25.0–33.8 px), L1 38.6 px, ≈0.59° (quy đổi), jitter 0.77°.
- MediaPipe FaceMesh · fp16: L2 trung vị **29.3 px** (CI 95% 24.8–33.5 px), L1 38.4 px, ≈0.59° (quy đổi), jitter 0.77°.
- FAN (face_alignment) · fp32: L2 trung vị **28.8 px** (CI 95% 24.7–33.0 px), L1 36.5 px, ≈0.59° (quy đổi), jitter 0.84°.
- FAN (face_alignment) · fp16: L2 trung vị **28.7 px** (CI 95% 24.7–32.8 px), L1 36.4 px, ≈0.59° (quy đổi), jitter 0.84°.
- Paired MediaPipe FaceMesh · fp32 vs MediaPipe FaceMesh · fp16: ΔL2 trung vị **-0.01 px** (CI -0.09–0.06) → **tương đương (|ΔL2| < 2 px)**.
- Paired MediaPipe FaceMesh · fp32 vs FAN (face_alignment) · fp32: ΔL2 trung vị **-1.08 px** (CI -4.30–3.98) → **tương đương (|ΔL2| < 2 px)**.
- Paired MediaPipe FaceMesh · fp16 vs FAN (face_alignment) · fp16: ΔL2 trung vị **-0.69 px** (CI -4.42–3.76) → **tương đương (|ΔL2| < 2 px)**.
- Paired FAN (face_alignment) · fp32 vs FAN (face_alignment) · fp16: ΔL2 trung vị **-0.01 px** (CI -0.08–0.07) → **tương đương (|ΔL2| < 2 px)**.
- Nếu 2 detector tương đương trong sai số pixel, chọn theo FPS (xem `benchmark_report.md`).

## 1. Dữ liệu

| Phiên | Tư thế | Tạo lúc | Target | Frame | Màn hình | pipeline_ok | dry-run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `20261124_175802_frontal` | frontal | 2026-11-24 18:01 | 100 | 800 | 1920x1080 | 100% |  |

- `pipeline_ok` = tỉ lệ target mà pipeline (detector dùng lúc thu) xử lý được ngay khi thu dữ liệu, chỉ để tham khảo.
- `benchmarks/gaze/testdata/` là dữ liệu test độc lập: **không** dùng để fit `weights/calibrator.ubj`.

## 2. Cách chấm điểm

- Mỗi target: lấy median `(pitch, yaw)` trên các frame hợp lệ; `std` của các frame là **jitter** trong một fixation.
- Mapping `(pitch, yaw) -> (x/W, y/H)` fit bằng `LinearRegression` giống `calibration.py`, sau đó nhân lại kích thước màn hình của phiên để ra pixel.
- `within`: k-fold theo target **trong từng phiên** (mapping không thấy mẫu đang chấm).
- `cross-session`: leave-one-session-out — fit trên các phiên khác, chấm phiên bị giữ lại. Đây là số trung thực cho tình huống ngày khác / ánh sáng khác.
- `L2/L1` tính bằng pixel, thêm `% chiều rộng` để so được giữa các màn hình khác kích thước.
- `≈ độ` là quy đổi tham khảo từ Jacobian của mapping (không đo khoảng cách mắt–màn hình), không dùng để so sánh chéo giữa các phiên.
- CI 95% bằng bootstrap: resample **theo phiên** (cluster), nếu chỉ có 1 phiên thì resample theo target nên CI hẹp hơn thực tế.
- Đơn vị độc lập là **target**, không phải frame: các frame trong một fixation tương quan mạnh nên không tính là mẫu độc lập.

## 3. Kết quả

### 3.1. within (k-fold theo target)

| Cấu hình | n target | L2 median [CI 95%] | L2 p95 | L1 median | bias dx | bias dy | ≈ độ | jitter | detect fail | gate 80° | L2 (% rộng) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe FaceMesh · fp32 | 100 | 29.3 [25.0–33.8] | 54.4 | 38.6 | 0.0 | -0.3 | 0.59° | 0.77° | 0.0% | 0.0% | 1.5% |
| MediaPipe FaceMesh · fp16 | 100 | 29.3 [24.8–33.5] | 54.0 | 38.4 | 0.0 | -0.3 | 0.59° | 0.77° | 0.0% | 0.0% | 1.5% |
| FAN (face_alignment) · fp32 | 100 | 28.8 [24.7–33.0] | 57.7 | 36.5 | -0.1 | -0.4 | 0.59° | 0.84° | 0.0% | 0.0% | 1.5% |
| FAN (face_alignment) · fp16 | 100 | 28.7 [24.7–32.8] | 57.3 | 36.4 | -0.1 | -0.4 | 0.59° | 0.84° | 0.0% | 0.0% | 1.5% |

### 3.2. Cross-session (leave-one-session-out)

Chưa đủ 2 phiên nên chưa chấm được. Thu thêm phiên khác ngày rồi chạy lại.

### 3.3. Theo từng phiên (within (k-fold theo target))

| Cấu hình | Phiên | n target | L2 median | L2 p95 | L1 median |
| --- | --- | --- | --- | --- | --- |
| MediaPipe FaceMesh · fp32 | `20261124_175802_frontal` | 100 | 29.3 | 54.4 | 38.6 |
| MediaPipe FaceMesh · fp16 | `20261124_175802_frontal` | 100 | 29.3 | 54.0 | 38.4 |
| FAN (face_alignment) · fp32 | `20261124_175802_frontal` | 100 | 28.8 | 57.7 | 36.5 |
| FAN (face_alignment) · fp16 | `20261124_175802_frontal` | 100 | 28.7 | 57.3 | 36.4 |

### 3.4. So sánh paired (within (k-fold theo target))

| Cặp so sánh | n target | ΔL2 median [CI 95%] | ΔL1 median | Δbias dx | Δbias dy | Kết luận |
| --- | --- | --- | --- | --- | --- | --- |
| MediaPipe FaceMesh · fp32 vs MediaPipe FaceMesh · fp16 | 100 | -0.01 [-0.09–0.06] | -0.01 | 0.0 | -0.0 | tương đương (|ΔL2| < 2 px) |
| MediaPipe FaceMesh · fp32 vs FAN (face_alignment) · fp32 | 100 | -1.08 [-4.30–3.98] | 0.22 | 0.1 | 0.1 | tương đương (|ΔL2| < 2 px) |
| MediaPipe FaceMesh · fp16 vs FAN (face_alignment) · fp16 | 100 | -0.69 [-4.42–3.76] | 0.11 | 0.1 | 0.1 | tương đương (|ΔL2| < 2 px) |
| FAN (face_alignment) · fp32 vs FAN (face_alignment) · fp16 | 100 | -0.01 [-0.08–0.07] | -0.00 | 0.0 | -0.0 | tương đương (|ΔL2| < 2 px) |

Δ = cấu hình A trừ cấu hình B trên **cùng target**; ΔL2 âm nghĩa là A lỗi nhỏ hơn. Kết luận dựa trên CI 95% của ΔL2 (bootstrap theo phiên).

## 4. Biểu đồ

![accuracy_cdf](figures/accuracy_cdf.png)

![accuracy_scatter](figures/accuracy_scatter.png)

## 5. Cảnh báo

- Chỉ có 1 phiên: chưa chấm được `cross-session`, còn `within` lạc quan hơn thực tế (cùng phiên, cùng vị trí đầu).

## 6. Cách chạy lại

```bash
# Thu thêm 1 phiên (mỗi lần chạy là 1 phiên mới, chạy bao nhiêu lần cũng được)
python tools/collect.py --targets 100

# Chấm điểm toàn bộ dữ liệu đã thu
python tools/evaluate.py

# So sánh fp16 vs fp32 cho UniGaze (chỉ trên cuda)
python tools/evaluate.py --precisions fp32,fp16

# Xoá cache kết quả pipeline (ví dụ sau khi đổi model/crop_scale)
python tools/evaluate.py --clear-cache
```

- Cache nằm ở `benchmarks/gaze/testdata/.cache/` và tự xoá khi code pipeline thay đổi (`models.py`, `preprocessing.py`, `utils.py`, `tools/evaluate.py`).
- Mỗi target lưu tối đa 8 frame JPEG trong 400 ms cuối của dwell.

