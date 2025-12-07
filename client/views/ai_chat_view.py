import google.generativeai as genai
from PySide6 import QtWidgets, QtCore, QtGui
from config.config import GEMINI_API_KEY
import markdown

import re

class AIChatView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget { background-color: #ffffff; font-family: 'Segoe UI', sans-serif; }
            QScrollBar:vertical { border: none; background: #f1f1f1; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #c1c1c1; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #a8a8a8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        # Initialize Gemini
        self.chat_session = None
        # Default model
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
        
        # Header
        header = QtWidgets.QWidget()
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #eee;")
        header.setFixedHeight(70)
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        
        # Title with Icon
        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_container)
        title_layout.setContentsMargins(0,0,0,0)
        title_layout.setSpacing(10)
        
        # Simplistic AI Icon representation (Label)
        icon_label = QtWidgets.QLabel("✨")
        icon_label.setStyleSheet("font-size: 24px;")
        
        title = QtWidgets.QLabel("Gemini Assistant")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #202124;")
        
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title)
        h_layout.addWidget(title_container)

        h_layout.addStretch()

        # Model Selector
        self.model_selector = QtWidgets.QComboBox()
        self.model_selector.addItems(["gemini-2.5-flash", "gemini-2.0-flash"])
        self.model_selector.setCurrentText(self.current_model_name)
        self.model_selector.setToolTip("Chọn bản cập nhật mô hình")
        self.model_selector.setStyleSheet("""
            QComboBox { 
                border: 1px solid #dadce0; 
                border-radius: 8px; 
                padding: 8px 12px; 
                background: white; 
                color: #202124; 
                min-width: 140px; 
                font-size: 14px;
            }
            QComboBox:hover { border: 1px solid #202124; background: #f8f9fa; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { 
                image: none; 
                border-left: 5px solid transparent; 
                border-right: 5px solid transparent; 
                border-top: 6px solid #5f6368; 
                margin-right: 8px; 
            }
            QAbstractItemView { 
                background: white; 
                border: 1px solid #dadce0; 
                selection-background-color: #e8f0fe; 
                selection-color: #1967d2; 
                outline: none;
                padding: 5px;
            }
            QAbstractItemView::item { padding: 8px; border-radius: 4px; color: #202124; }
        """)
        self.model_selector.currentTextChanged.connect(self.change_model)
        h_layout.addWidget(self.model_selector)
        
        layout.addWidget(header)

        # Chat Area
        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit { border: none; background: #ffffff; padding: 20px; font-size: 15px; line-height: 1.5; color: #3c4043; outline: none; }
        """)
        # Initial greeting with cleaner look
        self.chat_display.setHtml(f"""
            <div style='text-align: center; margin-top: 40px;'>
                <h2 style='color: #202124; font-weight: 500;'>Xin chào!</h2>
                <div style='color: #5f6368; font-size: 14px;'>Tôi đang sử dụng <b>{self.current_model_name}</b> để hỗ trợ bạn.</div>
            </div>
        """)
        layout.addWidget(self.chat_display)

        # Typing Indicator (Inserted before input)
        self.typing_container = QtWidgets.QWidget()
        self.typing_container.hide()
        typing_layout = QtWidgets.QHBoxLayout(self.typing_container)
        typing_layout.setContentsMargins(20, 0, 20, 5)
        
        self.typing_label = QtWidgets.QLabel("•••")
        self.typing_label.setStyleSheet("""
            QLabel {
                background-color: #f1f3f4;
                color: #5f6368;
                padding: 8px 15px;
                border-radius: 15px;
                font-weight: 900;
                font-size: 18px;
            }
        """)
        typing_layout.addWidget(self.typing_label)
        typing_layout.addStretch() # Push to left
        
        layout.addWidget(self.typing_container)

        # Input Area Wrapper
        input_container = QtWidgets.QWidget()
        input_container.setStyleSheet("background-color: white; border-top: 1px solid white;") # No distinct border, floating feel
        input_layout = QtWidgets.QHBoxLayout(input_container)
        input_layout.setContentsMargins(20, 10, 20, 20)
        
        # Inner Frame for nicer input look
        input_frame = QtWidgets.QFrame()
        input_frame.setStyleSheet("""
            QFrame { 
                background-color: #f1f3f4; 
                border-radius: 25px; 
                border: 1px solid transparent;
            }
            QFrame:focus-within { background-color: white; border: 1px solid #dadce0; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        """)
        frame_layout = QtWidgets.QHBoxLayout(input_frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)

        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Nhập tin nhắn tại đây...")
        self.input_field.setStyleSheet("""
            QLineEdit { border: none; background: transparent; color: #202124; font-size: 15px; }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        frame_layout.addWidget(self.input_field)

        self.btn_send = QtWidgets.QPushButton("➤")
        self.btn_send.setFixedSize(36, 36)
        self.btn_send.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton { 
                background: #f1f3f4; 
                color: #5f6368; 
                border-radius: 18px; 
                font-size: 16px; 
                border: none; 
                padding-left: 3px;
            }
            QPushButton:hover { background: #e8f0fe; color: #1967d2; }
            QPushButton:pressed { background: #d2e3fc; }
        """)
        self.btn_send.clicked.connect(self.send_message)
        frame_layout.addWidget(self.btn_send)

        input_layout.addWidget(input_frame)
        layout.addWidget(input_container)
        
        # Typing Timer
        self.typing_timer = QtCore.QTimer()
        self.typing_timer.setInterval(500)
        self.typing_timer.timeout.connect(self.animate_typing)
        self.typing_dots = 0

    def animate_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        # self.typing_label.setText("•" * (self.typing_dots if self.typing_dots > 0 else 1)) # Simple dots
        # Animated opacity or just length? 
        # User asked for "horizontal 3 dots moving".
        # Let's do: . .. ...
        dots = "." * self.typing_dots
        if self.typing_dots == 0: dots = "..." # Keep it visible 
        
        # Better animation: 3 fixed dots, cycling colors? Or just text.
        # Let's stick to the text cycle for simplicity and clarity.
        # "•" "••" "•••"
        text = "•" * ((self.typing_dots % 3) + 1) 
        self.typing_label.setText(text)

    def show_typing(self):
        self.typing_container.show()
        self.typing_timer.start()
        # Scroll to bottom to see typing
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def hide_typing(self):
        self.typing_container.hide()
        self.typing_timer.stop()

    def change_model(self, model_name):
        self.current_model_name = model_name
        self.init_ai()
        self.chat_display.insertHtml(f"<div style='color: #1e8e3e; text-align: center; margin: 10px; font-size: 13px;'><i>✨ Đã chuyển sang model: {model_name}</i></div><br>")
        self.chat_display.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return
        
        if not self.chat_session:
            self.init_ai()
            if not self.chat_session: return

        self.input_field.clear()
        self.append_message(text, is_user=True)
        self.chat_display.moveCursor(QtGui.QTextCursor.MoveOperation.End)

        self.show_typing() # Show typing indicator

        # Run in thread to prevent freezing UI
        import threading
        t = threading.Thread(target=self._generate_response, args=(text,))
        t.start()


    def _generate_response(self, text):
        try:
            response = self.chat_session.send_message(text)
            QtCore.QMetaObject.invokeMethod(self, "display_ai_response", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, response.text))
        except Exception as e:
             error_msg = str(e)
             if "429" in error_msg:
                 # Extract retry time
                 import re
                 match = re.search(r"retry in (\d+(\.\d+)?)s", error_msg)
                 if match:
                     seconds = float(match.group(1))
                     friendly_msg = f"""
                     <div style='color: #c0392b; font-weight: bold;'>⚠️ HẾT LƯỢT SỬ DỤNG (QUOTA EXCEEDED)</div>
                     <div style='color: #c0392b;'>Model <b>{self.current_model_name}</b> đang bị giới hạn.</div>
                     <div style='color: #d35400; margin-top: 5px;'>⏳ Vui lòng đợi <b>{seconds:.1f} giây</b> để reset.</div>
                     <div style='color: #7f8c8d; margin-top: 5px; font-size: 12px;'>Hoặc hãy thử chọn model khác từ menu phía trên.</div>
                     """
                 else:
                     friendly_msg = f"""
                     <div style='color: #c0392b; font-weight: bold;'>⚠️ HẾT LƯỢT SỬ DỤNG (QUOTA EXCEEDED)</div>
                     <div style='color: #c0392b;'>Model <b>{self.current_model_name}</b> đã hết lượt miễn phí.</div>
                     <div style='color: #7f8c8d; margin-top: 5px;'>Vui lòng thử model khác (Ví dụ: gemini-1.5-flash).</div>
                     """
                 QtCore.QMetaObject.invokeMethod(self, "display_ai_response", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, friendly_msg), QtCore.Q_ARG(bool, True))
             else:
                QtCore.QMetaObject.invokeMethod(self, "display_ai_response", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Error: {e}"), QtCore.Q_ARG(bool, False))

    @QtCore.Slot(str, bool)
    @QtCore.Slot(str)
    def display_ai_response(self, text, is_html_error=False):
        self.hide_typing() # Stop animation
        if is_html_error:
            self.chat_display.insertHtml(text)
            self.chat_display.insertHtml("<br>")
        else:
            self.append_message(text, is_user=False)
        self.chat_display.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def append_message(self, text, is_user):
        # Format HTML for chat bubble
        align = "right" if is_user else "left"
        
        # Colors: Gemini User = Blueish Gradient (simulated with solid for HTML), AI = Light Gray/White
        if is_user:
            bg_color = "#e8f0fe" # Light blue like Gemini user
            text_color = "#202124"
            border_radius = "20px 20px 5px 20px" # Rounded with one sharp corner
        else:
            bg_color = "#ffffff"
            text_color = "#202124"
            border_radius = "20px 20px 20px 5px"
            
        # Convert markdown to html for AI response
        if not is_user:
            try:
                text = markdown.markdown(text)
            except: 
                pass 
        
        # AI Icon for bot
        avatar = ""
        if not is_user:
            avatar = "<div style='font-size: 20px; margin-right: 10px;'>✨</div>"
        
        content = f"""
        <div style="width: 100%; display: flex; justify-content: {align}; margin-bottom: 20px;">
            {avatar if not is_user else ''}
            <div style="
                background-color: {bg_color}; 
                padding: 12px 18px; 
                border-radius: {border_radius}; 
                max-width: 75%; 
                font-size: 15px;
                {'border: 1px solid #e0e0e0;' if not is_user else ''} 
                color: {text_color};
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            ">
                {text}
            </div>
        </div>
        """
        self.chat_display.insertHtml(content)
        self.chat_display.insertHtml("<br>")

    def reset_chat(self):
        self.chat_display.clear()
        self.chat_display.setHtml(f"<div style='color: #7f8c8d; text-align: center; margin-top: 20px;'>Đã reset cuộc trò chuyện mới ({self.current_model_name}).</div>")
        self.init_ai()

    def show_error(self, message):
        QtWidgets.QMessageBox.warning(self, "Lỗi AI", message)
