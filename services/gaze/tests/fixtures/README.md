# Gaze test fixtures

`face_sample.jpg` — ảnh chân dung CC0 từ Wikimedia Commons:
<https://commons.wikimedia.org/wiki/File:Face_portrait_(Unsplash).jpg>
(tải qua `Special:Redirect/file` với width=640).

Dùng duy nhất cho smoke test `test_model_smoke.py`: kiểm tra pipeline
landmarker ONNX + UniGaze thật chạy được trên một ảnh mặt. Không dùng cho benchmark
chất lượng/accuracy.

`face_sample_landmarks.npz` — 478 điểm (pixel, `points`) của MediaPipe
FaceLandmarker 0.10.21 (IMAGE, num_faces=1) trên `face_sample.jpg`, kèm `size`
(w, h). Chỉ chứa toạ độ, không có ảnh. Là chuẩn so khớp cho landmarker ONNX
(`tests/smoke/test_landmarker_smoke.py`). Sinh lại bằng image `export`.
