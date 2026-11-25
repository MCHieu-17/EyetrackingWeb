"""Gaze service: ước lượng hướng nhìn (FaceLandmarker ONNX + UniGaze) + calibration.

Bố cục giống backend trong repo:
    app/main.py      - FastAPI app, lifespan, /health
    app/settings.py  - đọc biến môi trường
    app/schemas.py   - pydantic request/response
    app/api/         - router HTTP/WebSocket
    app/services/    - logic (pipeline, calibration, session)
"""
