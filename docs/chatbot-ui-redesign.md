# Chatbot UI — 2026-11-04

| Yêu cầu | Thay đổi |
|---|---|
| Placeholder gọn | “Nhập câu hỏi…”, ô nhập tự tăng chiều cao |
| Panel rộng hơn | clamp(360px, 28vw, 480px), giữ desktop breakpoint |
| Bỏ ghi chú dưới ô nhập | Xóa đoạn ghi chú |
| Tiếp tục phiên | Không xóa hội thoại khi gửi; reader dùng ngữ cảnh cả khóa; nhớ ID theo tài khoản/khóa/ngữ cảnh |
| Markdown, toán, bảng | GFM + remark-math + rehype-katex; citation bỏ qua toán/mã; nhận đủ done mới hiển thị |

Migration 030 chuẩn hóa context_key của phiên bài giảng hiện có, không gộp hoặc xóa hội thoại. Các phiên bài tập vẫn dùng khóa ngữ cảnh do backend xác định. API danh sách phiên nhận assignmentId tùy chọn, bổ sung canContinue. Triển khai bằng pipeline migration Docker Compose hiện tại.

Lưu ý triển khai: migration 030 chưa chạy vào database đang dùng. Cần rebuild qua Docker Compose để pipeline migration áp dụng trước khi chạy backend mới. Đã giữ bộ render câu trả lời ổn định bằng memo để thay đổi AOI không gây vòng lặp dựng lại KaTeX.
