# client/views/login_view.py
from PySide6 import QtWidgets, QtCore, QtGui
import socket
from config.config import SERVER_CONFIG
# Thêm import Controller
from client.controllers.auth_controller_client import AuthController


class LoginView(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.controller = None  # Biến lưu controller
        self.setWindowTitle("Đăng nhập - Chat App")
        self.setGeometry(100, 100, 450, 550)
        
        # Center on screen
        qr = self.frameGeometry()
        cp = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        self.setup_ui()

    def setup_ui(self):
        # Main layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Background gradient
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:0.5 #764ba2, stop:1 #f093fb);
            }
        """)

        # Container với bo góc
        container = QtWidgets.QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 25px;
            }
        """)
        container.setMaximumWidth(400)

        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.setSpacing(10)

        # Logo/Icon
        icon_label = QtWidgets.QLabel("💬")
        icon_label.setStyleSheet("font-size: 60px; background: transparent;")
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(icon_label)

        # Title
        title = QtWidgets.QLabel("Đăng nhập")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
            background: transparent;
        """)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Chào mừng bạn trở lại!")
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #7f8c8d;
            background: transparent;
        """)
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(subtitle)

        container_layout.addSpacing(10)

        # Email input
        email_label = QtWidgets.QLabel("📧 Email")
        email_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50; background: transparent;")
        container_layout.addWidget(email_label)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("example@email.com")
        self.email_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 15px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 15px;
                background-color: white;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 2px solid #667eea;
            }
        """)
        container_layout.addWidget(self.email_input)

        # Password input
        password_label = QtWidgets.QLabel("🔒 Mật khẩu")
        password_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50; background: transparent;")
        container_layout.addWidget(password_label)

        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Nhập mật khẩu")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 15px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 15px;
                background-color: white;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 2px solid #667eea;
            }
        """)
        self.password_input.returnPressed.connect(self.login)
        container_layout.addWidget(self.password_input)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px; background: transparent;")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        container_layout.addWidget(self.status_label)

        container_layout.addSpacing(10)

        # Login button
        self.login_button = QtWidgets.QPushButton("Đăng nhập")
        self.login_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QPushButton:pressed {
                padding: 15px 13px 13px 15px;
            }
        """)
        self.login_button.clicked.connect(self.login)
        self.login_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        container_layout.addWidget(self.login_button)

        # Divider
        divider_layout = QtWidgets.QHBoxLayout()
        line1 = QtWidgets.QFrame()
        line1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #e0e0e0;")
        divider_layout.addWidget(line1)

        or_label = QtWidgets.QLabel("hoặc")
        or_label.setStyleSheet("color: #7f8c8d; font-size: 12px; background: transparent; padding: 0 10px;")
        divider_layout.addWidget(or_label)

        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #e0e0e0;")
        divider_layout.addWidget(line2)

        container_layout.addLayout(divider_layout)

        # Register button
        self.register_button = QtWidgets.QPushButton("Tạo tài khoản mới")
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #667eea;
                border: 2px solid #667eea;
                border-radius: 15px;
                padding: 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #764ba2;
                color: #764ba2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        self.register_button.clicked.connect(self.go_to_register)
        self.register_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        container_layout.addWidget(self.register_button)

        # Center container in main layout
        main_layout.addStretch()
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(container)
        h_layout.addStretch()
        main_layout.addLayout(h_layout)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self.status_label.setText("⚠️ Vui lòng nhập đầy đủ thông tin")
            return

        try:
            print("[DEBUG] Creating new socket and connecting to server...")
            # 1. Tạo socket và kết nối
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)  # 5 second timeout for connection
            client_socket.connect((SERVER_CONFIG["host"], SERVER_CONFIG["port"]))
            client_socket.settimeout(None)  # Remove timeout after connection
            print("[DEBUG] Connected! Creating controller...")

            # 2. KHỞI TẠO CONTROLLER NGAY TẠI ĐÂY
            # Controller sẽ tự động bắt đầu thread nhận dữ liệu
            self.controller = AuthController(client_socket)
            print("[DEBUG] Controller created. Sending login request...")

            # 3. Gửi request Login thông qua Controller (thay vì gửi socket trần)
            request = {
                "action": "login",
                "email": email,
                "password": password
            }
            # Sử dụng send_request của controller để đảm bảo thread-safe
            response = self.controller.send_request(request)
            print(f"[DEBUG login] Response received: {response}")

            if response.get("status") == "success":
                user_id = response.get("user_id")
                display_name = response.get("display_name")
                
                # Update controller with current user ID for reconnection logic
                self.controller.current_user_id = user_id

                # 4. TRUYỀN CONTROLLER (đã khởi tạo) SANG MAIN
                # Lưu ý: Cần chắc chắn bạn đã sửa main.py để nhận tham số này
                self.app.show_main(self.controller, user_id, display_name)

                # Đóng cửa sổ login (App main sẽ mở)
                self.close()
            else:
                self.status_label.setText(f"❌ {response.get('message')}")
                # Nếu login thất bại thì dừng controller để đóng socket, tránh treo
                self.controller.stop()

        except Exception as e:
            self.status_label.setText(f"❌ Lỗi: {str(e)}")
            if self.controller:
                self.controller.stop()

    def go_to_register(self):
        self.app.show_register()