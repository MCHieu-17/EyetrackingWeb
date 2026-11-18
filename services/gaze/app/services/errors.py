"""Exception dùng chung, không import thư viện nặng (torch/cv2/mediapipe)."""


class InvalidImage(ValueError):
    """Bytes nhận được không decode được thành ảnh."""


class InferenceOverloaded(RuntimeError):
    """Queue suy luận đầy — caller nên trả 503/overloaded thay vì xếp hàng."""


class ModelNotReady(RuntimeError):
    """Pipeline chưa load xong (weights/model lỗi hoặc chưa warmup)."""
