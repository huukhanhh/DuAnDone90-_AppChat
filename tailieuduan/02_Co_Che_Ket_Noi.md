# 02. Cơ Chế Kết Nối (Socket & Threading)

## 1. Nguyên lý hoạt động
Hệ thống sử dụng **TCP Socket** để đảm bảo dữ liệu được truyền đi tin cậy. Dữ liệu trao đổi giữa Client và Server được đóng gói dưới dạng **JSON**, đi kèm với 4 byte header dộ dài (Length-Prefix Framing) để tránh tình trạng dính gói tin (TCP sticky packet).

## 2. Chi tiết thực hiện ở Server

### Mở Socket và Lắng nghe
Server khởi tạo socket, bind vào địa chỉ IP/Port và bắt đầu lắng nghe kết nối tại `server/controllers/server_main.py`.

```python
# File: server/controllers/server_main.py

class ServerController:
    def __init__(self):
        # Tạo socket TCP (IPv4)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Cho phép dùng lại Port ngay lập tức sau khi tắt server
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Gắn socket với Host và Port từ file config
        self.server_socket.bind((SERVER_CONFIG["host"], SERVER_CONFIG["port"]))
        
        # Bắt đầu lắng nghe (hàng đợi 5 kết nối)
        self.server_socket.listen(5)
```

### Chấp nhận kết nối (Threading)
Vòng lặp `while True` liên tục chấp nhận các kết nối mới. Mỗi khi có client mới, một luồng (Thread) mới được tạo ra để xử lý riêng client đó.

```python
# File: server/controllers/server_main.py (Dòng 372-376)

def start(self):
    print(f"Server started on port {SERVER_CONFIG['port']}")
    while True:
        try:
            client_sock, addr = self.server_socket.accept()
            # Tạo luồng riêng biệt để xử lý client này -> hàm handle_client
            threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
        except:
            break
```

## 3. Giao thức truyền tin (Protocol)
Để gửi và nhận dữ liệu chính xác, server và client tuân thủ quy tắc:
1. Gửi 4 byte (big-endian) chứa độ dài của dữ liệu JSON.
2. Gửi toàn bộ dữ liệu JSON.

Ví dụ hàm nhận dữ liệu ở Server:
```python
# File: server/controllers/server_main.py (Dòng 56)

def _recv_all(self, sock, length):
    data = b''
    while len(data) < length:
        # Nhận từng đoạn dữ liệu nhỏ cho đến khi đủ độ dài
        chunk = sock.recv(min(length - len(data), 10485760))
        if not chunk: raise socket.error("Socket broken")
        data += chunk
    return data
```

## 4. Xử lý yêu cầu (Dispatcher)
Trong hàm `handle_client`, server phân tích trường `action` trong JSON để gọi controller tương ứng.

```python
# File: server/controllers/server_main.py (Dòng 92-95)

data = self._recv_all(client_socket, data_length)
message = data.decode('utf-8')
request = json.loads(message)
action = request.get("action") # Xác định Client muốn làm gì (login, chat, v.v.)
```
