# client/ui/camera_capture_dialog.py
"""
Dialog chụp ảnh từ camera để gửi trong chat.

Cho phép người dùng:
1. Xem preview camera realtime
2. Chụp ảnh
3. Chụp lại nếu không hài lòng
4. Xác nhận và gửi ảnh

Camera chạy trong worker thread để không block UI.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import base64


class CameraWorker(QtCore.QThread):
    """
    Worker thread để xử lý camera.
    
    Chạy trong thread riêng để không block UI chính.
    """
    
    # Signals
    frame_ready = QtCore.Signal(object)      # QImage để hiển thị preview
    photo_captured = QtCore.Signal(str)      # Base64 encoded image
    error = QtCore.Signal(str)               # Thông báo lỗi
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._capture_requested = False
        self._cap = None
    
    def stop(self):
        """Dừng worker thread."""
        self._running = False
    
    def request_capture(self):
        """Yêu cầu chụp ảnh."""
        self._capture_requested = True
    
    def run(self):
        """Vòng lặp chính của thread."""
        try:
            import cv2
        except ImportError:
            self.error.emit("Thiếu thư viện OpenCV. Cần cài: pip install opencv-python")
            return
        
        # Mở camera
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            self.error.emit("Không thể mở camera. Vui lòng kiểm tra kết nối camera.")
            return
        
        self._running = True
        
        try:
            while self._running:
                ret, frame = self._cap.read()
                if not ret:
                    continue
                
                # Lật ngang để có hiệu ứng gương (mirror)
                frame = cv2.flip(frame, 1)
                
                # Kiểm tra yêu cầu chụp ảnh
                if self._capture_requested:
                    self._capture_requested = False
                    # Encode frame thành JPEG rồi base64
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    b64_data = base64.b64encode(buffer).decode('utf-8')
                    self.photo_captured.emit(b64_data)
                    continue
                
                # Chuyển BGR sang RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                
                # Tạo QImage
                qimg = QtGui.QImage(
                    frame_rgb.data, w, h, bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888
                )
                self.frame_ready.emit(qimg.copy())
                
                # Delay nhỏ (~30 fps)
                self.msleep(33)
                
        except Exception as e:
            self.error.emit(f"Lỗi camera: {e}")
        finally:
            if self._cap is not None:
                self._cap.release()
                self._cap = None


class CameraCaptureDialog(QtWidgets.QDialog):
    """
    Dialog modal để chụp ảnh từ camera.
    
    Cách sử dụng:
        dialog = CameraCaptureDialog(parent)
        dialog.photo_ready.connect(on_photo_ready)
        dialog.exec()
    """
    
    # Signal phát ra khi user xác nhận gửi ảnh
    photo_ready = QtCore.Signal(str)  # Base64 encoded image
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chụp ảnh")
        self.setModal(True)
        self.setMinimumSize(500, 480)
        self.resize(520, 500)
        
        self._worker = None
        self._captured_image = None  # Lưu ảnh đã chụp (base64)
        self._is_preview_mode = True  # True = đang preview, False = đã chụp
        self._setup_ui()
    
    def _setup_ui(self):
        """Xây dựng các thành phần UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Tiêu đề
        title = QtWidgets.QLabel("📷 Chụp ảnh")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a73e8;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Hướng dẫn
        self.instructions = QtWidgets.QLabel(
            "Nhìn vào camera và nhấn nút Chụp để chụp ảnh."
        )
        self.instructions.setStyleSheet("font-size: 12px; color: #666;")
        self.instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.instructions)
        
        # Khung preview camera
        preview_frame = QtWidgets.QFrame()
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 10px;
            }
        """)
        preview_layout = QtWidgets.QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        
        # Label hiển thị hình ảnh camera
        self.preview_label = QtWidgets.QLabel("Đang khởi động camera...")
        self.preview_label.setFixedSize(420, 315)
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: white; font-size: 14px;")
        preview_layout.addWidget(self.preview_label, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(preview_frame)
        
        # Các nút bấm
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(15)
        
        # Nút Chụp
        self.btn_capture = QtWidgets.QPushButton("📷 Chụp")
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 30px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.btn_capture.clicked.connect(self._on_capture_clicked)
        
        # Nút Chụp lại (ẩn ban đầu)
        self.btn_retake = QtWidgets.QPushButton("🔄 Chụp lại")
        self.btn_retake.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                font-size: 14px;
                padding: 10px 25px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_retake.clicked.connect(self._on_retake_clicked)
        self.btn_retake.hide()
        
        # Nút Gửi (ẩn ban đầu)
        self.btn_send = QtWidgets.QPushButton("✓ Gửi")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 30px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        self.btn_send.clicked.connect(self._on_send_clicked)
        self.btn_send.hide()
        
        # Nút Hủy
        self.btn_cancel = QtWidgets.QPushButton("Hủy")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                font-size: 14px;
                padding: 10px 30px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_capture)
        btn_layout.addWidget(self.btn_retake)
        btn_layout.addWidget(self.btn_send)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def showEvent(self, event):
        """Được gọi khi dialog hiển thị - bắt đầu camera preview."""
        super().showEvent(event)
        self._start_camera()
    
    def closeEvent(self, event):
        """Được gọi khi dialog đóng - dọn dẹp resources."""
        self._stop_worker()
        super().closeEvent(event)
    
    def _start_camera(self):
        """Khởi động worker để preview camera."""
        self._stop_worker()
        
        self._worker = CameraWorker()
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.photo_captured.connect(self._on_photo_captured)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _stop_worker(self):
        """Dừng và dọn dẹp worker thread."""
        if self._worker is not None:
            self._worker.stop()
            if not self._worker.wait(3000):
                print("[CameraCaptureDialog] Cảnh báo: Worker thread không dừng kịp thời")
            self._worker = None
    
    @QtCore.Slot(object)
    def _on_frame_ready(self, qimg):
        """Cập nhật preview với frame mới."""
        if qimg is not None and self._is_preview_mode:
            pixmap = QtGui.QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self.preview_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
    
    @QtCore.Slot(str)
    def _on_photo_captured(self, b64_data):
        """Xử lý khi đã chụp ảnh."""
        self._captured_image = b64_data
        self._is_preview_mode = False
        
        # Hiển thị ảnh đã chụp
        img_data = base64.b64decode(b64_data)
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(img_data)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)
        
        # Cập nhật UI
        self.instructions.setText("Ảnh đã chụp! Nhấn Gửi để gửi hoặc Chụp lại.")
        self.btn_capture.hide()
        self.btn_retake.show()
        self.btn_send.show()
    
    @QtCore.Slot(str)
    def _on_error(self, message):
        """Xử lý lỗi từ worker."""
        self.preview_label.setText("❌ Lỗi")
        self.btn_capture.setEnabled(False)
        
        QtWidgets.QMessageBox.critical(
            self,
            "Lỗi Camera",
            message
        )
        self.reject()
    
    def _on_capture_clicked(self):
        """Xử lý khi nhấn nút Chụp."""
        if self._worker is not None:
            self._worker.request_capture()
    
    def _on_retake_clicked(self):
        """Xử lý khi nhấn nút Chụp lại."""
        self._captured_image = None
        self._is_preview_mode = True
        
        # Reset UI
        self.instructions.setText("Nhìn vào camera và nhấn nút Chụp để chụp ảnh.")
        self.btn_capture.show()
        self.btn_retake.hide()
        self.btn_send.hide()
    
    def _on_send_clicked(self):
        """Xử lý khi nhấn nút Gửi."""
        if self._captured_image:
            self._stop_worker()
            self.photo_ready.emit(self._captured_image)
            self.accept()
    
    def _on_cancel_clicked(self):
        """Xử lý khi nhấn nút Hủy."""
        self._stop_worker()
        self.reject()
