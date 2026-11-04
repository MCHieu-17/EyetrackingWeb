# Chatbot UI — 2026-11-04

| Yêu cầu | Thay đổi | Kiểm tra |
|---|---|---|
| Placeholder gọn | “Nhập câu hỏi…”, ô nhập tự tăng chiều cao | Playwright nhập nhiều câu; kiểm tra thuộc tính |
| Panel rộng hơn | clamp(360px, 28vw, 480px), giữ desktop breakpoint | Build và kiểm tra giao diện |
| Bỏ ghi chú dưới ô nhập | Xóa đoạn ghi chú | Kiểm tra mã nguồn |
| Tiếp tục phiên | Không xóa hội thoại khi gửi; reader dùng ngữ cảnh cả khóa; nhớ ID theo tài khoản/khóa/ngữ cảnh | Backend PostgreSQL: ba câu, hai bài, một phiên, sáu tin nhắn; Playwright |
| Markdown, toán, bảng | GFM + remark-math + rehype-katex; citation bỏ qua toán/mã; nhận đủ done mới hiển thị | Unit formatter, sanitizer, pipeline; Playwright bảng và KaTeX |

Migration 030 chuẩn hóa context_key của phiên bài giảng hiện có, không gộp hoặc xóa hội thoại. Các phiên bài tập vẫn dùng khóa ngữ cảnh do backend xác định. API danh sách phiên nhận assignmentId tùy chọn, bổ sung canContinue. Triển khai bằng pipeline migration Docker Compose hiện tại.

Kiểm thử dùng API/provider giả lập và PostgreSQL/pgvector riêng. Đợt này chưa chạy smoke với LLM thật hoặc benchmark chất lượng câu trả lời; không suy diễn kết quả unit/E2E thành bằng chứng chất lượng provider.

Kết quả xác minh: 47 unit test frontend; 24 Playwright test chatbot/reader; 17 backend test với PostgreSQL riêng (gồm test ba câu qua hai bài); 35 test citation/guardrail/pipeline đều đạt. TypeScript và lint các file thay đổi đạt. Build production đạt.

Lưu ý triển khai: migration 030 chưa chạy vào database đang dùng. Cần rebuild qua Docker Compose để pipeline migration áp dụng trước khi chạy backend mới. Đã giữ bộ render câu trả lời ổn định bằng memo để thay đổi AOI không gây vòng lặp dựng lại KaTeX.
