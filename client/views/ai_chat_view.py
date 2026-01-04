import google.generativeai as genai
from PySide6 import QtWidgets, QtCore, QtGui
from config.config import GEMINI_API_KEY
import markdown
import re


class AIChatView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget { background-color: #f7f7f8; font-family: 'Segoe UI', sans-serif; }
            QScrollBar:vertical { border: none; background: #f1f1f1; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #c1c1c1; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #a8a8a8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        # Khởi tạo Gemini
        self.chat_session = None
        self.current_model_name = "gemini-2.5-flash"
        
        self.setup_ui()
        self.init_ai()

    def init_ai(self):
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
            self.show_error("Vui lòng cập nhật API Key trong config!")
            return
        
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(self.current_model_name)
            self.chat_session = self.model.start_chat(history=[])
        except Exception as e:
            self.show_error(f"Lỗi khởi tạo AI: {e}")

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ==========================================
        # HEADER - Model selector và tiêu đề
        # ==========================================
        header = QtWidgets.QWidget()
        header.setObjectName("header")
        header.setStyleSheet("""
            QWidget#header { 
                background-color: #ffffff; 
                border-bottom: 1px solid #e5e5e5;
            }
        """)
        header.setFixedHeight(60)
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        
        # AI Icon và Title
        icon_label = QtWidgets.QLabel("✨")
        icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        h_layout.addWidget(icon_label)
        
        title = QtWidgets.QLabel("Gemini AI")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #171717; background: transparent; margin-left: 8px;")
        h_layout.addWidget(title)
        
        h_layout.addStretch()

        # Model Selector
        self.model_selector = QtWidgets.QComboBox()
        self.model_selector.addItems(["gemini-2.5-flash", "gemini-2.0-flash"])
        self.model_selector.setCurrentText(self.current_model_name)
        self.model_selector.setToolTip("Chọn mô hình AI")
        self.model_selector.setStyleSheet("""
            QComboBox { 
                border: 1px solid #e5e5e5; 
                border-radius: 8px; 
                padding: 8px 14px; 
                background: #f9f9f9; 
                color: #171717; 
                min-width: 160px; 
                font-size: 13px;
            }
            QComboBox:hover { background: #f0f0f0; border-color: #d0d0d0; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { 
                border-left: 4px solid transparent; 
                border-right: 4px solid transparent; 
                border-top: 5px solid #666; 
                margin-right: 10px; 
            }
            QAbstractItemView { 
                background: white; 
                border: 1px solid #e5e5e5; 
                selection-background-color: #f0f0f0;
                outline: none;
                padding: 4px;
            }
        """)
        self.model_selector.currentTextChanged.connect(self.change_model)
        h_layout.addWidget(self.model_selector)
        
        # Reset button
        btn_reset = QtWidgets.QPushButton("🔄")
        btn_reset.setFixedSize(36, 36)
        btn_reset.setToolTip("Reset cuộc trò chuyện")
        btn_reset.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet("""
            QPushButton { background: #f9f9f9; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background: #f0f0f0; }
        """)
        btn_reset.clicked.connect(self.reset_chat)
        h_layout.addWidget(btn_reset)
        
        layout.addWidget(header)

        # ==========================================
        # CHAT AREA - Scroll area với messages
        # ==========================================
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: #f7f7f8; }
        """)
        
        self.chat_container = QtWidgets.QWidget()
        self.chat_container.setStyleSheet("background: #f7f7f8;")
        self.chat_layout = QtWidgets.QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 20, 0, 20)
        self.chat_layout.setSpacing(0)
        self.chat_layout.addStretch()
        
        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)
        
        # Welcome message
        self.add_system_message(f"Xin chào! Tôi đang sử dụng <b>{self.current_model_name}</b> để hỗ trợ bạn.")

        # ==========================================
        # TYPING INDICATOR
        # ==========================================
        self.typing_container = QtWidgets.QWidget()
        self.typing_container.setStyleSheet("background: transparent;")
        self.typing_container.hide()
        typing_layout = QtWidgets.QHBoxLayout(self.typing_container)
        typing_layout.setContentsMargins(24, 10, 24, 10)
        
        # AI avatar for typing
        typing_avatar = QtWidgets.QLabel("✨")
        typing_avatar.setFixedSize(32, 32)
        typing_avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        typing_avatar.setStyleSheet("font-size: 16px; background: #10a37f; border-radius: 16px;")
        typing_layout.addWidget(typing_avatar)
        
        self.typing_label = QtWidgets.QLabel("•••")
        self.typing_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #666;
                padding: 12px 18px;
                border-radius: 18px;
                font-weight: 600;
                font-size: 16px;
                margin-left: 10px;
            }
        """)
        typing_layout.addWidget(self.typing_label)
        typing_layout.addStretch()
        
        layout.addWidget(self.typing_container)

        # ==========================================
        # INPUT AREA - Bottom input bar
        # ==========================================
        input_container = QtWidgets.QWidget()
        input_container.setStyleSheet("background-color: #f7f7f8;")
        input_layout = QtWidgets.QHBoxLayout(input_container)
        input_layout.setContentsMargins(24, 10, 24, 20)
        
        # Input frame
        input_frame = QtWidgets.QFrame()
        input_frame.setStyleSheet("""
            QFrame { 
                background-color: #ffffff; 
                border-radius: 24px; 
                border: 1px solid #e5e5e5;
            }
        """)
        frame_layout = QtWidgets.QHBoxLayout(input_frame)
        frame_layout.setContentsMargins(20, 8, 8, 8)

        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Nhập tin nhắn...")
        self.input_field.setStyleSheet("""
            QLineEdit { 
                border: none; 
                background: transparent; 
                color: #171717; 
                font-size: 15px; 
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        frame_layout.addWidget(self.input_field)

        self.btn_send = QtWidgets.QPushButton("➤")
        self.btn_send.setFixedSize(40, 40)
        self.btn_send.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton { 
                background: #10a37f; 
                color: white; 
                border-radius: 20px; 
                font-size: 16px; 
                border: none;
            }
            QPushButton:hover { background: #0d8a6a; }
            QPushButton:pressed { background: #0a7259; }
        """)
        self.btn_send.clicked.connect(self.send_message)
        frame_layout.addWidget(self.btn_send)

        input_layout.addWidget(input_frame)
        layout.addWidget(input_container)
        
        # Typing animation timer
        self.typing_timer = QtCore.QTimer()
        self.typing_timer.setInterval(400)
        self.typing_timer.timeout.connect(self.animate_typing)
        self.typing_dots = 0

    def add_system_message(self, text):
        """Thêm thông báo hệ thống (đổi model, thông tin) - căn giữa"""
        msg_widget = QtWidgets.QWidget()
        msg_widget.setStyleSheet("background: transparent;")
        msg_layout = QtWidgets.QHBoxLayout(msg_widget)
        msg_layout.setContentsMargins(24, 8, 24, 8)
        
        msg_layout.addStretch()
        
        label = QtWidgets.QLabel(text)
        label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                background-color: #e8f5e9;
                color: #2e7d32;
                padding: 10px 20px;
                border-radius: 16px;
                font-size: 13px;
            }
        """)
        msg_layout.addWidget(label)
        
        msg_layout.addStretch()
        
        # Insert before stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_widget)
        self.scroll_to_bottom()

    def add_user_message(self, text):
        """Thêm tin nhắn người dùng - BÊN PHẢI"""
        msg_widget = QtWidgets.QWidget()
        msg_widget.setStyleSheet("background: transparent;")
        msg_layout = QtWidgets.QHBoxLayout(msg_widget)
        msg_layout.setContentsMargins(60, 12, 24, 12)
        
        msg_layout.addStretch()  # Push to right
        
        bubble = QtWidgets.QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)
        bubble.setStyleSheet("""
            QLabel {
                background-color: #10a37f;
                color: white;
                padding: 14px 18px;
                border-radius: 20px 20px 4px 20px;
                font-size: 15px;
                line-height: 1.5;
            }
        """)
        msg_layout.addWidget(bubble)
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_widget)
        self.scroll_to_bottom()

    def add_ai_message(self, text, is_error=False):
        """Thêm phản hồi AI - BÊN TRÁI với avatar"""
        msg_widget = QtWidgets.QWidget()
        msg_widget.setObjectName("ai_message")
        msg_widget.setStyleSheet("""
            QWidget#ai_message { background-color: #ffffff; }
        """)
        msg_layout = QtWidgets.QHBoxLayout(msg_widget)
        msg_layout.setContentsMargins(24, 16, 60, 16)
        msg_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        # AI Avatar
        avatar = QtWidgets.QLabel("✨")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("""
            background: #10a37f; 
            border-radius: 18px; 
            font-size: 16px;
        """)
        msg_layout.addWidget(avatar)
        
        # Message content
        content = QtWidgets.QLabel()
        content.setWordWrap(True)
        content.setTextFormat(QtCore.Qt.TextFormat.RichText)
        content.setOpenExternalLinks(True)
        
        # Convert markdown to HTML
        try:
            html_text = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        except:
            html_text = text
        
        content.setText(html_text)
        content.setStyleSheet(f"""
            QLabel {{
                color: {'#c0392b' if is_error else '#171717'};
                padding: 0px 16px;
                font-size: 15px;
                line-height: 1.6;
                background: transparent;
            }}
        """)
        msg_layout.addWidget(content, 1)
        
        msg_layout.addStretch()
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_widget)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        QtCore.QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def animate_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        dots = "•" * (self.typing_dots if self.typing_dots > 0 else 3)
        self.typing_label.setText(dots)

    def show_typing(self):
        self.typing_container.show()
        self.typing_timer.start()
        self.scroll_to_bottom()

    def hide_typing(self):
        self.typing_container.hide()
        self.typing_timer.stop()

    def change_model(self, model_name):
        self.current_model_name = model_name
        self.init_ai()
        self.add_system_message(f"✨ Đã chuyển sang model: <b>{model_name}</b>")

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return
        
        if not self.chat_session:
            self.init_ai()
            if not self.chat_session: return

        self.input_field.clear()
        self.add_user_message(text)
        self.show_typing()

        import threading
        t = threading.Thread(target=self._generate_response, args=(text,))
        t.start()

    def _generate_response(self, text):
        try:
            response = self.chat_session.send_message(text)
            QtCore.QMetaObject.invokeMethod(
                self, "display_ai_response", 
                QtCore.Qt.QueuedConnection, 
                QtCore.Q_ARG(str, response.text),
                QtCore.Q_ARG(bool, False)
            )
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                match = re.search(r"retry in (\d+(\.\d+)?)s", error_msg)
                if match:
                    seconds = float(match.group(1))
                    friendly_msg = f"⚠️ HẾT LƯỢT SỬ DỤNG\n\nModel {self.current_model_name} đang bị giới hạn.\nVui lòng đợi {seconds:.1f} giây hoặc chọn model khác."
                else:
                    friendly_msg = f"⚠️ HẾT LƯỢT SỬ DỤNG\n\nModel {self.current_model_name} đã hết lượt miễn phí.\nVui lòng thử model khác."
                QtCore.QMetaObject.invokeMethod(
                    self, "display_ai_response", 
                    QtCore.Qt.QueuedConnection, 
                    QtCore.Q_ARG(str, friendly_msg),
                    QtCore.Q_ARG(bool, True)
                )
            else:
                QtCore.QMetaObject.invokeMethod(
                    self, "display_ai_response", 
                    QtCore.Qt.QueuedConnection, 
                    QtCore.Q_ARG(str, f"Lỗi: {e}"),
                    QtCore.Q_ARG(bool, True)
                )

    @QtCore.Slot(str, bool)
    def display_ai_response(self, text, is_error=False):
        self.hide_typing()
        self.add_ai_message(text, is_error)

    def reset_chat(self):
        # Clear all messages
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.init_ai()
        self.add_system_message(f"🔄 Đã reset cuộc trò chuyện ({self.current_model_name})")

    def show_error(self, message):
        QtWidgets.QMessageBox.warning(self, "Lỗi AI", message)
