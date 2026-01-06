# Chức Năng Gọi Điện (Call Features)

## Tổng Quan

Ứng dụng hỗ trợ tính năng gọi điện 1-1 giữa hai người dùng, bao gồm:
- **Audio Call** (Gọi thoại) - ✅ Đã hoàn thành
- **Video Call** (Gọi video) - 🔜 Đang phát triển

---

## 1. Audio Call (Gọi Thoại)

### 1.1. Mô Tả Tính Năng

Cho phép hai người dùng thực hiện cuộc gọi thoại real-time qua mạng. Âm thanh được capture từ microphone, truyền qua server, và phát ra loa của người nhận.

### 1.2. Luồng Hoạt Động

```
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│   User A    │        │   Server    │        │   User B    │
│  (Caller)   │        │   (Relay)   │        │  (Receiver) │
└──────┬──────┘        └──────┬──────┘        └──────┬──────┘
       │                      │                      │
       │  1. call_request     │                      │
       │─────────────────────>│  call_request        │
       │                      │─────────────────────>│
       │                      │                      │
       │                      │  2. call_accepted    │
       │  call_accepted       │<─────────────────────│
       │<─────────────────────│                      │
       │                      │                      │
       │ ══════════════════ AUDIO STREAMING ═══════════════════
       │                      │                      │
       │  3. audio_data       │  audio_data          │
       │─────────────────────>│─────────────────────>│ ── Play
       │                      │                      │
       │  audio_data          │  audio_data          │
       │ Play ──<─────────────│<─────────────────────│
       │                      │                      │
       │  4. call_ended       │  call_ended          │
       │─────────────────────>│─────────────────────>│
       │                      │                      │
```

### 1.3. Các Tín Hiệu (Signals)

| Signal Type | Mô Tả | Data |
|-------------|-------|------|
| `call_request` | Yêu cầu gọi | `caller_name`, `caller_avatar` |
| `call_accepted` | Chấp nhận cuộc gọi | - |
| `call_rejected` | Từ chối cuộc gọi | - |
| `call_ended` | Kết thúc cuộc gọi | - |
| `audio_data` | Dữ liệu âm thanh | `audio` (base64) |

### 1.4. Thông Số Kỹ Thuật Audio

| Thông số | Giá trị |
|----------|---------|
| Format | PCM 16-bit |
| Channels | 1 (Mono) |
| Sample Rate | 16,000 Hz |
| Chunk Size | 1024 frames |
| Latency | ~64ms/chunk |

### 1.5. Thư Viện Sử Dụng

- **PyAudio**: Capture microphone và playback audio
- **PySide6 Signal/Slot**: Thread-safe communication

### 1.6. Files Liên Quan

| File | Vai Trò |
|------|---------|
| `client/views/call_dialog.py` | UI cuộc gọi + Audio streaming |
| `client/views/main_view.py` | Xử lý signal gọi + routing audio |
| `server/controllers/server_main.py` | Relay signal giữa users |
| `client/controllers/chat_mixin.py` | Gửi signal qua network |

### 1.7. Class Diagram

```
┌───────────────────────────────────┐
│       ActiveCallDialog            │
├───────────────────────────────────┤
│ - audio: PyAudio                  │
│ - input_stream: Stream (mic)      │
│ - output_stream: Stream (speaker) │
│ - audio_running: bool             │
├───────────────────────────────────┤
│ + start_timer()                   │
│ + start_audio_stream()            │
│ + stop_audio_stream()             │
│ + play_audio_data(bytes)          │
│ - _audio_capture_loop()           │
├───────────────────────────────────┤
│ «signal» hangup_signal            │
│ «signal» audio_data_signal(bytes) │
└───────────────────────────────────┘
```

---

## 2. Video Call (Gọi Video) - Đang Phát Triển

### 2.1. Mô Tả Tính Năng (Dự Kiến)

Cho phép hai người dùng thực hiện cuộc gọi video real-time. Kết hợp cả audio và video streaming.

### 2.2. Kiến Trúc Dự Kiến

```
┌───────────────────────────────────────────────────────────┐
│                     VideoCallDialog                        │
├───────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐               │
│  │  Local Video    │    │  Remote Video   │               │
│  │  (Camera)       │    │  (Peer)         │               │
│  │  ┌───────────┐  │    │  ┌───────────┐  │               │
│  │  │           │  │    │  │           │  │               │
│  │  │    📷     │  │    │  │    👤     │  │               │
│  │  │           │  │    │  │           │  │               │
│  │  └───────────┘  │    │  └───────────┘  │               │
│  └─────────────────┘    └─────────────────┘               │
│                                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │  Mute   │  │ Camera  │  │ Speaker │  │ Hangup  │      │
│  │   🎤    │  │   📹    │  │   🔊    │  │   ❌    │      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
└───────────────────────────────────────────────────────────┘
```

### 2.3. Tín Hiệu Dự Kiến

| Signal Type | Mô Tả |
|-------------|-------|
| `video_call_request` | Yêu cầu gọi video |
| `video_call_accepted` | Chấp nhận |
| `video_data` | Frame video (JPEG base64) |
| `audio_data` | Âm thanh (như audio call) |

### 2.4. Thông Số Kỹ Thuật Dự Kiến

| Thông số | Video | Audio |
|----------|-------|-------|
| Format | JPEG | PCM 16-bit |
| Resolution | 640x480 | - |
| Frame Rate | 15 FPS | - |
| Sample Rate | - | 16,000 Hz |

### 2.5. Thư Viện Dự Kiến

- **OpenCV**: Capture camera và encode frame
- **PyAudio**: Audio streaming (tái sử dụng từ audio call)
- **PySide6**: UI hiển thị video

### 2.6. Các Tính Năng Dự Kiến

- [ ] Hiển thị video local (preview)
- [ ] Hiển thị video remote (peer)
- [ ] Nút tắt/bật camera
- [ ] Nút tắt/bật microphone
- [ ] Nút tắt/bật speaker
- [ ] Picture-in-picture mode

---

## 3. So Sánh Audio Call vs Video Call

| Tính Năng | Audio Call | Video Call |
|-----------|------------|------------|
| Trạng thái | ✅ Hoàn thành | 🔜 Đang phát triển |
| Bandwidth | Thấp (~32 kbps) | Cao (~500 kbps) |
| Latency | ~64ms | ~100-200ms |
| CPU Usage | Thấp | Trung bình |
| Thư viện | PyAudio | OpenCV + PyAudio |

---

## 4. Giao Diện Người Dùng

### 4.1. Nút Gọi Trên Header

Khi chọn một user để chat, header hiển thị 2 nút:
- 📞 **Audio Call**: Bắt đầu cuộc gọi thoại
- 📹 **Video Call**: Bắt đầu cuộc gọi video (sắp có)

### 4.2. Dialog Cuộc Gọi Đến

Khi có cuộc gọi đến, hiển thị dialog với:
- Avatar và tên người gọi
- Nút ✅ Chấp nhận
- Nút ❌ Từ chối

### 4.3. Dialog Đang Gọi

Trong cuộc gọi, hiển thị:
- Avatar và tên người đang gọi
- Timer hiển thị thời lượng cuộc gọi
- Nút ❌ Dập máy

---

## 5. Xử Lý Lỗi

| Tình huống | Xử lý |
|------------|-------|
| User offline | Hiện thông báo "Người dùng không trực tuyến" |
| Cuộc gọi bị từ chối | Hiện thông báo "Người gọi đang bận" |
| Mất kết nối | Tự động đóng dialog cuộc gọi |
| Lỗi microphone | Log lỗi, cuộc gọi vẫn tiếp tục (chỉ một chiều) |
