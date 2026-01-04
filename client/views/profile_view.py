# client/views/profile_view.py
from PySide6 import QtWidgets, QtCore, QtGui
import base64


class ProfileDialog(QtWidgets.QDialog):
    def __init__(self, controller, current_display_name, current_avatar_base64=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Cập nhật thông tin cá nhân")
        self.setModal(False)
        self.resize(420, 520)

        self.avatar_base64 = current_avatar_base64

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


