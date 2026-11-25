-- 007_reset_gaze_calibrations.sql
-- Pipeline gaze đổi (FaceLandmarker 478 điểm + tiền xử lý/denormalize theo
-- research + UniGaze ONNX): (pitch, yaw) sinh ra thay đổi hệ quy chiếu nên mọi
-- calibration LinearRegression cũ không còn đúng. Xoá để học viên calibration
-- lại; backend cũng tăng MAPPING_MODEL_VERSION lên v3 nên calibration cũ không
-- thể lọt qua trong lúc deploy.
--
-- learning_sessions.calibration_id là ON DELETE SET NULL; dữ liệu gaze thô
-- (viewport_x/y) và lịch sử học không bị ảnh hưởng.
-- Không thêm bảng/cột; schema_generation giữ nguyên '13'.

DELETE FROM gaze_calibrations;
