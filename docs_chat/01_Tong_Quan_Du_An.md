# 01. Tổng Quan Dự Án

## 1. Giới thiệu chung
Dự án được xây dựng theo mô hình **Client-Server** (Khách - Chủ), cho phép nhiều người dùng kết nối cùng lúc để trò chuyện (chat), tạo nhóm và chia sẻ media.

## 2. Công nghệ sử dụng
- **Ngôn ngữ lập trình**: Python
- **Giao diện (Client)**: PySide6 (Qt framework)
- **Giao tiếp mạng**: Thư viện `socket` (TCP/IP)
- **Cơ sở dữ liệu**: MySQL
- **Bảo mật**: `bcrypt` để mã hóa mật khẩu
- **AI Integration**: Google Generative AI (Gemini)
- **Xử lý đa luồng**: `threading` để xử lý nhiều kết nối đồng thời.

## 3. Cấu trúc thư mục

### Server (`server/`)
Chịu trách nhiệm quản lý kết nối, xử lý logic nghiệp vụ và tương tác với cơ sở dữ liệu.
- `main.py`: Điểm khởi chạy của server.
- `controllers/`: Chứa các controller xử lý logic từng phần (Auth, Chat, Group, User).
    - `server_main.py`: File quan trọng nhất, chứa vòng lặp chính (main loop) để lắng nghe và phân phối yêu cầu từ client.
- `models/`: Chứa các class thao tác trực tiếp với Database (ví dụ: `UserModel`).

### Client (`client/`)
Chịu trách nhiệm hiển thị giao diện và gửi yêu cầu đến server.
- `views/`: Các file giao diện (Window login, Main chat, AI chat).
    - `main_view.py`: Giao diện chính của ứng dụng.
- `controllers/`: Xử lý logic phía client (gửi/nhận packet JSON).
- `run_client.py`: Điểm khởi chạy của client.
