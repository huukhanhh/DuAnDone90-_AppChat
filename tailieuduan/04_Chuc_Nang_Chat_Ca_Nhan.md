# 04. Chức Năng Chat Cá Nhân (1-on-1)

## 1. Mô tả
Cho phép hai người dùng gửi tin nhắn văn bản (text) thời gian thực cho nhau. Nếu người nhận không online, tin nhắn sẽ được lưu vào cơ sở dữ liệu và gửi ngay khi họ đăng nhập.

## 2. Luồng dữ liệu (Data Flow)

1.  **Client A** gửi JSON:
    ```json
    {
        "action": "message",
        "receiver_id": 2,
        "message": "Xin chào!"
    }
    ```
2.  **Server** nhận và xử lý tại `server_main.py` -> `chat_controller.py`.
3.  **Server** lưu tin nhắn vào Database.
4.  **Server** kiểm tra `receiver_id` có trong `user_sockets` (đang online) không.
    -   Nếu có: Gửi JSON đến Client B.
    -   Nếu không: Đánh dấu để gửi sau (Offline Message).

## 3. Chi tiết thực hiện

### Server: Xử lý tin nhắn
```python
# File: server/controllers/server_main.py (Dòng 157-160)

elif action in ["message", "send_image", ...]:
    if client_socket in self.clients:
        sender_id = self.clients[client_socket]
        # Gọi ChatController để lưu DB
        res_data = self.chat_ctrl.handle_message(sender_id, request) 
```

### Server: Lưu Database
```python
# File: server/models/user_model.py (Dòng 108)

def save_message(self, sender_id, receiver_id, message, is_call_log=False):
    query = "INSERT INTO chat_messages (sender_id, receiver_id, message, ...) VALUES ..."
    self.cursor.execute(query, (...))
    self.connection.commit()
```

### Server: Gửi cho người nhận
```python
# File: server/controllers/server_main.py (Dòng 181-186)

with self.lock:
    if receiver_id in self.user_sockets:
        # User đang online -> Gửi ngay
        self.send_to_client(self.user_sockets[receiver_id], msg_data)
    else:
        # User offline -> Lưu vào hàng đợi
        if receiver_id not in self.offline_messages: 
            self.offline_messages[receiver_id] = []
        self.offline_messages[receiver_id].append(msg_data)
```

## 4. Giao diện Client
- **File**: `client/views/main_view.py`.
- Lắng nghe tín hiệu `message_received` từ luồng nhận tin để hiển thị bong bóng chat.
