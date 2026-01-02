# 03. Xác Thực Người Dùng (Authentication)

## 1. Quy trình Đăng Ký (Register)

Client gửi gói tin với `action: "register"`. Server nhận, hash mật khẩu và lưu vào Database.

### Server Side
- **File xử lý**: `server/controllers/auth_controller.py` gọi xuống `server/models/user_model.py`.
- **Mã hóa**: Sử dụng thư viện `bcrypt` để tạo salt và hash an toàn.

```python
# File: server/models/user_model.py (Dòng 62-74)

def register_user(self, display_name, email, password):
    # 1. Kiểm tra email đã tồn tại chưa
    query = "SELECT email FROM users WHERE email = %s"
    # ...
    
    # 2. Tạo Salt và Hash password
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)

    # 3. Lưu vào DB
    query = "INSERT INTO users (display_name, email, password_hash) VALUES (%s, %s, %s)"
    self.cursor.execute(query, (display_name, email, password_hash.decode('utf-8')))
```

## 2. Quy trình Đăng Nhập (Login)

Client gửi email và password. Server kiểm tra DB và so sánh hash.

### Server Side
- **File xử lý**: `server/controllers/server_main.py` (Dispatcher) -> `auth_controller.py`.

```python
# File: server/models/user_model.py (Dòng 85-98)

def login_user(self, email, password):
    # 1. Lấy thông tin user (bao gồm hash) từ DB
    query = "SELECT id, display_name, password_hash, avatar_data FROM users WHERE email = %s"
    # ...
    
    # 2. So sánh mật khẩu gửi lên với hash trong DB
    if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
        return {"status": "success", "user_id": user_id, ...}
    else:
        return {"status": "error", "message": "Mật khẩu sai"}
```

## 3. Quản lý Phiên (Session)
Sau khi đăng nhập thành công:
1. Server lưu `socket` của client vào từ điển `self.clients` và `self.user_sockets` trong `server_main.py`.
2. Nếu User có tin nhắn offline (tin nhắn gửi tới khi họ ngoại tuyến), server sẽ gửi ngay lập tức sau khi đăng nhập.

```python
# File: server/controllers/server_main.py (Dòng 106-108)

with self.lock:
    self.clients[client_socket] = user_id
    self.user_sockets[user_id] = client_socket
```
