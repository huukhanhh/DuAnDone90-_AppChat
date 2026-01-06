# Tài Liệu Chi Tiết: Hệ Thống FaceID

## Mục Lục
1. [Tổng Quan](#1-tổng-quan)
2. [Kiến Trúc Hệ Thống](#2-kiến-trúc-hệ-thống)
3. [Các Thành Phần](#3-các-thành-phần)
4. [Luồng Xử Lý Chi Tiết](#4-luồng-xử-lý-chi-tiết)
5. [Cơ Sở Dữ Liệu](#5-cơ-sở-dữ-liệu)
6. [API Reference](#6-api-reference)
7. [Bảo Mật](#7-bảo-mật)

---

## 1. Tổng Quan

### 1.1 FaceID là gì?
FaceID là tính năng xác thực sinh trắc học cho phép người dùng:
- **Đăng ký khuôn mặt** thay vì chỉ dùng mật khẩu
- **Đăng nhập bằng khuôn mặt** - nhanh và tiện lợi
- **Bật/tắt FaceID** theo ý muốn

### 1.2 Công nghệ sử dụng
| Thành phần | Thư viện | Mô tả |
|------------|----------|-------|
| Nhận diện khuôn mặt | DeepFace | Thư viện Python hỗ trợ nhiều model |
| Model embedding | Facenet512 | Tạo vector 512 chiều đại diện khuôn mặt |
| Xử lý ảnh | OpenCV | Đọc camera, xử lý frame |
| Giao diện | PySide6 | Dialog camera preview |
| Multi-threading | QThread | Tránh đóng băng UI khi xử lý |

### 1.3 Nguyên lý hoạt động cơ bản

```
Khuôn mặt → Camera → Frame ảnh → DeepFace → Vector 512 số thực
                                              (embedding)
```

Mỗi khuôn mặt được chuyển thành một vector 512 chiều (512 số thực).
So sánh 2 khuôn mặt = So sánh 2 vector bằng **cosine similarity**.

---

## 2. Kiến Trúc Hệ Thống

### 2.1 Sơ đồ tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │ LoginView   │    │ ProfileDialog   │    │ MainView     │ │
│  │             │    │                 │    │              │ │
│  │ [FaceID     │    │ [Thiết lập]     │    │              │ │
│  │  Login Btn] │    │ [Tắt FaceID]    │    │              │ │
│  └──────┬──────┘    └────────┬────────┘    └──────────────┘ │
│         │                    │                               │
│         ▼                    ▼                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              FaceID Dialog Layer                        │ │
│  │  ┌─────────────────┐    ┌─────────────────┐            │ │
│  │  │ FaceLoginDialog │    │ FaceEnrollDialog│            │ │
│  │  │ (đăng nhập)     │    │ (thiết lập)     │            │ │
│  │  └────────┬────────┘    └────────┬────────┘            │ │
│  └───────────┼──────────────────────┼──────────────────────┘ │
│              │                      │                        │
│              ▼                      ▼                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           FaceEmbeddingProvider (Singleton)             │ │
│  │  - Lazy load DeepFace                                   │ │
│  │  - Camera control                                       │ │
│  │  - Embedding extraction                                 │ │
│  └────────────────────────────┬────────────────────────────┘ │
│                               │                              │
│              ┌────────────────┴────────────────┐             │
│              │        embedding_codec          │             │
│              │  - numpy ↔ bytes ↔ base64       │             │
│              └────────────────┬────────────────┘             │
└───────────────────────────────┼──────────────────────────────┘
                                │ TCP/IP JSON
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                         SERVER                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   server_main.py                        │ │
│  │  Route: FACE_STATUS, FACE_ENROLL, FACE_DISABLE,        │ │
│  │         FACE_LOGIN → FaceAuthController                 │ │
│  └────────────────────────────┬────────────────────────────┘ │
│                               │                              │
│                               ▼                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │               FaceAuthController                        │ │
│  │  - handle_face_status()                                 │ │
│  │  - handle_face_enroll()                                 │ │
│  │  - handle_face_disable()                                │ │
│  │  - handle_face_login()                                  │ │
│  └────────────────────────────┬────────────────────────────┘ │
│                               │                              │
│              ┌────────────────┴────────────────┐             │
│              │     UserFaceAuthModel           │             │
│              │  - Database CRUD operations     │             │
│              └────────────────┬────────────────┘             │
│                               │                              │
│                               ▼                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                     SQLite Database                      │ │
│  │  Table: user_face_auth                                  │ │
│  │  - embedding (BLOB)                                     │ │
│  │  - threshold, model_name, is_enabled                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Các Thành Phần

### 3.1 Client-side

#### 3.1.1 `client/face/face_embedding_provider.py`

**Mục đích:** Cung cấp khả năng trích xuất embedding từ khuôn mặt.

**Class chính:** `FaceEmbeddingProvider`

| Phương thức | Mô tả | Input | Output |
|-------------|-------|-------|--------|
| `is_available()` | Kiểm tra dependencies đã cài đủ chưa | - | `bool` |
| `get_missing_deps()` | Lấy danh sách thư viện thiếu | - | `List[str]` |
| `initialize()` | Tải và khởi tạo model Facenet512 | - | `bool` |
| `get_embedding_from_frame(frame)` | Trích xuất embedding từ 1 frame | BGR frame | `np.ndarray[512]` hoặc `None` |
| `average_embeddings(list)` | Tính trung bình nhiều embeddings | `List[np.ndarray]` | `np.ndarray[512]` |
| `open_camera(index)` | Mở camera | camera index | `cv2.VideoCapture` |
| `frame_to_qimage(frame)` | Chuyển frame sang QImage | BGR frame | `QImage` |

**Ví dụ sử dụng:**
```python
from client.face.face_embedding_provider import get_provider

provider = get_provider()  # Singleton

# Kiểm tra dependencies
if not provider.is_available():
    print(f"Thiếu: {provider.get_missing_deps()}")
    return

# Khởi tạo model (chỉ cần 1 lần)
provider.initialize()

# Mở camera
cap = provider.open_camera(0)

# Đọc frame
ret, frame = cap.read()

# Trích xuất embedding
embedding = provider.get_embedding_from_frame(frame)
# embedding: numpy array shape (512,)

# Giải phóng camera
provider.release_camera(cap)
```

---

#### 3.1.2 `client/ui/face_enroll_dialog.py`

**Mục đích:** Dialog để người dùng thiết lập FaceID.

**Classes:**
- `FaceEnrollWorker(QThread)`: Worker thread xử lý camera
- `FaceEnrollDialog(QDialog)`: Dialog giao diện

**Signals:**
| Signal | Tham số | Khi nào emit |
|--------|---------|--------------|
| `frame_ready` | `QImage` | Mỗi frame camera mới |
| `progress_update` | `(current, total)` | Mỗi embedding thu được |
| `embedding_ready` | `(b64, dim, model, threshold)` | Hoàn thành capture |
| `error` | `str` | Có lỗi xảy ra |

**Luồng hoạt động:**
```
1. Dialog mở → showEvent() → _start_preview()
2. Worker thread bắt đầu → camera preview
3. User nhấn "Bắt đầu" → _on_start_clicked() → worker.start_capture()
4. Worker thu thập 15 frames với embedding
5. Tính trung bình → mã hóa base64 → emit embedding_ready
6. Dialog đóng → caller gửi FACE_ENROLL lên server
```

---

#### 3.1.3 `client/ui/face_login_dialog.py`

**Mục đích:** Dialog để đăng nhập bằng FaceID.

**Tương tự `face_enroll_dialog.py` nhưng:**
- Signal `login_embedding_ready(b64, dim)` thay vì `enrollment_complete`
- Không cần `model_name` và `threshold` (server đã lưu)

---

#### 3.1.4 `common/face/embedding_codec.py`

**Mục đích:** Chuyển đổi embedding giữa các định dạng.

| Hàm | Input | Output | Mô tả |
|-----|-------|--------|-------|
| `embedding_to_bytes(vec)` | `np.ndarray[512]` | `bytes` (2048 bytes) | float32 → little-endian bytes |
| `bytes_to_embedding(b, dim)` | `bytes`, `int` | `np.ndarray[dim]` | bytes → numpy array |
| `embedding_to_b64(vec)` | `np.ndarray[512]` | `str` | numpy → base64 string |
| `b64_to_embedding(s, dim)` | `str`, `int` | `np.ndarray[dim]` | base64 → numpy array |
| `normalize_embedding(vec)` | `np.ndarray` | `np.ndarray` | Chuẩn hóa L2 |

**Tại sao cần base64?**
- JSON không hỗ trợ binary data
- Base64 chuyển bytes thành text an toàn để gửi qua network

**Ví dụ:**
```python
from common.face.embedding_codec import embedding_to_b64, b64_to_embedding

# Có embedding numpy array
embedding = np.random.randn(512).astype(np.float32)

# Chuyển sang base64 để gửi qua JSON
b64_string = embedding_to_b64(embedding)
# b64_string: "AbCdEf123..." (khoảng 2730 ký tự)

# Phục hồi từ base64
restored = b64_to_embedding(b64_string, dim=512)
# restored: numpy array giống embedding
```

---

### 3.2 Server-side

#### 3.2.1 `server/controllers/face_auth_controller.py`

**Mục đích:** Xử lý tất cả request liên quan FaceID.

**Class:** `FaceAuthController`

| Phương thức | Action | Yêu cầu auth | Mô tả |
|-------------|--------|--------------|-------|
| `handle_face_status()` | FACE_STATUS | ✅ Có | Lấy trạng thái FaceID hiện tại |
| `handle_face_enroll()` | FACE_ENROLL | ✅ Có | Đăng ký/cập nhật FaceID |
| `handle_face_disable()` | FACE_DISABLE | ✅ Có | Tắt FaceID |
| `handle_face_login()` | FACE_LOGIN | ❌ Không | Đăng nhập bằng FaceID |

**Rate Limiting:**
- Tối đa 5 lần thất bại FACE_LOGIN
- Khóa 30 giây sau 5 lần thất bại
- Tự động reset sau khi hết thời gian khóa

---

#### 3.2.2 `server/models/user_face_auth_model.py`

**Mục đích:** CRUD operations cho bảng `user_face_auth`.

| Phương thức | Mô tả |
|-------------|-------|
| `get_face_auth_by_user_id(user_id)` | Lấy record theo user_id |
| `get_active_face_auth_by_user_id(user_id)` | Lấy record đang enabled |
| `upsert_face_auth(...)` | Tạo mới hoặc cập nhật |
| `disable_face_auth(user_id)` | Tắt FaceID (is_enabled = 0) |
| `touch_last_used(user_id)` | Cập nhật last_used_at |

---

## 4. Luồng Xử Lý Chi Tiết

### 4.1 Thiết Lập FaceID (Enrollment)

```
┌──────────────────────────────────────────────────────────────┐
│                    LUỒNG THIẾT LẬP FACEID                    │
└──────────────────────────────────────────────────────────────┘

User đang ở MainView
        │
        ▼
[1] Click avatar → Mở ProfileDialog
        │
        ▼
[2] ProfileDialog.showEvent() 
        │
        ▼
[3] Gửi request: {"action": "FACE_STATUS"}
        │
        ▼
[4] Server trả về: {"enabled": false, "has_face": false}
        │
        ▼
[5] UI hiển thị: "⚪ Chưa thiết lập"
        │
        ▼
[6] User click "Thiết lập FaceID"
        │
        ▼
[7] Mở FaceEnrollDialog
        │
        ▼
[8] FaceEnrollWorker.run():
        ├─► Import FaceEmbeddingProvider
        ├─► Kiểm tra dependencies (is_available())
        ├─► Tải model Facenet512 (initialize())
        └─► Mở camera (open_camera(0))
        │
        ▼
[9] Vòng lặp preview:
        while running:
            read frame → emit frame_ready → hiển thị
        │
        ▼
[10] User click "Bắt đầu" → start_capture()
        │
        ▼
[11] Vòng lặp capture (15 lần):
        for i in 0..14:
            read frame
            embedding = get_embedding_from_frame(frame)
            if embedding != None:
                embeddings.append(embedding)
                emit progress_update(i+1, 15)
        │
        ▼
[12] Tính trung bình: average_embeddings(embeddings)
        │
        ▼
[13] Chuẩn hóa L2: normalize_embedding(avg)
        │
        ▼
[14] Mã hóa: embedding_to_b64(normalized)
        │
        ▼
[15] Emit: embedding_ready(b64, 512, "Facenet512", 0.7)
        │
        ▼
[16] ProfileDialog nhận signal → Gửi request:
        {
            "action": "FACE_ENROLL",
            "embedding_b64": "AbCdEf...",
            "embedding_dim": 512,
            "model_name": "Facenet512",
            "threshold": 0.7
        }
        │
        ▼
[17] Server FaceAuthController.handle_face_enroll():
        ├─► Validate fields
        ├─► Decode base64 → bytes
        ├─► Kiểm tra length = 512 * 4 = 2048 bytes
        └─► Upsert vào DB
        │
        ▼
[18] Server trả về: {"type": "FACE_ENROLL_RESULT", "ok": true}
        │
        ▼
[19] ProfileDialog hiển thị: "Thiết lập FaceID thành công!"
        │
        ▼
[20] Refresh status → UI hiển thị: "🟢 Đang bật"
```

---

### 4.2 Đăng Nhập Bằng FaceID

```
┌──────────────────────────────────────────────────────────────┐
│                  LUỒNG ĐĂNG NHẬP FACEID                      │
└──────────────────────────────────────────────────────────────┘

User ở màn hình Login
        │
        ▼
[1] Nhập email: "user@example.com"
        │
        ▼
[2] Click "🔐 Đăng nhập bằng FaceID"
        │
        ▼
[3] LoginView._on_faceid_login_clicked():
        ├─► Validate email không rỗng
        └─► Mở FaceLoginDialog
        │
        ▼
[4] FaceLoginDialog: tương tự FaceEnrollDialog
        ├─► Mở camera
        ├─► Preview
        └─► User click "Quét khuôn mặt"
        │
        ▼
[5] Thu thập 15 embeddings → trung bình → base64
        │
        ▼
[6] Emit: login_embedding_ready(b64, 512)
        │
        ▼
[7] LoginView._on_face_embedding_ready():
        ├─► Đóng dialog
        └─► Gọi _do_face_login()
        │
        ▼
[8] _do_face_login():
        ├─► Tạo socket mới
        ├─► Connect server
        └─► Tạo Controller
        │
        ▼
[9] Gửi request:
        {
            "action": "FACE_LOGIN",
            "email": "user@example.com",
            "embedding_b64": "XyZ789...",
            "embedding_dim": 512
        }
        │
        ▼
[10] Server FaceAuthController.handle_face_login():
         │
         ▼
    [10a] Kiểm tra rate limit
         │ LOCKED? → return {"reason": "LOCKED"}
         ▼
    [10b] Tìm user theo email
         │ Không tìm thấy? → return {"reason": "NOT_FOUND"}
         ▼
    [10c] Lấy face record từ DB
         │ Không có/tắt? → return {"reason": "NOT_ENABLED"}
         ▼
    [10d] Kiểm tra dimension khớp
         │ Không khớp? → return {"reason": "DIM_MISMATCH"}
         ▼
    [10e] Giải mã embeddings:
         │   vec_in = b64_to_embedding(request)
         │   vec_db = bytes_to_embedding(db_record)
         ▼
    [10f] Chuẩn hóa L2 cả 2 vector
         │
         ▼
    [10g] Tính cosine similarity:
         │   similarity = vec_in · vec_db
         │   (tích vô hướng của 2 vector đã chuẩn hóa)
         ▼
    [10h] So sánh với threshold:
         │   threshold = 0.7 (từ DB)
         │   if similarity < threshold:
         │       → return {"reason": "NOT_MATCH"}
         ▼
    [10i] THÀNH CÔNG:
         │   - Cập nhật last_used_at
         │   - Xóa failure counter
         │   - Return giống password login
         │
        ▼
[11] Server trả về:
        {
            "status": "success",
            "user_id": 10,
            "display_name": "Nguyen Van A",
            "avatar": "base64...",
            "is_invisible": false
        }
        │
        ▼
[12] LoginView._handle_login_success():
        ├─► Lưu user_id vào controller
        └─► app.show_main(controller, user_id, display_name)
        │
        ▼
[13] Mở MainView → Đăng nhập thành công!
```

---

## 5. Cơ Sở Dữ Liệu

### 5.1 Bảng `user_face_auth`

```sql
CREATE TABLE user_face_auth (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER UNIQUE NOT NULL,     -- FK đến users.id
    embedding   BLOB NOT NULL,                -- 2048 bytes (512 * 4)
    embedding_dim INTEGER NOT NULL,           -- 512
    model_name  TEXT NOT NULL,                -- "Facenet512"
    threshold   REAL NOT NULL DEFAULT 0.7,    -- Ngưỡng similarity
    is_enabled  INTEGER NOT NULL DEFAULT 1,   -- 0 = tắt, 1 = bật
    created_at  TEXT NOT NULL,                -- Timestamp tạo
    updated_at  TEXT NOT NULL,                -- Timestamp cập nhật
    last_used_at TEXT                         -- Lần dùng cuối
);
```

### 5.2 Ví dụ dữ liệu

| id | user_id | embedding | embedding_dim | model_name | threshold | is_enabled |
|----|---------|-----------|---------------|------------|-----------|------------|
| 1  | 10      | [BLOB]    | 512           | Facenet512 | 0.7       | 1          |
| 2  | 15      | [BLOB]    | 512           | Facenet512 | 0.7       | 0          |

- User 10: FaceID đang bật
- User 15: FaceID đã tắt (vẫn giữ embedding)

---

## 6. API Reference

### 6.1 Các Request/Response

#### FACE_STATUS
```json
// Request (cần đăng nhập trước)
{"action": "FACE_STATUS"}

// Response - Chưa thiết lập
{"type": "FACE_STATUS_RESULT", "ok": true, "enabled": false, "has_face": false}

// Response - Đang bật
{"type": "FACE_STATUS_RESULT", "ok": true, "enabled": true, "has_face": true, 
 "model_name": "Facenet512", "updated_at": "2024-01-05 15:30:00"}
```

#### FACE_ENROLL
```json
// Request (cần đăng nhập trước)
{
    "action": "FACE_ENROLL",
    "embedding_b64": "base64_string...",
    "embedding_dim": 512,
    "model_name": "Facenet512",
    "threshold": 0.7
}

// Response thành công
{"type": "FACE_ENROLL_RESULT", "ok": true}

// Response thất bại
{"type": "FACE_ENROLL_RESULT", "ok": false, "reason": "BAD_REQUEST"}
```

#### FACE_DISABLE
```json
// Request (cần đăng nhập trước)
{"action": "FACE_DISABLE"}

// Response
{"type": "FACE_DISABLE_RESULT", "ok": true}
```

#### FACE_LOGIN
```json
// Request (KHÔNG cần đăng nhập trước)
{
    "action": "FACE_LOGIN",
    "email": "user@example.com",
    "embedding_b64": "base64_string...",
    "embedding_dim": 512
}

// Response thành công (giống password login)
{
    "status": "success",
    "user_id": 10,
    "display_name": "Nguyen Van A",
    "avatar": "base64...",
    "is_invisible": false,
    "last_active_at": null
}

// Response thất bại
{
    "status": "error",
    "action": "FACE_LOGIN_RESULT",
    "ok": false,
    "reason": "NOT_MATCH"  // hoặc NOT_FOUND, NOT_ENABLED, DIM_MISMATCH, LOCKED
}
```

---

## 7. Bảo Mật

### 7.1 Rate Limiting
- **5 lần thất bại** → Khóa socket 30 giây
- Tránh brute-force attack

### 7.2 Embedding Storage
- Embedding được lưu dạng **bytes thô** (không phải ảnh)
- Không thể khôi phục lại hình ảnh khuôn mặt từ embedding
- Embedding chỉ dùng để so sánh

### 7.3 Threshold
- Mặc định 0.7 (70% similarity)
- Có thể điều chỉnh theo nhu cầu
- Threshold cao hơn = bảo mật hơn nhưng khó nhận diện hơn

### 7.4 Lưu ý
- Face embedding là **one-way function** - không thể khôi phục ảnh gốc
- Nhưng vẫn là dữ liệu sinh trắc học nhạy cảm
- Cần bảo vệ database và truyền tải qua kết nối an toàn
