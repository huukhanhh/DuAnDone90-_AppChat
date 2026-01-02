# 08. Cấu Trúc Dữ Liệu (Database Models)

## 1. Thiết kế chung
Database sử dụng MySQL với các bảng có quan hệ chặt chẽ.

## 2. Chi tiết các bảng (Tables)

### Bảng `users`
Lưu thông tin người dùng.
- `id` (INT, PK, AI): Mã người dùng.
- `display_name` (VARCHAR): Tên hiển thị.
- `email` (VARCHAR): Email đăng nhập (Unique).
- `password_hash` (VARCHAR): Mật khẩu đã mã hóa.
- `avatar_data` (LONGTEXT): Ảnh đại diện (Base64).

### Bảng `chat_messages` (Chat 1-1)
Lưu tin nhắn cá nhân.
- `id` (INT, PK, AI)
- `sender_id` (INT, FK -> users.id)
- `receiver_id` (INT, FK -> users.id)
- `message` (TEXT): Nội dung tin nhắn (hoặc tên file nếu là media).
- `timestamp` (DATETIME): Thời gian gửi.
- `is_image`, `is_voice`, `is_video`, `is_call_log` (BOOLEAN): Cờ đánh dấu loại tin nhắn.
- `image_data`, `voice_data`, `video_data` (LONGTEXT): Dữ liệu nhị phân (Base64).

### Bảng `groups`
Lưu thông tin nhóm chat.
- `id` (INT, PK, AI)
- `name` (VARCHAR): Tên nhóm.
- `owner_id` (INT, FK -> users.id): Người tạo nhóm (Trưởng nhóm).
- `avatar_data` (LONGTEXT): Ảnh nhóm.

### Bảng `group_members`
Lưu thành viên trong nhóm (Quan hệ User - Group).
- `group_id` (INT, FK -> groups.id)
- `user_id` (INT, FK -> users.id)
- *Composite Primary Key (group_id, user_id)*

### Bảng `group_messages`
Lưu tin nhắn trong nhóm.
- `id` (INT, PK, AI)
- `group_id` (INT, FK -> groups.id)
- `sender_id` (INT, FK -> users.id): Người gửi (Null nếu là tin hệ thống).
- `message`, `timestamp`, `is_image`... : Tương tự bảng `chat_messages`.
- `is_system` (BOOLEAN): Đánh dấu tin nhắn hệ thống (VD: "A đã thêm B").
