-- 026_gaze_raw_and_aoi.sql
--
-- Lưu gaze RAW theo viewport + AOI DOM-anchored để phân tích lại sau này.
--
-- Nguyên tắc:
--   * gaze_raw_samples là nguồn sự thật: toạ độ viewport chuẩn hoá, cho phép
--     < 0 hoặc > 1 khi người dùng nhìn ra ngoài màn hình. Không downsample ở DB;
--     backend downsample theo GAZE_RAW_HZ (mặc định 15Hz).
--   * Viewport lúc lấy mẫu PHẢI bằng viewport lúc calibration. DB có CHECK để
--     chặn dữ liệu sai; API cũng trả 409 viewport_mismatch.
--   * AOI gắn với DOM: frontend đo getBoundingClientRect() và gửi layout snapshot.
--     aoi_layout_rects lưu rect thật theo aoi_code; aoi_definitions chỉ là catalog
--     (code/name/parent/selector), không lưu toạ độ cố định.
--   * gaze_aoi_hits là bảng derived: rebuild từ raw + snapshot rects. Nhờ vậy có
--     thể thêm AOI mới sau khi đã thu dữ liệu mà vẫn map lại được.
--   * Partition theo tháng và KHÔNG xoá partition cũ.
--
-- Idempotent: chạy lại nhiều lần an toàn.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) learning_sessions: viewport + calibration viewport
-- ---------------------------------------------------------------------------
ALTER TABLE learning_sessions
    ADD COLUMN IF NOT EXISTS viewport_width_px INTEGER,
    ADD COLUMN IF NOT EXISTS viewport_height_px INTEGER,
    ADD COLUMN IF NOT EXISTS calibration_width_px INTEGER,
    ADD COLUMN IF NOT EXISTS calibration_height_px INTEGER,
    ADD COLUMN IF NOT EXISTS device_pixel_ratio REAL;

-- ---------------------------------------------------------------------------
-- 2) aoi_definitions: catalog AOI toàn hệ thống
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aoi_definitions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code              VARCHAR(64) NOT NULL,
    name              VARCHAR(100) NOT NULL,
    description       TEXT,
    scope             VARCHAR(16) NOT NULL DEFAULT 'viewport'
                      CHECK (scope IN ('viewport', 'slide')),
    parent_id         UUID REFERENCES aoi_definitions(id) ON DELETE SET NULL,
    selector          VARCHAR(255),
    lesson_content_id UUID REFERENCES lesson_contents(id) ON DELETE CASCADE,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((scope = 'slide') = (lesson_content_id IS NOT NULL))
);

-- AOI toàn hệ thống: mỗi code chỉ có 1 bản active.
CREATE UNIQUE INDEX IF NOT EXISTS ux_aoi_definitions_code_active
    ON aoi_definitions (code) WHERE is_active;

CREATE INDEX IF NOT EXISTS idx_aoi_definitions_parent
    ON aoi_definitions (parent_id);

-- ---------------------------------------------------------------------------
-- 3) aoi_layout_snapshots: layout DOM tại một thời điểm của phiên học
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aoi_layout_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    viewport_width_px   INTEGER NOT NULL,
    viewport_height_px  INTEGER NOT NULL,
    layout_key          VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aoi_layout_snapshots_session
    ON aoi_layout_snapshots (learning_session_id, captured_at);

-- ---------------------------------------------------------------------------
-- 4) aoi_layout_rects: rect thật của từng phần tử [data-aoi]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aoi_layout_rects (
    id          BIGSERIAL PRIMARY KEY,
    snapshot_id UUID NOT NULL REFERENCES aoi_layout_snapshots(id) ON DELETE CASCADE,
    aoi_code    VARCHAR(64) NOT NULL,
    x_min       REAL NOT NULL,
    y_min       REAL NOT NULL,
    x_max       REAL NOT NULL,
    y_max       REAL NOT NULL,
    CHECK (x_min < x_max AND y_min < y_max),
    CHECK (x_min >= 0 AND x_max <= 1 AND y_min >= 0 AND y_max <= 1)
);

CREATE INDEX IF NOT EXISTS idx_aoi_layout_rects_snapshot
    ON aoi_layout_rects (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_aoi_layout_rects_code
    ON aoi_layout_rects (aoi_code);

-- ---------------------------------------------------------------------------
-- 5) gaze_raw_samples: raw viewport gaze, partition theo tháng
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gaze_raw_samples (
    id                    BIGSERIAL,
    learning_session_id   UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    lesson_content_id     UUID REFERENCES lesson_contents(id) ON DELETE SET NULL,
    layout_snapshot_id    UUID REFERENCES aoi_layout_snapshots(id) ON DELETE SET NULL,
    event_time            TIMESTAMPTZ NOT NULL,
    received_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_ts_ms          BIGINT,
    gaze_x                REAL,
    gaze_y                REAL,
    slide_x               REAL,
    slide_y               REAL,
    status                VARCHAR(16) NOT NULL DEFAULT 'ok'
                          CHECK (status IN ('ok', 'no_face', 'error')),
    surface               VARCHAR(16) NOT NULL DEFAULT 'lesson'
                          CHECK (surface IN ('lesson', 'quiz')),
    viewport_width_px     INTEGER NOT NULL,
    viewport_height_px    INTEGER NOT NULL,
    calibration_width_px  INTEGER NOT NULL,
    calibration_height_px INTEGER NOT NULL,
    device_pixel_ratio    REAL NOT NULL,
    layout_key            VARCHAR(64),
    source                VARCHAR(16) NOT NULL DEFAULT 'real'
                          CHECK (source IN ('real', 'simulated')),
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, event_time),
    CHECK (viewport_width_px = calibration_width_px),
    CHECK (viewport_height_px = calibration_height_px),
    CHECK (
        (status = 'ok' AND gaze_x IS NOT NULL AND gaze_y IS NOT NULL)
        OR (status <> 'ok' AND gaze_x IS NULL AND gaze_y IS NULL)
    ),
    CHECK (gaze_x IS NULL OR (gaze_x > -100 AND gaze_x < 100)),
    CHECK (gaze_y IS NULL OR (gaze_y > -100 AND gaze_y < 100))
) PARTITION BY RANGE (event_time);

-- Lưới an toàn cho dữ liệu rơi ngoài các partition tháng đã tạo.
CREATE TABLE IF NOT EXISTS gaze_raw_samples_default
    PARTITION OF gaze_raw_samples DEFAULT;

-- Function idempotent: tạo partition tháng hiện tại + months_ahead tháng tới.
CREATE OR REPLACE FUNCTION create_gaze_raw_partitions(months_ahead INT DEFAULT 12)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    start_date DATE := date_trunc('month', CURRENT_DATE);
    d          DATE;
    part_name  TEXT;
    created    INT := 0;
BEGIN
    FOR i IN 0..months_ahead LOOP
        d         := start_date + make_interval(months => i);
        part_name := 'gaze_raw_samples_' || to_char(d, 'YYYY_MM');
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF gaze_raw_samples
                 FOR VALUES FROM (%L) TO (%L)
                 WITH (fillfactor = 90)',
                part_name, d, d + INTERVAL '1 month'
            );
            created := created + 1;
        END IF;
    END LOOP;
    RETURN created;
END;
$$;

SELECT create_gaze_raw_partitions(12);

CREATE INDEX IF NOT EXISTS idx_gaze_raw_samples_session
    ON gaze_raw_samples (learning_session_id, event_time);
CREATE INDEX IF NOT EXISTS idx_gaze_raw_samples_content
    ON gaze_raw_samples (lesson_content_id, event_time);
CREATE INDEX IF NOT EXISTS idx_gaze_raw_samples_snapshot
    ON gaze_raw_samples (layout_snapshot_id);

-- ---------------------------------------------------------------------------
-- 6) gaze_aoi_hits: sample ↔ AOI (derived, rebuild được)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gaze_aoi_hits (
    id                  BIGSERIAL PRIMARY KEY,
    learning_session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    gaze_sample_id      BIGINT NOT NULL,
    event_time          TIMESTAMPTZ NOT NULL,
    aoi_id              UUID NOT NULL REFERENCES aoi_definitions(id) ON DELETE CASCADE,
    UNIQUE (gaze_sample_id, aoi_id)
);

CREATE INDEX IF NOT EXISTS idx_gaze_aoi_hits_session
    ON gaze_aoi_hits (learning_session_id, event_time);
CREATE INDEX IF NOT EXISTS idx_gaze_aoi_hits_aoi
    ON gaze_aoi_hits (aoi_id, event_time);

COMMIT;
