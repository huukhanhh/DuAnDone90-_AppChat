# 07. Xử Lý Đa Phương Tiện (Image/Voice/Video)

## 1. Cơ chế truyền tải
Do giao thức Socket truyền byte, nên các file nhị phân (ảnh, âm thanh, video) được mã hóa thành chuỗi **Base64** trước khi gửi đi trong gói tin JSON.

## 2. Quy trình Gửi (Sender)

1.  **Đọc file**: Đọc nội dung file dưới dạng binary (`rb`).
2.  **Mã hóa**: Convert binary sang chuỗi Base64 (ASCII).
3.  **Đóng gói**: Tạo JSON message.

```python
# Ví dụ logic ở Client (File: client/views/main_view.py)
with open(file_path, "rb") as f:
    binary_data = f.read()
    base64_data = base64.b64encode(binary_data).decode('utf-8')

request = {
    "action": "send_image",
    "image_data": base64_data,
    "filename": "meo.jpg"
}
```

## 3. Quy trình Lưu trữ (Server)
Server nhận chuỗi Base64 và lưu trực tiếp vào Cơ sở dữ liệu (Blob/LongText) hoặc lưu ra file (trong source code hiện tại đang lưu trực tiếp vào Database để đơn giản hóa việc deploy).

```python
# File: server/models/user_model.py (Dòng 120-124)

def save_image_message(self, sender_id, receiver_id, image_data, filename):
    query = """
        INSERT INTO chat_messages (..., is_image, image_data)
        VALUES (..., True, %s)
    """
    self.cursor.execute(query, (..., image_data)) 
    # image_data ở đây là chuỗi Base64 dài
```

## 4. Quy trình Nhận & Hiển thị (Receiver)
1.  Client nhận gói tin JSON chứa chuỗi Base64.
2.  Giải mã Base64 ngược lại thành binary.
3.  Load vào `QPixmap` (ảnh) hoặc lưu ra file tạm để `QMediaPlayer` phát (Voice/Video).

```python
# Logic hiển thị ảnh (File: client/views/main_view.py)
pix = QtGui.QPixmap()
pix.loadFromData(base64.b64decode(self.avatar_base64))
```
