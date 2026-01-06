# client/ui/face_login_dialog.py
"""
Dialog đăng nhập FaceID với preview camera và xử lý bằng QThread.

Dialog này cho phép người dùng đăng nhập bằng FaceID:
1. Mở camera để preview khuôn mặt
2. Người dùng nhấn nút để bắt đầu quét
3. Chụp nhiều frame và trích xuất embedding
4. Tính trung bình embedding và gửi về cho caller

Camera capture và embedding extraction chạy trong worker thread
để tránh đóng băng UI.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional, List


class FaceLoginWorker(QtCore.QThread):
    """
    Worker thread để chụp camera và trích xuất embedding cho đăng nhập.
    Tương tự FaceEnrollWorker nhưng thiết kế cho flow đăng nhập.
    """
    
    # Signals
    frame_ready = QtCore.Signal(object)      # QImage để hiển thị preview
    progress_update = QtCore.Signal(int, int)  # (số lượng hiện tại, tổng cần)
    embedding_ready = QtCore.Signal(str, int)  # (embedding_b64, embedding_dim)
    error = QtCore.Signal(str)  # Thông báo lỗi
    finished_capture = QtCore.Signal(bool)  # Thành công/thất bại
    
    def __init__(self, num_frames: int = 15, parent=None):
        """
        Khởi tạo worker.
        
        Args:
            num_frames: Số lượng frame cần chụp (mặc định 15)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.num_frames = num_frames
        self._running = False  # Kiểm soát vòng lặp chính
        self._capturing = False  # Đang capture hay chỉ preview
        self._provider = None  # FaceEmbeddingProvider
        self._cap = None  # OpenCV VideoCapture
    
    def stop(self):
        """Dừng worker thread an toàn."""
        self._running = False
        self._capturing = False
    
    def start_capture(self):
        """Bắt đầu chế độ capture frames."""
        self._capturing = True
    
    def run(self):
        """
        Vòng lặp chính của thread.
        
        Flow:
        1. Import lazy và kiểm tra dependencies
        2. Khởi tạo model nhận diện
        3. Mở camera
        4. Vòng lặp: đọc frame -> hiển thị preview
        5. Khi capture: trích xuất embedding
        6. Khi đủ: tính trung bình và gửi kết quả
        """
        # Import lazy để tránh lỗi nếu thiếu dependencies
        try:
            from client.face.face_embedding_provider import get_provider
        except ImportError as e:
            self.error.emit(f"Lỗi import: {e}")
            return
        
        self._provider = get_provider()
        
        # Kiểm tra dependencies đã cài đủ chưa
        if not self._provider.is_available():
            missing = self._provider.get_missing_deps()
            cmd = self._provider.get_install_command()
            self.error.emit(f"Thiếu thư viện: {', '.join(missing)}\n\nCần cài: {cmd}")
            return
        
        # Khởi tạo model (có thể tải model lần đầu)
        if not self._provider.initialize():
            self.error.emit("Không thể khởi tạo model nhận diện khuôn mặt.")
            return
        
        # Mở camera
        self._cap = self._provider.open_camera(0)
        if self._cap is None:
            self.error.emit("Không thể mở camera. Vui lòng kiểm tra kết nối camera.")
            return
        
        self._running = True
        embeddings: List = []  # Thu thập embeddings
        
        try:
            while self._running:
                # Đọc frame từ camera
                ret, frame = self._cap.read()
                if not ret:
                    continue
                
                # Lật ngang để có hiệu ứng gương
                import cv2
                frame = cv2.flip(frame, 1)
                
                # Chuyển sang QImage để hiển thị preview
                qimg = self._provider.frame_to_qimage(frame)
                if qimg:
                    self.frame_ready.emit(qimg)
                
                # Chế độ capture - thu thập embeddings
                if self._capturing:
                    embedding = self._provider.get_embedding_from_frame(frame)
                    if embedding is not None:
                        embeddings.append(embedding)
                        self.progress_update.emit(len(embeddings), self.num_frames)
                        
                        # Kiểm tra đã đủ số lượng chưa
                        if len(embeddings) >= self.num_frames:
                            self._capturing = False
                            self._running = False
                            
                            # Tính trung bình và chuẩn hóa
                            avg_embedding = self._provider.average_embeddings(embeddings)
                            if avg_embedding is None:
                                self.error.emit("Không thể tính embedding trung bình.")
                                self.finished_capture.emit(False)
                                return
                            
                            # Mã hóa sang base64
                            try:
                                from common.face.embedding_codec import embedding_to_b64
                                b64 = embedding_to_b64(avg_embedding)
                                
                                self.embedding_ready.emit(
                                    b64,
                                    self._provider.get_embedding_dim()
                                )
                                self.finished_capture.emit(True)
                            except Exception as e:
                                self.error.emit(f"Lỗi mã hóa embedding: {e}")
                                self.finished_capture.emit(False)
                            return
                
                # Delay nhỏ để giảm CPU usage (~30 fps)
                self.msleep(33)
                
        except Exception as e:
            self.error.emit(f"Lỗi camera: {e}")
            self.finished_capture.emit(False)
        finally:
            # Luôn giải phóng camera
            self._provider.release_camera(self._cap)
            self._cap = None


class FaceLoginDialog(QtWidgets.QDialog):
    """
    Dialog modal để đăng nhập bằng FaceID.
    
    Tính năng:
    - Hiển thị preview camera realtime
    - Hiển thị tiến độ quét (x/15)
    - Nút Quét/Hủy
    - Xử lý trong background thread
    
    Cách sử dụng:
        dialog = FaceLoginDialog(parent)
        dialog.login_embedding_ready.connect(on_embedding)
        dialog.exec()
    """
    
    # Signal phát ra khi có embedding để đăng nhập
    # Tham số: (embedding_b64, embedding_dim)
    login_embedding_ready = QtCore.Signal(str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Đăng nhập FaceID")
        self.setModal(True)
        self.setMinimumSize(500, 450)
        self.resize(520, 480)
        
        self._worker: Optional[FaceLoginWorker] = None
        self._pending_embedding: Optional[tuple] = None  # Lưu kết quả chờ xử lý
        self._setup_ui()
    
    def _setup_ui(self):
        """Xây dựng các thành phần UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Tiêu đề
        title = QtWidgets.QLabel("🔐 Đăng nhập bằng FaceID")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a73e8;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Hướng dẫn
        instructions = QtWidgets.QLabel(
            "Nhìn thẳng vào camera để xác thực khuôn mặt.\n"
            "Đảm bảo ánh sáng đầy đủ để nhận diện tốt hơn."
        )
        instructions.setStyleSheet("font-size: 12px; color: #666;")
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
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
        self.preview_label.setFixedSize(400, 300)
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: white; font-size: 14px;")
        preview_layout.addWidget(self.preview_label, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(preview_frame)
        
        # Label hiển thị tiến độ
        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.setStyleSheet("font-size: 14px; color: #1a73e8; font-weight: bold;")
        self.progress_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        
        # Các nút bấm
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.btn_start = QtWidgets.QPushButton("🎯 Quét khuôn mặt")
        self.btn_start.setStyleSheet("""
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
        self.btn_start.clicked.connect(self._on_start_clicked)
        
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
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def showEvent(self, event):
        """Được gọi khi dialog hiển thị - bắt đầu camera preview."""
        super().showEvent(event)
        self._start_preview()
    
    def closeEvent(self, event):
        """Được gọi khi dialog đóng - dọn dẹp resources."""
        self._stop_worker()
        super().closeEvent(event)
    
    def _start_preview(self):
        """Khởi động worker để preview camera."""
        self._stop_worker()  # Dừng worker cũ nếu có
        
        self._worker = FaceLoginWorker(num_frames=15)
        # Kết nối các signals
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.embedding_ready.connect(self._on_embedding_ready)
        self._worker.error.connect(self._on_error)
        self._worker.finished_capture.connect(self._on_capture_finished)
        self._worker.start()
    
    def _stop_worker(self):
        """Dừng và dọn dẹp worker thread."""
        if self._worker is not None:
            self._worker.stop()
            # Đợi lâu hơn để đảm bảo thread dừng hoàn toàn
            if not self._worker.wait(5000):
                print("[FaceLoginDialog] Cảnh báo: Worker thread không dừng kịp thời")
            self._worker = None
    
    @QtCore.Slot(object)
    def _on_frame_ready(self, qimg):
        """Cập nhật preview với frame mới."""
        if qimg is not None:
            pixmap = QtGui.QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self.preview_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
    
    @QtCore.Slot(int, int)
    def _on_progress_update(self, current, total):
        """Cập nhật hiển thị tiến độ."""
        self.progress_label.setText(f"Đang quét {current}/{total}...")
        self.btn_start.setEnabled(False)
    
    @QtCore.Slot(str, int)
    def _on_embedding_ready(self, b64, dim):
        """Xử lý khi có embedding - lưu lại để emit sau khi cleanup."""
        self._pending_embedding = (b64, dim)
    
    @QtCore.Slot(str)
    def _on_error(self, message):
        """Xử lý lỗi từ worker."""
        self.preview_label.setText("❌ Lỗi")
        self.progress_label.setText("")
        self.btn_start.setEnabled(False)
        
        QtWidgets.QMessageBox.critical(
            self,
            "Lỗi FaceID",
            message
        )
        self.reject()
    
    @QtCore.Slot(bool)
    def _on_capture_finished(self, success):
        """Xử lý khi capture hoàn thành."""
        if success:
            self.progress_label.setText("✅ Đang xác thực...")
            self.btn_start.setEnabled(False)
            # Dừng worker trước, sau đó mới emit signal
            self._stop_worker()
            if self._pending_embedding:
                b64, dim = self._pending_embedding
                self.login_embedding_ready.emit(b64, dim)
        else:
            self.progress_label.setText("❌ Thất bại. Thử lại?")
            self.btn_start.setEnabled(True)
    
    def _on_start_clicked(self):
        """Xử lý khi nhấn nút Quét."""
        if self._worker is not None:
            self.progress_label.setText("Đang quét 0/15...")
            self.btn_start.setEnabled(False)
            self._worker.start_capture()
    
    def _on_cancel_clicked(self):
        """Xử lý khi nhấn nút Hủy."""
        self._stop_worker()
        self.reject()
