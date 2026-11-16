-- =============================================================================
-- 002_email_otp.sql — Đăng nhập sinh viên bằng email trường + OTP.
--
-- Thay Microsoft OAuth (oauth_accounts) bằng OTP gửi qua SMTP:
--   * users.email_verified_at: lần xác thực email gần nhất.
--   * email_otps: challenge OTP đã băm HMAC, mỗi email chỉ có một challenge
--     đang hoạt động (consumed_at/invalidated_at đều NULL).
--   * Bỏ oauth_accounts vì không còn liên kết Microsoft 365.
--   * Nâng schema_generation 12 -> 13 (backend fail-fast nếu lệch).
--
-- Chỉ dùng IF EXISTS/IF NOT EXISTS để chạy lại an toàn trên DB đã áp.
-- =============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS email_otps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    code_hash       VARCHAR(128) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    attempts        SMALLINT NOT NULL DEFAULT 0
                    CONSTRAINT email_otps_attempts_check
                    CHECK (attempts >= 0),
    max_attempts    SMALLINT NOT NULL DEFAULT 5
                    CONSTRAINT email_otps_max_attempts_check
                    CHECK (max_attempts > 0),
    consumed_at     TIMESTAMPTZ,
    invalidated_at  TIMESTAMPTZ,
    requested_ip    INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tra cứu challenge mới nhất của một email (cooldown/rate-limit).
CREATE INDEX IF NOT EXISTS idx_email_otps_email_created
    ON email_otps (email, created_at DESC);

-- Dọn dẹp row hết hạn theo created_at bởi maintenance.
CREATE INDEX IF NOT EXISTS idx_email_otps_created_at
    ON email_otps (created_at);

-- Một challenge đang hoạt động cho mỗi email; challenge cũ phải consumed
-- hoặc invalidated trước khi phát hành challenge mới.
CREATE UNIQUE INDEX IF NOT EXISTS ux_email_otps_active_email
    ON email_otps (email)
    WHERE consumed_at IS NULL AND invalidated_at IS NULL;

DROP TABLE IF EXISTS oauth_accounts;

UPDATE app_metadata
   SET value = '13',
       updated_at = now()
 WHERE key = 'schema_generation';
