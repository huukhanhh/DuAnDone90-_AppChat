# 06. Chức Năng Chat AI (Gemini Integration)

## 1. Tổng quan
Dự án tích hợp Google Generative AI (Gemini) để tạo một trợ lý ảo thông minh. Chatbot này chạy hoàn toàn ở phía **Client**, nghĩa là Client gọi trực tiếp API của Google chứ không thông qua Server chat của ta.

## 2. Cấu hình
- **File**: `config/config.py` chứa `GEMINI_API_KEY`.
- **Thư viện**: `google.generativeai`.

## 3. Triển khai code

### Khởi tạo AI (Client Side)
Tại `client/views/ai_chat_view.py`, class `AIChatView`:

```python
# File: client/views/ai_chat_view.py (Dòng 27-37)

def init_ai(self):
    # Cấu hình API Key
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Khởi tạo model (ví dụ: gemini-2.5-flash)
    self.model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Bắt đầu session chat (lưu ngữ cảnh lịch sử)
    self.chat_session = self.model.start_chat(history=[])
```

### Gửi và Nhận phản hồi
Sử dụng Threading để không làm đơ giao diện khi chờ API phản hồi.

```python
# File: client/views/ai_chat_view.py (Dòng 252-255)

def _generate_response(self, text):
    try:
        # Gửi tin nhắn đến Google
        response = self.chat_session.send_message(text)
        
        # Cập nhật UI (phải dùng invokeMethod để thread an toàn)
        QtCore.QMetaObject.invokeMethod(self, "display_ai_response", ..., response.text)
    except Exception as e:
        # Xử lý lỗi (ví dụ: Quota Exceeded)
        pass
```

## 4. Giao diện (UI)
- Sử dụng `QTextEdit` để hiển thị HTML.
- Hỗ trợ Markdown rendering (thư viện `markdown`) để hiển thị đẹp mắt các phản hồi của AI (in đậm, danh sách, v.v.).
- Có hiệu ứng "Typing..." (đang nhập) để tăng trải nghiệm người dùng.
