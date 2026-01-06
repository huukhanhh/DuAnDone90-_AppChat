# client/views/profile_view.py
from PySide6 import QtWidgets, QtCore, QtGui
import base64


class ProfileDialog(QtWidgets.QDialog):
    def __init__(self, controller, current_display_name, current_avatar_base64=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Cập nhật thông tin cá nhân")
        self.setModal(False)
        self.resize(420, 650)  # Tăng chiều cao để chứa FaceID section

        self.avatar_base64 = current_avatar_base64
        
        # FaceID enrollment data (pending)
        self._pending_face_data = None

        layout = QtWidgets.QVBoxLayout(self)

        # Avatar preview
        self.avatar_label = QtWidgets.QLabel()
        self.avatar_label.setFixedSize(120, 120)
        self.avatar_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("border-radius: 60px; background: #eee;")
        layout.addWidget(self.avatar_label, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._refresh_avatar_preview()

        self.change_avatar_btn = QtWidgets.QPushButton("Chọn ảnh đại diện...")
        self.change_avatar_btn.clicked.connect(self.choose_avatar)
        layout.addWidget(self.change_avatar_btn, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Display name
        form = QtWidgets.QFormLayout()
        self.display_name_edit = QtWidgets.QLineEdit()
        self.display_name_edit.setText(current_display_name or "")
        form.addRow("Tên hiển thị", self.display_name_edit)

        # Password change (optional)
        self.old_password_edit = QtWidgets.QLineEdit(); self.old_password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.new_password_edit = QtWidgets.QLineEdit(); self.new_password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.new_password2_edit = QtWidgets.QLineEdit(); self.new_password2_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        form.addRow("Mật khẩu hiện tại", self.old_password_edit)
        form.addRow("Mật khẩu mới", self.new_password_edit)
        form.addRow("Nhập lại mật khẩu", self.new_password2_edit)
        layout.addLayout(form)

        # ============================================================
        # FaceID Section
        # ============================================================
        layout.addSpacing(10)
        
        # Separator line
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #ddd;")
        layout.addWidget(separator)
        
        layout.addSpacing(5)
        
        # FaceID title
        faceid_title = QtWidgets.QLabel("🔐 FaceID")
        faceid_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a73e8;")
        layout.addWidget(faceid_title)
        
        # FaceID status label
        self.faceid_status_label = QtWidgets.QLabel("Đang kiểm tra...")
        self.faceid_status_label.setStyleSheet("font-size: 13px; color: #666; margin-left: 5px;")
        layout.addWidget(self.faceid_status_label)
        
        # FaceID buttons
        faceid_btns = QtWidgets.QHBoxLayout()
        faceid_btns.setSpacing(10)
        
        self.btn_enroll_face = QtWidgets.QPushButton("📷 Thiết lập / Cập nhật FaceID")
        self.btn_enroll_face.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                font-size: 12px;
                padding: 8px 15px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1557b0; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.btn_enroll_face.clicked.connect(self._on_enroll_face_clicked)
        
        self.btn_disable_face = QtWidgets.QPushButton("🚫 Tắt FaceID")
        self.btn_disable_face.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #666;
                font-size: 12px;
                padding: 8px 15px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:disabled { background-color: #f9f9f9; color: #bbb; }
        """)
        self.btn_disable_face.clicked.connect(self._on_disable_face_clicked)
        
        faceid_btns.addWidget(self.btn_enroll_face)
        faceid_btns.addWidget(self.btn_disable_face)
        faceid_btns.addStretch()
        layout.addLayout(faceid_btns)
        
        layout.addSpacing(10)
        # ============================================================
        # End FaceID Section
        # ============================================================

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#e74c3c")
        layout.addWidget(self.status_label)

        # Buttons
        btns = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Lưu thay đổi")
        self.save_btn.clicked.connect(self.save_changes)
        btns.addStretch(); btns.addWidget(self.save_btn)
        layout.addLayout(btns)

    def showEvent(self, event):
        """Called when dialog is shown. Fetch FaceID status."""
        super().showEvent(event)
        self._refresh_faceid_status()

    def _refresh_faceid_status(self):
        """Fetch FACE_STATUS from server and update UI."""
        try:
            resp = self.controller.send_request({"action": "FACE_STATUS"})
            
            if resp.get("type") == "FACE_STATUS_RESULT" and resp.get("ok"):
                has_face = resp.get("has_face", False)
                enabled = resp.get("enabled", False)
                
                if not has_face:
                    self.faceid_status_label.setText("⚪ Chưa thiết lập")
                    self.faceid_status_label.setStyleSheet("font-size: 13px; color: #666;")
                    self.btn_disable_face.setEnabled(False)
                elif enabled:
                    self.faceid_status_label.setText("🟢 Đang bật")
                    self.faceid_status_label.setStyleSheet("font-size: 13px; color: #22c55e; font-weight: bold;")
                    self.btn_disable_face.setEnabled(True)
                else:
                    self.faceid_status_label.setText("🔴 Đã tắt")
                    self.faceid_status_label.setStyleSheet("font-size: 13px; color: #e74c3c;")
                    self.btn_disable_face.setEnabled(True)
            else:
                self.faceid_status_label.setText("⚠️ Không thể kiểm tra trạng thái")
                self.faceid_status_label.setStyleSheet("font-size: 13px; color: #f59e0b;")
        except Exception as e:
            print(f"[ProfileDialog] Error fetching FACE_STATUS: {e}")
            self.faceid_status_label.setText("⚠️ Lỗi kết nối")
            self.faceid_status_label.setStyleSheet("font-size: 13px; color: #e74c3c;")

    def _on_enroll_face_clicked(self):
        """Open FaceEnrollDialog to capture face embedding."""
        try:
            from client.ui.face_enroll_dialog import FaceEnrollDialog
        except ImportError as e:
            QtWidgets.QMessageBox.critical(
                self, "Lỗi",
                f"Không thể mở dialog FaceID: {e}"
            )
            return
        
        dialog = FaceEnrollDialog(self)
        dialog.enrollment_complete.connect(self._on_enrollment_complete)
        dialog.exec()

    @QtCore.Slot(str, int, str, float)
    def _on_enrollment_complete(self, embedding_b64: str, embedding_dim: int, 
                                 model_name: str, threshold: float):
        """Handle completed face enrollment - send to server."""
        try:
            # Send FACE_ENROLL to server
            resp = self.controller.send_request({
                "action": "FACE_ENROLL",
                "embedding_b64": embedding_b64,
                "embedding_dim": embedding_dim,
                "model_name": model_name,
                "threshold": threshold
            })
            
            if resp.get("type") == "FACE_ENROLL_RESULT" and resp.get("ok"):
                QtWidgets.QMessageBox.information(
                    self, "Thành công",
                    "Đã thiết lập FaceID thành công!\nBạn có thể đăng nhập bằng khuôn mặt."
                )
                self._refresh_faceid_status()
            else:
                reason = resp.get("reason", "Unknown error")
                QtWidgets.QMessageBox.warning(
                    self, "Thất bại",
                    f"Không thể thiết lập FaceID: {reason}"
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Lỗi",
                f"Lỗi khi gửi dữ liệu FaceID: {e}"
            )

    def _on_disable_face_clicked(self):
        """Disable FaceID for current user."""
        reply = QtWidgets.QMessageBox.question(
            self, "Xác nhận",
            "Bạn có chắc chắn muốn tắt FaceID?\nBạn sẽ không thể đăng nhập bằng khuôn mặt cho đến khi thiết lập lại.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        try:
            resp = self.controller.send_request({"action": "FACE_DISABLE"})
            
            if resp.get("type") == "FACE_DISABLE_RESULT" and resp.get("ok"):
                QtWidgets.QMessageBox.information(
                    self, "Thành công",
                    "Đã tắt FaceID."
                )
                self._refresh_faceid_status()
            else:
                reason = resp.get("reason", "Unknown error")
                QtWidgets.QMessageBox.warning(
                    self, "Thất bại",
                    f"Không thể tắt FaceID: {reason}"
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Lỗi",
                f"Lỗi khi tắt FaceID: {e}"
            )

    def _refresh_avatar_preview(self):
        if self.avatar_base64:
            try:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(base64.b64decode(self.avatar_base64))
                # Tạo pixmap tròn
                rounded = QtGui.QPixmap(120, 120)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 120, 120)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pixmap.scaled(120, 120, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
                painter.end()
                self.avatar_label.setPixmap(rounded)
                self.avatar_label.setStyleSheet("background-color: transparent;")
            except Exception:
                self.avatar_label.setText("[Ảnh lỗi]")
                self.avatar_label.setStyleSheet("font-size:48px; border-radius:60px; background:#eee;")
        else:
            self.avatar_label.setText("👤")
            self.avatar_label.setStyleSheet("font-size:48px; border-radius:60px; background:#eee;")

    def choose_avatar(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn ảnh đại diện", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)")
        if file_path:
            try:
                # Đọc và resize ảnh để giảm kích thước (tối đa 200x200)
                pixmap = QtGui.QPixmap(file_path)
                if pixmap.isNull():
                    QtWidgets.QMessageBox.warning(self, "Lỗi", "Không thể đọc file ảnh")
                    return
                
                # Resize ảnh nếu quá lớn (giữ tỷ lệ, max 200x200)
                if pixmap.width() > 200 or pixmap.height() > 200:
                    pixmap = pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                
                # Convert sang bytes và encode base64
                byte_array = QtCore.QByteArray()
                buffer = QtCore.QBuffer(byte_array)
                buffer.open(QtCore.QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")  # Dùng PNG để đảm bảo chất lượng
                buffer.close()
                
                self.avatar_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
                self._refresh_avatar_preview()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể đọc ảnh: {e}")

    def save_changes(self):
        # Update profile
        name = self.display_name_edit.text().strip()
        if name == "":
            self.status_label.setText("Tên hiển thị không được để trống")
            return

        # Disable button để tránh click nhiều lần
        self.save_btn.setEnabled(False)
        self.status_label.setText("Đang cập nhật...")

        try:
            # Change password if provided (xử lý trước khi update profile)
            if self.old_password_edit.text() or self.new_password_edit.text() or self.new_password2_edit.text():
                if self.new_password_edit.text() != self.new_password2_edit.text():
                    self.status_label.setText("Mật khẩu xác nhận không khớp")
                    self.save_btn.setEnabled(True)
                    return
                if len(self.new_password_edit.text()) < 6:
                    self.status_label.setText("Mật khẩu mới phải >= 6 ký tự")
                    self.save_btn.setEnabled(True)
                    return
                # Gửi cả password trong request update_profile
                resp = self.controller.update_profile(
                    display_name=name, 
                    avatar_data=self.avatar_base64,
                    old_password=self.old_password_edit.text(),
                    new_password=self.new_password_edit.text()
                )
            else:
                resp = self.controller.update_profile(
                    display_name=name, 
                    avatar_data=self.avatar_base64
                )
            
            if resp.get("status") != "success":
                self.status_label.setText(resp.get("message", "Không thể cập nhật hồ sơ"))
                self.save_btn.setEnabled(True)
                return

            QtWidgets.QMessageBox.information(self, "Thành công", "Đã cập nhật thông tin")
            self.accept()
        except Exception as e:
            self.status_label.setText(f"Lỗi: {str(e)}")
            self.save_btn.setEnabled(True)
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật: {str(e)}")



