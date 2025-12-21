# 05. Chức Năng Chat Nhóm (Group Chat)

## 1. Mô tả
Hỗ trợ tạo nhóm chat nhiều thành viên. Bất kỳ thành viên nào gửi tin nhắn, Server sẽ broadcast (phát tán) tin nhắn đó đến tất cả các thành viên còn lại trong nhóm.

## 2. Cơ sở dữ liệu
Gồm 3 bảng chính:
- `groups`: Lưu thông tin nhóm (id, name, owner_id).
- `group_members`: Lưu quan hệ 1-n (group_id, user_id).
- `group_messages`: Lưu nội dung chat của nhóm.

## 3. Giao thức và Cơ chế hoạt động (Technical & Protocol)

Mặc dù Chat 1-1 sử dụng kết nối TCP/IP trực tiếp giữa Client-Server (mô hình tập trung), Chat Nhóm trong dự án này **vẫn sử dụng chính giao thức TCP/IP đó** và vận hành theo cơ chế **Server-Side Unicast Relay** (hay còn gọi là Application-Layer Multicasting).

Dưới đây là chi tiết kỹ thuật:

### 3.1. Tại sao không dùng IP Multicast?
- **IP Multicast (UDP)** thường dùng cho streaming hoặc mạng LAN cục bộ, khó triển khai trên Internet diện rộng (ISP thường chặn) và không đảm bảo độ tin cậy (gói tin có thể mất).
- **TCP/IP Relay** đảm bảo tin cậy (tin nhắn chắc chắn đến nơi), dễ triển khai trên hạ tầng mạng hiện có và tận dụng lại ngay kết nối TCP đang mở của Client.

### 3.2. Quy trình xử lý tin nhắn nhóm
Quy trình gửi tin nhắn diễn ra theo các bước sau, hoàn toàn trên lớp ứng dụng (Application Layer):

1.  **Gửi (Client -> Server):**
    Thành viên A gửi một gói tin JSON qua socket TCP đã kết nối của họ đến Server:
    ```json
    { "action": "group_message", "group_id": 1, "message": "Hello Group" }
    ```

2.  **Lưu trữ (Server DB):**
    Server nhận gói tin, lưu nội dung vào bảng `group_messages` trong MySQL để đảm bảo lịch sử chat được bảo toàn.

3.  **Tra cứu (Server Lookup):**
    Server truy vấn bảng `group_members` để lấy danh sách ID của tất cả thành viên trong nhóm `group_id=1`.

4.  **Phân phối (Server -> Clients - Fan-out):**
    Server lặp qua danh sách thành viên. Với mỗi thành viên:
    - Kiểm tra xem họ có đang online không (có trong danh sách `user_sockets` không).
    - Nếu online, Server lấy socket TCP riêng của thành viên đó và gửi gói tin JSON (Unicast).
    
    *Ví dụ: Nếu nhóm có 10 người, Server sẽ thực hiện 10 lần gửi (send) riêng biệt qua 10 socket khác nhau.*

```python
# Minh họa logic (Server-Side)
for member_id in group_members:
    if member_id in self.user_sockets:
        client_sock = self.user_sockets[member_id]
        self.send_to_client(client_sock, message_packet)
```

## 4. Các chức năng chính

### Tạo nhóm
Client gửi action `create_group` kèm danh sách thành viên.
```python
# File: server/models/user_model.py (Dòng 292)
def create_group(self, name, owner_id, member_ids):
    # Insert table groups
    self.cursor.execute("INSERT INTO `groups` ...")
    # Insert table group_members (cho từng user)
    self.cursor.executemany("INSERT INTO group_members ...", values)
```

### Gửi tin nhắn nhóm
Client gửi action `group_message`. Server tìm tất cả thành viên của nhóm và gửi tin nhắn.

```python
# File: server/controllers/server_main.py (Dòng 215-233)

res_data = self.group_ctrl.handle_group_message(sender_id, request)
gid = res_data["group_id"]

# Lấy danh sách ID thành viên
members = self.model.get_group_members(gid)

# Broadcast cho từng người (trừ người gửi nếu muốn, hoặc gửi cả để đồng bộ)
with self.lock:
    for mid in members:
        if mid in self.user_sockets:
            self.send_to_client(self.user_sockets[mid], msg_data)
```

### Thêm thành viên
Action `add_group_member`. Server thêm vào bảng `group_members` và gửi thông báo hệ thống ("A đã thêm B vào nhóm").

```python
# File: server/models/user_model.py (Dòng 314)
# Kiểm tra đã tồn tại chưa trước khi Insert
self.cursor.execute("SELECT 1 FROM group_members WHERE group_id=%s AND user_id=%s", ...)
```

## 5. Thông báo hệ thống (System Message)
Khi có sự kiện (tạo nhóm, thêm người, rời nhóm), hệ thống tự động chèn một dòng tin nhắn đặc biệt (`is_system=True`) vào lịch sử chat để mọi người cùng biết.
