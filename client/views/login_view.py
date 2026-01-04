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

        # Dark gradient background
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        # Container - no border, transparent background
        container = QtWidgets.QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        container.setMaximumWidth(480)
        container.setMinimumWidth(420)

        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(50, 50, 50, 50)
        container_layout.setSpacing(12)

        # Logo/Icon
        icon_label = QtWidgets.QLabel("💬")
        icon_label.setStyleSheet("""
            font-size: 64px; 
            background: transparent;
            padding: 15px;
        """)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(icon_label)

        # Title - Larger and bolder
        title = QtWidgets.QLabel("Đăng nhập")
        title.setStyleSheet("""
            font-size: 38px;
            font-weight: 700;
            color: #ffffff;
            background: transparent;
        """)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Chào mừng bạn trở lại!")
        subtitle.setStyleSheet("""
            font-size: 16px;
            color: rgba(255, 255, 255, 0.7);
            background: transparent;
            margin-bottom: 15px;
        """)
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(subtitle)

        container_layout.addSpacing(25)

        # Email input label
        email_label = QtWidgets.QLabel("Email")
        email_label.setStyleSheet("""
            font-size: 14px; 
            font-weight: 600;
color: rgba(255, 255, 255, 0.9); 
            background: transparent;
            margin-left: 5px;
            margin-bottom: 5px;
        """)
        container_layout.addWidget(email_label)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("example@email.com")
        self.email_input.setStyleSheet("""
            QLineEdit {
                padding: 16px 20px;
                font-size: 16px;
                border: none;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.45);
            }
        """)
        container_layout.addWidget(self.email_input)

        container_layout.addSpacing(15)

        # Password input label
        password_label = QtWidgets.QLabel("Mật khẩu")
        password_label.setStyleSheet("""
            font-size: 14px; 
            font-weight: 600; 
            color: rgba(255, 255, 255, 0.9); 
            background: transparent;
            margin-left: 5px;
            margin-bottom: 5px;
        """)
        container_layout.addWidget(password_label)

        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Nhập mật khẩu của bạn")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 16px 20px;
                font-size: 16px;
                border: none;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.45);
            }
        """)
        self.password_input.returnPressed.connect(self.login)
        container_layout.addWidget(self.password_input)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("""
            color: #ff6b6b; 
            font-size: 14px; 
            background: transparent;
            padding: 8px;
        """)
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        container_layout.addWidget(self.status_label)

        container_layout.addSpacing(20)

        # Login button
        self.login_button = QtWidgets.QPushButton("Đăng nhập")
        self.login_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6c63ff, stop:1 #4834d4);
color: white;
                border: none;
                border-radius: 10px;
                padding: 18px;
                font-size: 17px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7c74ff, stop:1 #5a45e8);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5b52e0, stop:1 #3d28c4);
            }
        """)
        self.login_button.clicked.connect(self.login)
        self.login_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        container_layout.addWidget(self.login_button)

        container_layout.addSpacing(15)

        # Divider
        divider_layout = QtWidgets.QHBoxLayout()
        line1 = QtWidgets.QFrame()
        line1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); max-height: 1px; border: none;")
        divider_layout.addWidget(line1)

        or_label = QtWidgets.QLabel("hoặc")
        or_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6); 
            font-size: 14px; 
            background: transparent; 
            padding: 0 20px;
        """)
        divider_layout.addWidget(or_label)

        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); max-height: 1px; border: none;")
        divider_layout.addWidget(line2)

        container_layout.addLayout(divider_layout)

        container_layout.addSpacing(15)

        # Register button
        self.register_button = QtWidgets.QPushButton("Tạo tài khoản mới")
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 18px;
                font-size: 17px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.25);
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