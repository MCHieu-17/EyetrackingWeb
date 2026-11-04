BEGIN;
UPDATE chat_sessions SET context_key = 'reader:course'
WHERE assignment_id IS NULL AND (context_key = '' OR context_key LIKE 'reader:%');
COMMIT;
