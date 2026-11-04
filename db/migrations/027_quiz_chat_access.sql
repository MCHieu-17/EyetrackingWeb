BEGIN;
ALTER TABLE quiz_assignments ADD COLUMN IF NOT EXISTS allow_chatbot BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS context_key TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_quiz_attempt_sessions_student ON quiz_attempt_sessions(student_id);
COMMIT;
