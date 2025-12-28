from PySide6 import QtWidgets, QtCore, QtGui, QtMultimedia

try:
    from PySide6 import QtMultimediaWidgets

    HAS_VIDEO_WIDGET = True
except ImportError:
    HAS_VIDEO_WIDGET = False

import sys
import json
import threading
import base64
import os
import io
import wave
import pyaudio
import re

from client.controllers.auth_controller_client import AuthController
from client.views.profile_view import ProfileDialog
from client.views.create_group_dialog import CreateGroupDialog
from client.views.ai_chat_view import AIChatView
from client.views.call_dialog import IncomingCallDialog, ActiveCallDialog


# --- GIỮ NGUYÊN CÁC CLASS CON: ChatListItem, VoiceMessageWidget, ClickableLabel, VideoMessageWidget ---
# (Bạn hãy giữ nguyên code các class con này như cũ để tiết kiệm dòng, chỉ thay class MainView bên dưới)

class ChatListItem(QtWidgets.QWidget):
    def __init__(self, user_id, display_name, last_message="", avatar_base64=None, item_type="user", parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.item_type = item_type
        self.display_name = display_name
        self.avatar_base64 = avatar_base64
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)
        avatar_label = QtWidgets.QLabel()
        avatar_label.setFixedSize(40, 40)
        avatar_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if self.avatar_base64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(self.avatar_base64))
                # Tạo pixmap tròn
                rounded = QtGui.QPixmap(40, 40)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 40, 40)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(40, 40, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                avatar_label.setPixmap(rounded)
                avatar_label.setStyleSheet("background-color: transparent;")
            except Exception:
                avatar_label.setText("👤")
                avatar_label.setStyleSheet("background-color: #ddd; border-radius: 20px;")
        else:
            avatar_label.setText("👤")
            avatar_label.setStyleSheet("background-color: #ddd; border-radius: 20px;")
        layout.addWidget(avatar_label)

        # Info Layout
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Name Layout (Name + Status Dot)
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.setSpacing(5)
        
        name_label = QtWidgets.QLabel(display_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        name_layout.addWidget(name_label)
        
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setStyleSheet("color: #2ecc71; font-size: 10px;") # Green dot
        self.status_dot.hide() # Default hidden
        name_layout.addWidget(self.status_dot)
        name_layout.addStretch()
        
        info_layout.addLayout(name_layout)

        last_msg_label = QtWidgets.QLabel(last_message if last_message else "Bắt đầu trò chuyện...")
        last_msg_label.setStyleSheet("font-size: 11px; color: #95a5a6;")
        last_msg_label.setWordWrap(False)
        info_layout.addWidget(last_msg_label)
        layout.addLayout(info_layout)
        self.setLayout(layout)
        self.setStyleSheet(
            "ChatListItem { background-color: transparent; border-bottom: 1px solid #f0f0f0; } ChatListItem:hover { background-color: #f8f9fa; }")

    def set_online(self, is_online):
        if is_online:
            self.status_dot.show()
        else:
            self.status_dot.hide()


class VoiceMessageWidget(QtWidgets.QWidget):
    def __init__(self, voice_data, is_self=False, parent=None):
        super().__init__(parent)
        self.voice_data = voice_data
        self.is_playing = False
        self.audio_player = QtMultimedia.QMediaPlayer()
        self.temp_file = None
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)
        self.play_button = QtWidgets.QPushButton("▶")
        self.play_button.setFixedSize(24, 24)
        self.play_button.setStyleSheet(
            "QPushButton { background-color: rgba(255,255,255,0.3); border: none; border-radius: 12px; color: white; } QPushButton:hover { background-color: rgba(255,255,255,0.5); }")
        self.play_button.clicked.connect(self.toggle_play)
        layout.addWidget(self.play_button)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; background-color: rgba(0,0,0,0.1); border-radius: 2px; } QProgressBar::chunk { background-color: white; border-radius: 2px; }")
        layout.addWidget(self.progress_bar)
        self.time_label = QtWidgets.QLabel("0:00")
        self.time_label.setStyleSheet("color: #eee; font-size: 10px;")
        layout.addWidget(self.time_label)
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.audio_player.positionChanged.connect(self.on_position_changed)
        self.audio_player.durationChanged.connect(self.on_duration_changed)
        self.audio_player.stateChanged.connect(self.on_state_changed)
        self.setFixedHeight(40);
        self.setFixedWidth(200);
        self.setStyleSheet("background: transparent;")

    def toggle_play(self):
        if not self.is_playing:
            self.play_voice()
        else:
            self.stop_voice()

    def play_voice(self):
        try:
            if self.temp_file is None or not os.path.exists(self.temp_file):
                audio_bytes = base64.b64decode(self.voice_data)
                import tempfile
                temp_dir = tempfile.gettempdir()
                self.temp_file = os.path.join(temp_dir, f"temp_voice_{id(self)}.wav")
                with open(self.temp_file, 'wb') as f: f.write(audio_bytes)
            self.audio_player.setSource(QtCore.QUrl.fromLocalFile(self.temp_file))
            self.audio_player.play()
        except Exception as e:
            print(f"Lỗi phát voice: {e}")

    def stop_voice(self):
        self.audio_player.stop()

    def on_position_changed(self, position):
        if self.audio_player.duration() > 0:
            progress = int((position / self.audio_player.duration()) * 100)
            self.progress_bar.setValue(progress)
            seconds = position // 1000
            self.time_label.setText(f"{seconds // 60}:{seconds % 60:02d}")

    def on_duration_changed(self, duration):
        if duration > 0: self.progress_bar.setMaximum(100)

    def on_state_changed(self, state):
        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing = True
            self.play_button.setText("❚❚")
            self.progress_timer.start(100)
        else:
            self.is_playing = False
            self.play_button.setText("▶")
            self.progress_timer.stop()
            if state == QtMultimedia.QMediaPlayer.PlaybackState.StoppedState:
                self.progress_bar.setValue(0)
                self.time_label.setText("0:00")

    def update_progress(self):
        if self.audio_player.duration() > 0:
            pos = self.audio_player.position()
            dur = self.audio_player.duration()
            self.progress_bar.setValue(int((pos / dur) * 100))

    def cleanup(self):
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                if self.audio_player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState: self.audio_player.stop()
                os.remove(self.temp_file)
            except:
                pass


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton: self.clicked.emit()
        super().mousePressEvent(event)


class VideoMessageWidget(QtWidgets.QWidget):
    def __init__(self, video_data_base64, is_self=False, parent=None):
        super().__init__(parent)
        self.video_data = video_data_base64
        self.temp_file = None
        
        self.media_player = QtMultimedia.QMediaPlayer()
        self.audio_output = QtMultimedia.QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Khung Video (Video Container)
        container = QtWidgets.QWidget()
        container.setFixedSize(300, 200)
        container.setStyleSheet("background: black; border-radius: 10px;")
        l = QtWidgets.QVBoxLayout(container)
        l.setContentsMargins(0, 0, 0, 0)
        
        if HAS_VIDEO_WIDGET:
            vw = QtMultimediaWidgets.QVideoWidget()
            l.addWidget(vw)
            self.media_player.setVideoOutput(vw)
        else:
            l.addWidget(QtWidgets.QLabel("No Video Widget", alignment=QtCore.Qt.AlignmentFlag.AlignCenter))
            
        layout.addWidget(container)

        # Khu vực điều khiển (Controls Area)
        controls = QtWidgets.QWidget()
        controls.setFixedWidth(300)
        c_layout = QtWidgets.QHBoxLayout(controls)
        c_layout.setContentsMargins(5, 5, 5, 5)

        self.play_btn = QtWidgets.QPushButton("▶")
        self.play_btn.setFixedSize(30, 30)
        self.play_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.play_btn.setStyleSheet("""
            QPushButton { border: none; font-size: 18px; color: #667eea; background: transparent; }
            QPushButton:hover { color: #5a6fd6; }
        """)
        self.play_btn.clicked.connect(self.toggle)
        c_layout.addWidget(self.play_btn)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #ddd; height: 4px; border-radius: 2px; background: #ddd; }
            QSlider::handle:horizontal { background: #667eea; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #667eea; border-radius: 2px; }
        """)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderPressed.connect(self.pause_for_seek)
        self.slider.sliderReleased.connect(self.end_seek)
        c_layout.addWidget(self.slider)

        layout.addWidget(controls)

        self.media_player.playbackStateChanged.connect(self.update_state)
        self.media_player.positionChanged.connect(self.update_slider)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)
        self.media_player.errorOccurred.connect(self.handle_error)

        self.thumbnail_shown = False
        self.create_temp()

    def create_temp(self):
        import tempfile, hashlib
        try:
            h = hashlib.md5(self.video_data[:100].encode()).hexdigest()
            self.temp_file = os.path.join(tempfile.gettempdir(), f"vid_{h}.mp4")
            if not os.path.exists(self.temp_file):
                with open(self.temp_file, 'wb') as f: f.write(base64.b64decode(self.video_data))
            self.media_player.setSource(QtCore.QUrl.fromLocalFile(self.temp_file))
        except Exception as e:
            print(f"Video Data Error: {e}")

    def handle_media_status(self, status):
        if status == QtMultimedia.QMediaPlayer.MediaStatus.LoadedMedia and not self.thumbnail_shown:
            # Mẹo để hiển thị khung hình đầu tiên
            self.media_player.play()
            QtCore.QTimer.singleShot(150, self.media_player.pause)
            self.thumbnail_shown = True
    
    def handle_error(self):
        err_msg = self.media_player.errorString()
        print(f"Video Error: {err_msg}")
        # Có thể hiện label lỗi, nhưng hiện tại in ra console để debug lỗi dữ liệu

    def toggle(self):
        if self.playback_state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    @property
    def playback_state(self):
        return self.media_player.playbackState()

    def update_state(self, state):
        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")

    def update_slider(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)

    def update_duration(self, duration):
        self.slider.setRange(0, duration)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def pause_for_seek(self):
        self.was_playing = (self.playback_state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState)
        self.media_player.pause()

    def end_seek(self):
        self.set_position(self.slider.value())
        if getattr(self, 'was_playing', False):
            self.media_player.play()

    def cleanup(self):
        self.media_player.stop()
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass


# ====================================================================
# CLASS MAIN VIEW CHÍNH - ĐÃ SỬA LỖI CRASH UI THREAD
# ====================================================================
class MainView(QtWidgets.QMainWindow):
    # Khai báo các tín hiệu để giao tiếp giữa luồng mạng và luồng giao diện
    message_received = QtCore.Signal(str, str, str, int, int, str, bool)  # content, sender_name, message_type, target_id, sender_id, sender_avatar, is_system
    profile_updated_signal = QtCore.Signal(int, str)  # uid, name (không gửi avatar qua signal)
    new_group_signal = QtCore.Signal()
    status_updated_signal = QtCore.Signal(int, str) # uid, status
    signal_received = QtCore.Signal(dict) # Tín hiệu mới cho các sự kiện P2P
    force_logout_signal = QtCore.Signal(str)  # message - Tín hiệu bị đăng xuất từ thiết bị khác

    def __init__(self, app, controller, user_id, display_name):
        super().__init__()
        self.app = app
        self.controller = controller
        self.socket = controller.client_socket
        self.user_id = user_id
        self.display_name = display_name
        self.current_mode = "user"
        self.ai_chat_window = None # Window AI Chat
        self._message_check_running = True  # Flag to control message checking loop

        self.setWindowTitle("Python Chat App")
        self.resize(1100, 750)
        
        # Căn giữa màn hình
        qr = self.frameGeometry()
        cp = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        # UI Setup
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setup_sidebar()
        main_layout.addWidget(self.sidebar_widget)

        # Ngăn xếp nội dung chính (Main Content Stack)
        self.stack = QtWidgets.QStackedWidget()
        
        # --- Trang 0: Chat Cá nhân/Nhóm (Splitter) ---
        self.chat_container = QtWidgets.QWidget()
        self.chat_layout = QtWidgets.QHBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #e0e0e0; }")

        self.setup_user_list()
        self.splitter.addWidget(self.user_list_widget)

        self.setup_chat_area()
        self.splitter.addWidget(self.chat_area_widget)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        
        self.chat_layout.addWidget(self.splitter)
        self.stack.addWidget(self.chat_container) # Index 0

        # --- Trang 1: Chat AI ---
        self.ai_chat_view = AIChatView()
        self.stack.addWidget(self.ai_chat_view) # Index 1
        
        main_layout.addWidget(self.stack)

        # Thiết lập Logic
        self.controller.current_user_id = self.user_id

        # KẾT NỐI TÍN HIỆU (RẤT QUAN TRỌNG ĐỂ KHÔNG BỊ CRASH)
        self.message_received.connect(self.display_incoming_message)
        self.profile_updated_signal.connect(self.handle_profile_update_ui)
        self.status_updated_signal.connect(self.handle_status_update_ui)
        self.new_group_signal.connect(self.load_groups)
        self.signal_received.connect(self.on_signal_received) # Connect new signal
        self.force_logout_signal.connect(self.handle_force_logout)  # Single Session Enforcement

        self.current_receiver_id = None
        self.current_receiver_name = None
        self.self_avatar = None
        self.self_is_invisible = False
        self.user_avatars = {}
        self.user_names = {}  # Cache tên hiển thị của user
        self.user_statuses = {} # Cache trạng thái online/offline
        self.last_active_times = {} # Cache thời gian: user_id -> timestamp string
        self.current_chat_id = None # user_id or group_id
        self.active_call_dialog = None # Theo dõi dialog cuộc gọi đang diễn ra
        self.incoming_dialog = None # Theo dõi dialog cuộc gọi đến

        self.is_recording = False
        self.frames = []
        self.audio = None
        self.stream = None

        # Trạng thái chỉ báo đang nhập
        self.is_typing_active = False
        self.typing_timer = QtCore.QTimer()
        self.typing_timer.setSingleShot(True)
        self.typing_timer.setInterval(3000) # 3 giây
        self.typing_timer.timeout.connect(self.on_typing_timer_timeout)

        self.refresh_self_profile()
        
        self.all_users = []
        self.all_groups = []
        self.load_users()

        threading.Thread(target=self.check_incoming_messages, daemon=True).start()

    # --- UI Setup ---
    def setup_sidebar(self):
        self.sidebar_widget = QtWidgets.QWidget()
        self.sidebar_widget.setFixedWidth(70)
        self.sidebar_widget.setStyleSheet(
            "QWidget { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2); }")
        layout = QtWidgets.QVBoxLayout(self.sidebar_widget)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(15)

        self.btn_chat_one = QtWidgets.QPushButton("💬")
        self.btn_chat_one.setFixedSize(50, 50)
        self.btn_chat_one.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.3); border-radius: 15px; border: 2px solid white; font-size: 24px; }")
        self.btn_chat_one.clicked.connect(self.switch_to_user_mode)
        layout.addWidget(self.btn_chat_one)

        self.btn_chat_group = QtWidgets.QPushButton("👥")
        self.btn_chat_group.setFixedSize(50, 50)
        self.btn_chat_group.setStyleSheet(
            "QPushButton { background-color: transparent; border-radius: 15px; font-size: 24px; color: rgba(255,255,255,0.7); }")
        self.btn_chat_group.clicked.connect(self.switch_to_group_mode)
        layout.addWidget(self.btn_chat_group)

        self.btn_ai_chat = QtWidgets.QPushButton("🤖")
        self.btn_ai_chat.setFixedSize(50, 50)
        self.btn_ai_chat.setToolTip("Gemini AI Assistant")
        self.btn_ai_chat.setStyleSheet(
            "QPushButton { background-color: transparent; border-radius: 15px; font-size: 24px; color: rgba(255,255,255,0.7); }")
        self.btn_ai_chat.clicked.connect(self.open_ai_chat)
        layout.addWidget(self.btn_ai_chat)

        layout.addStretch()

        self.sidebar_avatar = ClickableLabel()
        self.sidebar_avatar.setFixedSize(50, 50)
        self.sidebar_avatar.setStyleSheet(
            "background-color: #ddd; border-radius: 25px; border: 2px solid rgba(255,255,255,0.8);")
        self.sidebar_avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sidebar_avatar.clicked.connect(self.open_profile_dialog)
        layout.addWidget(self.sidebar_avatar)

        self.btn_logout = QtWidgets.QPushButton("⏻")
        self.btn_logout.setFixedSize(50, 50)
        self.btn_logout.setStyleSheet(
            "QPushButton { background-color: transparent; border-radius: 15px; font-size: 20px; color: #ff6b6b; }")
        self.btn_logout.clicked.connect(self.logout)
        layout.addWidget(self.btn_logout)

    def setup_user_list(self):
        self.user_list_widget = QtWidgets.QWidget()
        self.user_list_widget.setMinimumWidth(280) # Ngăn chiều rộng quá nhỏ
        self.user_list_widget.setStyleSheet("background-color: #ffffff;")
        layout = QtWidgets.QVBoxLayout(self.user_list_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        header_container = QtWidgets.QWidget()
        header_container.setStyleSheet("border-bottom: 1px solid #eee; padding: 15px;")
        header_layout = QtWidgets.QHBoxLayout(header_container)

        lbl_title = QtWidgets.QLabel("Tin nhắn")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        self.btn_add_group = QtWidgets.QPushButton("+")
        self.btn_add_group.setFixedSize(30, 30)
        self.btn_add_group.setStyleSheet(
            "QPushButton { background-color: #667eea; color: white; border-radius: 15px; font-weight: bold; font-size: 18px; }")
        self.btn_add_group.clicked.connect(self.open_create_group_dialog)
        self.btn_add_group.hide()
        header_layout.addWidget(self.btn_add_group)
        layout.addWidget(header_container)

        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Tìm kiếm...")
        self.search_box.setStyleSheet(
            "QLineEdit { border: 1px solid #ddd; border-radius: 15px; padding: 5px 10px; background-color: #f8f9fa; margin: 10px; color: #000000; }")
        self.search_box.textChanged.connect(self.on_search_text_changed)
        layout.addWidget(self.search_box)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Tắt thanh cuộn ngang
        scroll_area.setStyleSheet("border: none; background: white;")
        scroll_content = QtWidgets.QWidget()
        self.chat_list_layout = QtWidgets.QVBoxLayout(scroll_content)
        self.chat_list_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_list_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def setup_chat_area(self):
        self.chat_area_widget = QtWidgets.QWidget()
        self.chat_area_widget.setStyleSheet("background-color: #f5f6fa;")
        layout = QtWidgets.QVBoxLayout(self.chat_area_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_header = QtWidgets.QWidget()
        self.chat_header.setFixedHeight(65)
        self.chat_header.setStyleSheet("background-color: white; border-bottom: 1px solid #ddd;")
        h_layout = QtWidgets.QHBoxLayout(self.chat_header)
        h_layout.setContentsMargins(15, 5, 15, 5)

        # Container cho Text (Name + Status)
        text_container = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout(text_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)

        self.header_name_label = QtWidgets.QLabel("Chọn một người để chat")
        self.header_name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        v_layout.addWidget(self.header_name_label)

        self.header_status_label = QtWidgets.QLabel("")
        self.header_status_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        self.header_status_label.hide() # Ẩn mặc định
        v_layout.addWidget(self.header_status_label)

        h_layout.addWidget(text_container)
        
        h_layout.addStretch()
        
        # Nút Gọi (Trên cùng bên phải)
        self.btn_call_header = QtWidgets.QPushButton("📞")
        self.btn_call_header.setFixedSize(40, 40)
        self.btn_call_header.setStyleSheet("""
            QPushButton { background-color: #f0f2f5; border-radius: 20px; font-size: 20px; color: #667eea; border: none; }
            QPushButton:hover { background-color: #e4e6eb; }
        """)
        self.btn_call_header.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_call_header.clicked.connect(self.start_call)
        h_layout.addWidget(self.btn_call_header)

        # Nút Thêm Thành Viên
        self.btn_add_member = QtWidgets.QPushButton("➕")
        self.btn_add_member.setFixedSize(40, 40)
        self.btn_add_member.setToolTip("Thêm thành viên")
        self.btn_add_member.setStyleSheet("QPushButton { background-color: #f0f2f5; border-radius: 20px; font-size: 18px; border: none; } QPushButton:hover { background-color: #e4e6eb; }")
        self.btn_add_member.clicked.connect(self.add_member_to_group)
        self.btn_add_member.hide()
        h_layout.addWidget(self.btn_add_member)

        # Nút Rời Nhóm
        self.btn_leave_group = QtWidgets.QPushButton("🚪")
        self.btn_leave_group.setFixedSize(40, 40)
        self.btn_leave_group.setToolTip("Rời nhóm")
        self.btn_leave_group.setStyleSheet("QPushButton { background-color: #ffebee; border-radius: 20px; font-size: 18px; color: #d32f2f; border: none; } QPushButton:hover { background-color: #ffcdd2; }")
        self.btn_leave_group.clicked.connect(self.leave_group)
        self.btn_leave_group.hide()
        h_layout.addWidget(self.btn_leave_group)

        # Nút Xem Thành Viên (Mới)
        self.btn_view_members = QtWidgets.QPushButton("📜")
        self.btn_view_members.setFixedSize(40, 40)
        self.btn_view_members.setToolTip("Xem danh sách thành viên")
        self.btn_view_members.setStyleSheet("QPushButton { background-color: #f0f2f5; border-radius: 20px; font-size: 18px; border: none; } QPushButton:hover { background-color: #e4e6eb; }")
        self.btn_view_members.clicked.connect(self.view_group_members)
        self.btn_view_members.hide()
        h_layout.addWidget(self.btn_view_members)


        layout.addWidget(self.chat_header)

        self.chat_scroll = QtWidgets.QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        # Kiểu thanh cuộn tùy chỉnh (Hiệu ứng Overlay/Hover)
        self.chat_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.1); 
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.4); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.chat_content = QtWidgets.QWidget()
        self.chat_messages_layout = QtWidgets.QVBoxLayout(self.chat_content)
        self.chat_messages_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_messages_layout.setSpacing(15)
        self.chat_messages_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_content)
        layout.addWidget(self.chat_scroll)

        # Nhãn chỉ báo đang nhập (Typing Indicator Label)
        self.typing_label = QtWidgets.QLabel("")
        self.typing_label.setStyleSheet("font-style: italic; color: #7f8c8d; font-size: 12px; margin-left: 20px; margin-bottom: 5px;")
        self.typing_label.hide()
        layout.addWidget(self.typing_label)

        input_container = QtWidgets.QWidget()
        input_container.setStyleSheet("background-color: white; border-top: 1px solid #ddd;")
        input_container.setFixedHeight(70)
        inp_layout = QtWidgets.QHBoxLayout(input_container)

        self.btn_img = self._create_icon_button("🖼", "#667eea", "Gửi ảnh")
        self.btn_img.clicked.connect(self.send_image)
        inp_layout.addWidget(self.btn_img)
        self.btn_vid = self._create_icon_button("🎬", "#8e44ad", "Gửi video")
        self.btn_vid.clicked.connect(self.send_video)
        inp_layout.addWidget(self.btn_vid)
        
        # Nút Gọi đã bị xóa khỏi đây
        # self.btn_call = self._create_icon_button("📞", "#2ecc71", "Gọi điện")
        # self.btn_call.clicked.connect(self.start_call)
        # inp_layout.addWidget(self.btn_call)

        self.btn_mic = self._create_icon_button("🎤", "#ff6b6b", "Giữ để ghi âm")
        self.btn_mic.pressed.connect(self.start_recording)
        self.btn_mic.released.connect(self.stop_recording)
        inp_layout.addWidget(self.btn_mic)

        self.message_input = QtWidgets.QLineEdit()
        self.message_input.setPlaceholderText("Nhập tin nhắn @...")
        self.message_input.setStyleSheet(
            "QLineEdit { border: none; background-color: #f0f2f5; border-radius: 20px; padding: 10px 15px; font-size: 14px; color: #000000; }")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.textChanged.connect(self.handle_typing_input)
        inp_layout.addWidget(self.message_input)

        self.btn_emoji = self._create_icon_button("😊", "#f39c12", "Emoji")
        self.btn_emoji.clicked.connect(self.show_emoji_picker)
        inp_layout.addWidget(self.btn_emoji)
        self.btn_send = self._create_icon_button("✈", "#00b894", "Gửi")
        self.btn_send.clicked.connect(self.send_message)
        inp_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

    def _create_icon_button(self, text, color, tooltip):
        btn = QtWidgets.QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(40, 40)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {color}; font-size: 20px; border-radius: 20px; }} QPushButton:hover {{ background-color: {color}20; }}")
        return btn

    # --- Logic ---
    def switch_to_user_mode(self):
        self.current_mode = "user"
        self._clear_chat_ui() # Xóa trạng thái chat
        self.stack.setCurrentIndex(0) # Chuyển sang chat thường
        self.btn_chat_one.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.3); border-radius: 15px; border: 2px solid white; font-size: 24px;")
        self.btn_chat_group.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")
        self.btn_ai_chat.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")
        self.btn_add_group.hide()
        self.btn_add_group.hide()
        self.header_name_label.setText("Chọn một người để chat")
        self.header_status_label.hide()
        if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
        self.load_users()

    def switch_to_group_mode(self):
        self.current_mode = "group"
        self._clear_chat_ui() # Xóa trạng thái chat
        self.stack.setCurrentIndex(0) # Chuyển sang chat thường
        self.btn_chat_group.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.3); border-radius: 15px; border: 2px solid white; font-size: 24px;")
        self.btn_chat_one.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")
        self.btn_ai_chat.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")
        self.btn_add_group.show()
        self.btn_add_group.show()
        self.header_name_label.setText("Chọn một nhóm để chat")
        self.header_status_label.hide()
        if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
        if hasattr(self, 'btn_add_member'): self.btn_add_member.hide() # Ban đầu ẩn, chỉ hiện khi chọn
        if hasattr(self, 'btn_leave_group'): self.btn_leave_group.hide()
        self.load_groups()

    def _clear_chat_ui(self):
        self.current_receiver_id = None
        self.current_receiver_name = None
        self.current_chat_id = None
        if hasattr(self, 'typing_label'): self.typing_label.hide()
        # Xóa tin nhắn cũ
        for i in reversed(range(self.chat_messages_layout.count())):
            item = self.chat_messages_layout.itemAt(i)
            if item.widget():
                w = item.widget()
                if hasattr(w, 'cleanup'): w.cleanup()
                w.deleteLater()

    def open_create_group_dialog(self):
        all_users = [u for u in self.controller.get_users() if u['user_id'] != self.user_id]
        dialog = CreateGroupDialog(self, all_users)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name, member_ids = dialog.get_data()
            resp = self.controller.create_group(name, member_ids)
            if resp.get("status") == "success":
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã tạo nhóm '{name}'")
                self.load_groups()
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", resp.get("message", "Lỗi không xác định"))

    @QtCore.Slot()
    def open_ai_chat(self):
        self.stack.setCurrentIndex(1) # Chuyển sang chat AI
        self.btn_ai_chat.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.3); border-radius: 15px; border: 2px solid white; font-size: 24px;")
        self.btn_chat_one.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")
        self.btn_chat_group.setStyleSheet("background-color: transparent; border: none; font-size: 24px;")


    @QtCore.Slot()
    def load_groups(self):
        try:
            self.all_groups = self.controller.get_groups() # Cache nhóm
            self.update_list_display(self.search_box.text())
        except Exception as e:
            print(f"Lỗi load groups: {e}")

    @QtCore.Slot()
    def load_users(self):
        try:
            # Cache tất cả user
            self.all_users = self.controller.get_users()
            self.user_avatars = {}
            self.user_names = {}
            self.user_statuses = {}
            self.last_active_times = {}
            for user in self.all_users:
                uid = user["user_id"]
                self.user_avatars[uid] = user.get("avatar")
                self.user_names[uid] = user.get("display_name")
                self.user_statuses[uid] = user.get("status", "offline")
                self.last_active_times[uid] = user.get("last_active_at") # Store timestamp
            
            self.update_list_display(self.search_box.text())
        except Exception as e:
            print(f"Lỗi load users: {e}")

    def on_search_text_changed(self, text):
        self.update_list_display(text)

    def highlight_text(self, text, query):
        if not query: return text
        # Regex để highlight đơn giản
        try:
             # Thay thế không phân biệt chữ hoa chữ thường nhưng giữ nguyên text gốc
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            return pattern.sub(lambda m: f"<span style='color: #2980b9; font-weight: 900;'>{m.group(0)}</span>", text)
        except:
             return text

    def update_list_display(self, filter_text=""):
        # Xóa danh sách hiện tại
        while self.chat_list_layout.count() > 0:
            item = self.chat_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        self.chat_list_layout.addStretch() # Đảm bảo stretch ở cuối (đã xóa và thêm lại logic bên dưới)
        # Actually stretch should be at bottom, let's just clear widgets and append.
        # But we need to keep layout logic. The original had addStretch at the beginning??
        # Checked `setup_user_list`: `self.chat_list_layout.addStretch()` was added initially.
        # Let's just remove all and add items then add stretch.
        
        # Xác định nguồn dữ liệu
        source_list = self.all_groups if self.current_mode == "group" else self.all_users
        
        count = 0
        for item_data in source_list:
            if self.current_mode == "group":
                uid = item_data["id"]
                name = item_data["name"]
                avatar = item_data.get("avatar")
                last_msg = item_data.get("last_message", "Chạm để chat nhóm")
                item_type = "group"
            else:
                uid = item_data["user_id"]
                if uid == self.user_id: continue # Bỏ qua chính mình
                name = item_data["display_name"]
                avatar = item_data.get("avatar")
                last_msg = "Nhấn để xem tin nhắn"
                item_type = "user"

            # Bộ lọc
            if filter_text and filter_text.lower() not in name.lower():
                continue
            
            # Highlight tên
            display_name_html = self.highlight_text(name, filter_text)
            
            # Tạo Item
            # Modified ChatListItem needed?
            # ChatListItem takes display_name string and puts it in QLabel.
            # QLabel supports rich text if we pass it properly.
            
            # Sử dụng cách tiếp cận sửa đổi nhẹ: Truyền HTML vào ChatListItem?
            # It uses `QtWidgets.QLabel(display_name)` -> We can setText with HTML.
            
            widget = ChatListItem(uid, display_name_html, last_msg, avatar, item_type=item_type)
            # Cập nhật trạng thái online nếu có trong cache
            if item_type == "user":
                 is_online = (self.user_statuses.get(uid) == "online")
                 widget.set_online(is_online)
            
            widget.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            widget.mousePressEvent = lambda e, u=uid, n=name: self.select_chat_by_id(u, n, item_type)
            
            self.chat_list_layout.insertWidget(self.chat_list_layout.count() - 1, widget)
            count += 1
            
        if count == 0 and filter_text:
             lbl = QtWidgets.QLabel("Không tìm thấy kết quả.")
             lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
             lbl.setStyleSheet("color: #999; margin-top: 20px;")
             self.chat_list_layout.insertWidget(0, lbl)
        elif count == 0 and self.current_mode == "group" and not filter_text:
             lbl = QtWidgets.QLabel("Bạn chưa có nhóm nào.\nHãy tạo nhóm mới!")
             lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
             lbl.setStyleSheet("color: #7f8c8d; margin-top: 20px;")
             self.chat_list_layout.insertWidget(0, lbl)

    def select_chat_by_id(self, target_id, display_name, item_type="user"):
        self.current_receiver_id = target_id
        self.current_receiver_name = display_name
        self.current_chat_id = target_id # Set current chat ID
        self.current_mode = item_type # Set current mode

        icon = "👥" if item_type == "group" else "💬"
        self.header_name_label.setText(f"{icon} {display_name}")
        
        # Cập nhật trạng thái hiển thị trên Header (chỉ cho mode user)
        if item_type == "user":
            status = self.user_statuses.get(target_id, "offline")
            self.update_header_status_display(target_id, status)
        else:
            self.header_status_label.hide()


        # Ẩn nút gọi cho logic nhóm
        if item_type == "group":
            if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
            if hasattr(self, 'btn_add_member'): self.btn_add_member.show()
            if hasattr(self, 'btn_view_members'): self.btn_view_members.show()
            if hasattr(self, 'btn_leave_group'): self.btn_leave_group.show()
        else:
            if hasattr(self, 'btn_call_header'): self.btn_call_header.show()
            if hasattr(self, 'btn_add_member'): self.btn_add_member.hide()
            if hasattr(self, 'btn_view_members'): self.btn_view_members.hide()
            if hasattr(self, 'btn_leave_group'): self.btn_leave_group.hide()

        for i in reversed(range(self.chat_messages_layout.count())):
            item = self.chat_messages_layout.itemAt(i)
            if item.widget():
                w = item.widget()
                if hasattr(w, 'cleanup'): w.cleanup()
                w.deleteLater()

        try:
            if item_type == "user":
                history = self.controller.get_chat_history(target_id)
            else:
                history = self.controller.get_group_chat_history(target_id)

            for msg in history:
                is_self = (msg.get("sender_id") == self.user_id)
                sender_id = msg.get("sender_id")
                
                if is_self:
                    name = "Bạn"
                    avatar = self.self_avatar
                else:
                    # Ưu tiên lấy từ cache (đã được cập nhật) nếu có
                    if sender_id and sender_id in self.user_names:
                        name = self.user_names[sender_id]
                    else:
                        # Lấy từ message (server đã query từ DB nên sẽ có tên mới nhất)
                        name = msg.get("sender_name", "Unknown")
                        # Lưu vào cache
                        if sender_id:
                            self.user_names[sender_id] = name
                    
                    if sender_id and sender_id in self.user_avatars:
                        avatar = self.user_avatars[sender_id]
                    else:
                        # Lấy từ message
                        avatar = msg.get("sender_avatar")
                        # Lưu vào cache
                        if sender_id:
                            self.user_avatars[sender_id] = avatar

                if msg.get("is_image"):
                    self.add_message_to_chat(msg["image_data"], name, is_self, is_image=True, avatar_base64=avatar)
                elif msg.get("is_voice"):
                    self.add_message_to_chat(msg["voice_data"], name, is_self, is_voice=True, avatar_base64=avatar)
                elif msg.get("is_video"):
                    self.add_message_to_chat(msg["video_data"], name, is_self, is_video=True, avatar_base64=avatar)
                elif msg.get("is_call_log"): 
                    self.add_message_to_chat(msg["message"], name, is_self, is_call_log=True, avatar_base64=avatar)
                elif msg.get("is_system"):
                     self.add_system_message(msg["message"])
                else:
                    self.add_message_to_chat(msg["message"], name, is_self, avatar_base64=avatar)
            
            # Buộc cuộn xuống dưới cùng sau khi cập nhật layout
            QtCore.QTimer.singleShot(100, self.scroll_to_bottom)

        except Exception as e:
            print(f"Lỗi load history: {e}")

    def scroll_to_bottom(self):
        js = self.chat_scroll.verticalScrollBar()
        js.setValue(js.maximum())

    def add_message_to_chat(self, message, sender_name, is_self=False, is_image=False, is_voice=False, is_video=False, is_call_log=False,
                            avatar_base64=None):
        try:
            bubble = self.create_message_bubble(message, sender_name, is_self, is_image, is_voice, is_video, is_call_log,
                                                avatar_base64)
            self.chat_messages_layout.insertWidget(self.chat_messages_layout.count() - 1, bubble)
            QtCore.QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()))
        except Exception as e:
            print(f"Lỗi add msg: {e}")

    def create_message_bubble(self, message, sender_name, is_self, is_image, is_voice, is_video, is_call_log, avatar_base64):
        bubble_widget = QtWidgets.QWidget()
        bubble_layout = QtWidgets.QHBoxLayout(bubble_widget)
        bubble_layout.setContentsMargins(0, 5, 0, 5) # Increased margins
        
        # STYLE TIN NHẮN HỆ THỐNG / NHẬT KÝ CUỘC GỌI
        if is_call_log:
            lbl = QtWidgets.QLabel(message)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("""
                font-size: 11px; 
                background-color: #ecf0f1; 
                padding: 4px 12px; 
                border-radius: 10px;
                margin-top: 5px;
                margin-bottom: 5px;
            """)
            
            # Màu sắc và Icon dựa trên nội dung
            txt = message.strip()
            # Nếu text CHÍNH XÁC là "Cuộc gọi thoại", nghĩa là Từ chối/Nhỡ (Không có thời lượng)
            if txt == "Cuộc gọi thoại":
                lbl.setText(f"📞 ❌ {txt}")
                lbl.setStyleSheet(lbl.styleSheet() + "color: #e74c3c; font-style: italic;") # Red
            
            # Nếu text bắt đầu bằng "Cuộc gọi thoại" và có xuống dòng (Thông tin thời lượng), nghĩa là Đã kết thúc
            elif txt.startswith("Cuộc gọi thoại\n"):
                lbl.setText(f"📞 {txt}")
                lbl.setStyleSheet(lbl.styleSheet() + "color: #2c3e50; font-weight: bold;") # Dark Blue
            
            # Dự phòng (Log cũ hoặc tin nhắn hệ thống khác)
            else:
                if "từ chối" in txt.lower() or "nhỡ" in txt.lower():
                     lbl.setText(f"📞 ❌ {txt}")
                     lbl.setStyleSheet(lbl.styleSheet() + "color: #e74c3c; font-style: italic;")
                else:
                     lbl.setStyleSheet(lbl.styleSheet() + "color: #7f8c8d; font-style: italic;")

            bubble_layout.addStretch()
            bubble_layout.addWidget(lbl)
            bubble_layout.addStretch()
            return bubble_widget

        # Style tin nhắn thường
        bubble_layout.setSpacing(10)
        avatar = QtWidgets.QLabel()
        avatar.setFixedSize(35, 35)
        avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if avatar_base64:
            try:
                p = QtGui.QPixmap()
                p.loadFromData(base64.b64decode(avatar_base64))
                # Tạo pixmap tròn
                rounded = QtGui.QPixmap(35, 35)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 35, 35)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, p.scaled(35, 35, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                avatar.setPixmap(rounded)
                avatar.setStyleSheet("background-color: transparent;")
            except:
                avatar.setText("👤")
                avatar.setStyleSheet("border-radius: 17px; background-color: #ddd;")
        else:
            avatar.setText("👤")
            avatar.setStyleSheet("border-radius: 17px; background-color: #ddd;")
        content_wrapper = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        if not is_self:
            lbl_name = QtWidgets.QLabel(sender_name)
            lbl_name.setStyleSheet("font-size: 10px; color: #888; margin-left: 5px;")
            content_layout.addWidget(lbl_name)
        if is_voice:
            msg_widget = VoiceMessageWidget(message, is_self)
            msg_widget.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {'#667eea' if is_self else '#fff'}, stop:1 {'#764ba2' if is_self else '#fff'}); border-radius: 15px; border: 1px solid {'#667eea' if is_self else '#ddd'};")
            content_layout.addWidget(msg_widget)
        elif is_video:
            msg_widget = VideoMessageWidget(message, is_self)
            content_layout.addWidget(msg_widget)
        elif is_image:
            lbl_img = QtWidgets.QLabel()
            try:
                p = QtGui.QPixmap()
                p.loadFromData(base64.b64decode(message))
                lbl_img.setPixmap(p.scaled(250, 250, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
            except:
                lbl_img.setText("Lỗi ảnh")
            lbl_img.setStyleSheet("border-radius: 10px;")
            content_layout.addWidget(lbl_img)
        else:
            lbl_msg = QtWidgets.QLabel(message)
            lbl_msg.setWordWrap(True)
            lbl_msg.setStyleSheet(
                f"background-color: {'#667eea' if is_self else 'white'}; color: {'white' if is_self else 'black'}; padding: 10px 15px; border-radius: 15px; border: 1px solid {'#667eea' if is_self else '#ddd'};")
            lbl_msg.setMaximumWidth(400)
            content_layout.addWidget(lbl_msg)
        if is_self:
            bubble_layout.addStretch()
            bubble_layout.addWidget(content_wrapper)
        else:
            bubble_layout.addWidget(avatar, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
            bubble_layout.addWidget(content_wrapper)
            bubble_layout.addStretch()
        return bubble_widget

    def add_system_message(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #95a5a6; font-size: 11px; font-style: italic; margin: 10px;")
        self.chat_messages_layout.insertWidget(self.chat_messages_layout.count() - 1, lbl)

    def send_message(self):
        msg = self.message_input.text().strip()
        
        # Dừng typing ngay lập tức khi gửi
        if self.is_typing_active:
             self.typing_timer.stop()
             self.on_typing_timer_timeout()

        if not msg or not self.current_receiver_id: return
        try:
            if self.current_mode == "user":
                resp = self.controller.send_message(self.current_receiver_id, msg)
            else:
                resp = self.controller.send_group_message(self.current_receiver_id, msg)
            if resp and resp.get("status") == "success":
                self.add_message_to_chat(msg, "Bạn", True, avatar_base64=self.self_avatar)
                self.message_input.clear()
        except Exception as e:
            print(e)

    def send_image(self):
        if not self.current_receiver_id: return
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Image Files (*.png *.jpg)")
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                if self.current_mode == "user":
                    self.controller.send_image(self.current_receiver_id, data, os.path.basename(file_path))
                    self.add_message_to_chat(data, "Bạn", True, is_image=True, avatar_base64=self.self_avatar)
                else:
                    self.controller.send_group_message(self.current_receiver_id, "", is_image=True, image_data=data)
            except Exception as e:
                print(e)

    def send_video(self):
        if not self.current_receiver_id: return
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn video", "", "Video (*.mp4 *.avi)")
        if file_path:
            # Kiểm tra giới hạn kích thước (50MB)
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:
                QtWidgets.QMessageBox.warning(self, "File quá lớn", "Video không được vượt quá 50MB để đảm bảo tốc độ.")
                return

            try:
                with open(file_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                self.controller.send_video(self.current_receiver_id, data, os.path.basename(file_path))
                self.add_message_to_chat(data, "Bạn", True, is_video=True, avatar_base64=self.self_avatar)
            except Exception as e:
                print(e)
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể gửi video: {e}")

    def start_call(self):
        if not self.current_receiver_id:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn người để gọi.")
            return
        
        # 1. Hiện ActiveCallDialog (Trạng thái Người gọi)
        self.active_call_dialog = ActiveCallDialog(self.current_receiver_name, self.user_avatars.get(self.current_receiver_id), is_caller=True, parent=self)
        self.active_call_dialog.hangup_signal.connect(lambda: self.end_call_remote(self.current_receiver_id))
        self.active_call_dialog.show()
        
        # 2. Gửi yêu cầu gọi
        self.controller.send_signal(self.current_receiver_id, "call_request", {
            "caller_name": self.display_name,
            "caller_avatar": self.self_avatar
        })

    def send_call_signal(self, signal_type, data=None):
        if self.current_receiver_id:
            self.controller.send_signal(self.current_receiver_id, signal_type, data)

    def on_signal_received(self, msg):
        signal_type = msg.get("signal_type")
        sender_id = msg.get("sender_id")
        
        if signal_type == "call_request":
            # Hiện Dialog cuộc gọi đến
            caller_name = msg.get("caller_name", "Unknown")
            caller_avatar = msg.get("caller_avatar")
            
            self.incoming_dialog = IncomingCallDialog(caller_name, caller_avatar, parent=self)
            
            # Kết nối tín hiệu
            self.incoming_dialog.accept_signal.connect(lambda: self.accept_call(sender_id, caller_name, caller_avatar))
            self.incoming_dialog.reject_signal.connect(lambda: self.reject_call(sender_id))
            
            self.incoming_dialog.show()

        elif signal_type == "call_accepted":
            if self.active_call_dialog:
                self.active_call_dialog.start_timer()

        elif signal_type == "call_rejected":
            if self.active_call_dialog:
                self.active_call_dialog.close()
                self.active_call_dialog = None
                QtWidgets.QMessageBox.information(self, "Cuộc gọi", "Người gọi đang bận.")
                
                # Ghi log cuộc gọi nhỡ cục bộ (Phía người gọi)
                # Khớp format cho cuộc gọi bị từ chối (Chuỗi chính xác)
                # msg_content = "Cuộc gọi thoại"
                # self.add_message_to_chat(msg_content, "Bạn", is_self=True, is_call_log=True, avatar_base64=self.self_avatar)
                pass


        elif signal_type == "call_ended":
            duration = "00:00"
            if self.active_call_dialog:
                duration = self.active_call_dialog.timer_lbl.text()
                self.active_call_dialog.close()
                self.active_call_dialog = None
            
            if hasattr(self, 'incoming_dialog') and self.incoming_dialog and self.incoming_dialog.isVisible():
                self.incoming_dialog.close()
            
            # Ghi log cuộc gọi kết thúc
            # Log call ended
            # "call_ended" được gửi bởi người dập máy.
            # The one who hangs up should be the one to save the log to DB?
            # Or both?
            # Hãy giữ nguyên: Hành động "Dập máy" kích hoạt lưu log.
            # Tín hiệu "call_ended" chỉ đóng UI.
            # Tin nhắn log sẽ đến qua kênh tin nhắn chuẩn.
            pass

        elif signal_type == "typing":
            # Kiểm tra xem tín hiệu này có phải từ người mình đang chat không
            target_sender_id = sender_id
            
            # Note: Với chat nhóm, logic có thể khác (ai đang gõ?), nhưng hiện tại đơn giản nhất:
            # Nếu chat User chuẩn:
            if self.current_mode == "user" and self.current_receiver_id == target_sender_id:
                is_typing = msg.get("is_typing", False)
                if is_typing:
                    self.typing_label.setText(f"{self.current_receiver_name} đang soạn tin...")
                    self.typing_label.show()
                else:
                    self.typing_label.hide()
            
            # Nếu xử lý chat nhóm (Mở rộng tùy chọn):
            # If we receive a typing signal in a group context (depends on if server relays it with group_id or just sender_id)
            # Current server relays signal with sender_id. 
            # If we are in a group, and one of the members sends a typing signal...
            # The signal mechanism in chat_mixin.py sends to 'receiver_id'. 
            # If it's a group, we are sending to the group_id?
            # Server handles signal relay by looking up 'target_id' in 'user_sockets'. 
            # Groups are NOT in user_sockets. 
            # So, currently this typing indicator ONLY works for 1-1 Chat because signal routing is user-to-user.
            # That fits the "Client-Server Chat Application... without modifying core database" constraint perfectly
            # as supporting group typing would require server logic change to broadcast signal to group members.
            pass

    def handle_typing_input(self, text):
        if not self.current_receiver_id: return
        # Chỉ hỗ trợ typing 1-1 hiện tại do giới hạn tín hiệu server (target_id phải là user socket)
        if self.current_mode != "user": return

        if not self.is_typing_active and text:
            self.is_typing_active = True
            self.controller.send_typing_status(self.current_receiver_id, True)
            self.typing_timer.start()
        elif self.is_typing_active:
             if not text: # Cleared text
                 self.typing_timer.stop()
                 self.on_typing_timer_timeout()
             else:
                 # Debounce: Restart timer
                 self.typing_timer.start()

    def on_typing_timer_timeout(self):
        self.is_typing_active = False
        if self.current_receiver_id and self.current_mode == "user":
            self.controller.send_typing_status(self.current_receiver_id, False)

    def accept_call(self, sender_id, name, avatar):
        # 1. Đóng Dialog cuộc gọi đến (được xử lý bởi class)
        # 2. Hiện Dialog đang gọi
        self.active_call_dialog = ActiveCallDialog(name, avatar, is_caller=False, parent=self)
        self.active_call_dialog.start_timer()
        self.active_call_dialog.show()
        
        # 3. Gửi tín hiệu chấp nhận
        self.controller.send_signal(sender_id, "call_accepted")
        
        # Xử lý dập máy
        self.active_call_dialog.hangup_signal.connect(lambda: self.end_call_remote(sender_id))

    def reject_call(self, sender_id):
        self.controller.send_signal(sender_id, "call_rejected")
        # Ghi log nhỡ (Từ chối) - Cái này lưu vào DB cho cả hai
        # Dùng chuỗi chính xác "Cuộc gọi thoại" để biểu thị từ chối/nhỡ
        self.controller.send_call_log(sender_id, "Cuộc gọi thoại")
        # Thêm log cục bộ cho bản thân
        self.add_message_to_chat("Cuộc gọi thoại", "Bạn", is_self=True, is_call_log=True, avatar_base64=self.self_avatar)

    def end_call_remote(self, target_id):
        # Tôi đang dập máy.
        duration = self.active_call_dialog.timer_lbl.text()
        
        # Tính thời gian bắt đầu (Hiện tại - thời lượng) một cách tương đối, hoặc dùng Giờ hiện tại làm "Giờ kết thúc cuộc gọi"
        import datetime
        now = datetime.datetime.now().strftime("%H:%M")
        
        # Kiểm tra xem cuộc gọi có thực sự kết nối không (duration > 00:00)
        # Nếu 00:00, nghĩa là Người gọi hủy hoặc Người nhận từ chối trước khi Trả lời
        if duration == "00:00":
             log_msg = "Cuộc gọi thoại" # Triggers Red X logic
        else:
             # Msg format: "Cuộc gọi thoại\n[Time] - [Duration]"
             log_msg = f"Cuộc gọi thoại\n{now} - {duration}"
        
        # 1. Thông báo cho đối phương đóng UI
        self.controller.send_signal(target_id, "call_ended")
        
        # 2. Lưu log vào DB và User B
        self.controller.send_call_log(target_id, log_msg)
        
        # 3. Hiện log cục bộ (User A)
        self.add_message_to_chat(log_msg, "Bạn", is_self=True, is_call_log=True, avatar_base64=self.self_avatar)


    # === CÁC SLOT TÍN HIỆU AN TOÀN VỚI THREAD (THREAD-SAFE SIGNAL SLOTS) ===
    def check_incoming_messages(self):
        while self._message_check_running:
            try:
                # Check if controller is still running
                if not self.controller or not self.controller.running:
                    print("[DEBUG] Controller stopped, exiting message check loop")
                    break
                msg = self.controller.get_incoming_message(0.5)
                if msg:
                    action = msg.get("action")

                    if action == "profile_update_notification":
                        updated_uid = msg.get("user_id")
                        new_name = msg.get("display_name")
                        # KHÔNG lấy avatar từ notification (để tránh crash)
                        # Avatar sẽ được fetch lại từ get_users
                        # EMIT SIGNAL (KHÔNG GỌI HÀM UI TRỰC TIẾP)
                        self.profile_updated_signal.emit(updated_uid, new_name)
                        continue

                    if action == "new_group":
                        self.new_group_signal.emit()
                        continue

                    if action == "signal":
                        self.signal_received.emit(msg)
                        continue

                    if action == "user_status_update":
                        uid = msg.get("user_id")
                        status = msg.get("status")
                        last_active = msg.get("last_active_at")
                        if uid is not None and status is not None:
                            # Update cache directly here since we have last_active_at
                            self.last_active_times[int(uid)] = last_active
                            self.status_updated_signal.emit(int(uid), str(status))
                        continue

                    # === SINGLE SESSION ENFORCEMENT ===
                    if action == "force_logout":
                        print(f"[DEBUG] Received force_logout: {msg}")
                        logout_message = msg.get("message", "Bạn đã bị đăng xuất.")
                        self.force_logout_signal.emit(logout_message)
                        print("[DEBUG] force_logout_signal emitted, breaking loop")
                        break  # Thoát vòng lặp nghe tin

                    sender_id = msg.get('sender_id')
                    group_id = msg.get('group_id')
                    t = 'text'
                    content = msg.get('message', '')
                    if msg.get('is_image'):
                        t = 'image'; content = msg.get('image_data')
                    elif msg.get('is_voice'):
                        t = 'voice'; content = msg.get('voice_data')
                    elif msg.get('is_video'):
                        t = 'video'; content = msg.get('video_data')
                    elif msg.get('is_call_log'):
                        t = 'call_log'
                    
                    sender_name = msg.get('sender_name', 'Unknown')
                    sender_avatar = msg.get('sender_avatar')  # Lấy avatar từ message
                    
                    # Cập nhật cache ngay khi nhận tin nhắn mới
                    if sender_id:
                        if sender_name and sender_name != 'Unknown':
                            self.user_names[sender_id] = sender_name
                        if sender_avatar:
                            self.user_avatars[sender_id] = sender_avatar

                    if sender_id == self.user_id: continue

                    should_display = False
                    target_id_for_signal = sender_id
                    if group_id:
                        target_id_for_signal = group_id
                        if self.current_mode == "group" and self.current_receiver_id == group_id:
                            should_display = True
                    else:
                        if self.current_mode == "user" and self.current_receiver_id == sender_id:
                            should_display = True

                    is_system = msg.get('is_system', False)

                    if should_display:
                        # Truyền cả sender_id và sender_avatar để hiển thị đúng
                        self.message_received.emit(content, sender_name, t, target_id_for_signal, sender_id, sender_avatar, is_system)
            except Exception as e:
                if self._message_check_running:
                    print(f"Error checking messages: {e}")
                break
        print("[DEBUG] Message check loop exited")

    # === SINGLE SESSION ENFORCEMENT: Xử lý khi bị kick từ thiết bị khác ===
    @QtCore.Slot(str)
    def handle_force_logout(self, message):
        """Xử lý khi tài khoản đăng nhập từ thiết bị khác."""
        # Dừng các thread/timer
        self._message_check_running = False
        
        # Hiển thị thông báo chặn màn hình
        QtWidgets.QMessageBox.warning(
            self,
            "Phiên đăng nhập kết thúc",
            message
        )
        
        # Đóng socket và cleanup
        if self.controller:
            try:
                self.controller.stop()
            except:
                pass
        
        # Close AI window if open
        if self.ai_chat_window:
            try:
                self.ai_chat_window.close()
            except:
                pass
            self.ai_chat_window = None
        
        # Quay về màn hình Login
        self.app.show_login()
        self.close()

    @QtCore.Slot(int, str)
    def handle_profile_update_ui(self, user_id, display_name):
        # Hàm này chạy trên MAIN THREAD -> An toàn để cập nhật UI
        # Avatar sẽ được fetch lại từ get_users, không lấy từ notification
        try:
            # 1. Cập nhật sidebar nếu là bản thân
            if user_id == self.user_id:
                self.display_name = display_name
                # Refresh profile của chính mình để lấy avatar mới
                self.refresh_self_profile()

            # 2. Cập nhật cache user_avatars và user_names
            # Fetch lại danh sách user để cập nhật avatar và tên cache
            try:
                users = self.controller.get_users()
                for user in users:
                    uid = user["user_id"]
                    self.user_avatars[uid] = user.get("avatar")
                    self.user_names[uid] = user.get("display_name")
                    self.user_statuses[uid] = user.get("status", "offline")
                    self.last_active_times[uid] = user.get("last_active_at") # Store timestamp
            except Exception as e:
                print(f"Lỗi fetch users for cache: {e}")

            # 3. Reload danh sách bên trái
            try:
                if self.current_mode == "user":
                    self.load_users()
                elif self.current_mode == "group":
                    self.load_groups()
            except Exception as e:
                print(f"Lỗi reload danh sách: {e}")

            # 4. Cập nhật Header nếu đang chat với người đó
            if self.current_mode == "user" and self.current_receiver_id == user_id:
                self.current_receiver_name = display_name
                self.header_name_label.setText(f"💬 {display_name}")
                # Cập nhật lại trạng thái nếu đang hiển thị
                status = self.user_statuses.get(user_id, "offline")
                self.update_header_status_display(user_id, status)

            # 5. Cập nhật tin nhắn hiện có (Avatar & Tên)
            try:
                self.update_messages_avatar_name(user_id, display_name)
            except Exception as e:
                print(f"Lỗi cập nhật tin nhắn: {e}")

        except Exception as e:
            print(f"Lỗi trong handle_profile_update_ui: {e}")
            import traceback
            traceback.print_exc()

    def update_messages_avatar_name(self, user_id, new_name):
        """Cập nhật tên và avatar cho các tin nhắn của user_id đang hiển thị"""
        new_avatar_b64 = self.user_avatars.get(user_id)
        
        # Tạo pixmap avatar mới
        new_pixmap = None
        if new_avatar_b64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(new_avatar_b64))
                new_pixmap = QtGui.QPixmap(35, 35)
                new_pixmap.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(new_pixmap)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 35, 35)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(35, 35, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
            except:
                pass

        # Duyệt qua tất cả các tin nhắn trong layout
        for i in range(self.chat_messages_layout.count()):
            item = self.chat_messages_layout.itemAt(i)
            widget = item.widget()
            if not widget: continue
            
            # Tìm avatar label và name label trong bubble
            # Cấu trúc bubble: HBoxLayout -> [Avatar, ContentWrapper] hoặc [ContentWrapper, Avatar]
            # ContentWrapper: VBoxLayout -> [NameLabel (optional), MessageContent]
            
            # Vì cấu trúc bubble khá động, ta sẽ tìm theo type
            avatar_label = None
            name_label = None
            
            # Tìm Avatar Label (nằm trực tiếp trong layout chính của bubble)
            for child in widget.findChildren(QtWidgets.QLabel):
                if child.size().width() == 35 and child.size().height() == 35: # Kích thước avatar
                    avatar_label = child
                elif child.text() == self.user_names.get(user_id, ""): # Tìm label tên cũ (có thể không chính xác tuyệt đối nhưng tạm ổn)
                    pass 

            # Cách tốt hơn: Lưu user_id vào widget khi tạo bubble để dễ tìm
            # Nhưng vì ta đang sửa code cũ, ta sẽ duyệt layout
            
            # Kiểm tra xem bubble này có phải của user_id không?
            # Rất khó nếu không lưu user_id vào bubble.
            # => Cần sửa create_message_bubble để gắn user_id vào widget
            pass 
        
        # DO CẤU TRÚC BUBBLE KHÔNG LƯU USER_ID, TA CẦN RELOAD LẠI CHAT HISTORY LÀ TỐT NHẤT
        # ĐỂ ĐẢM BẢO CHÍNH XÁC.
        # Tuy nhiên, yêu cầu là "cập nhật hiển thị", reload cũng là 1 cách cập nhật.
        # Nhưng reload sẽ làm mất vị trí scroll.
        # => Ta sẽ sửa create_message_bubble để lưu user_id vào property của widget.
        
        # Vì ta không thể sửa create_message_bubble ngay trong hàm này (nó ở chỗ khác),
        # nên giải pháp an toàn nhất hiện tại là reload current chat nếu đang chat với user đó.
        
        if self.current_mode == "user" and (self.current_receiver_id == user_id or user_id == self.user_id):
             # Nếu đang chat với người update HOẶC chính mình update
             self.reload_current_chat()
        elif self.current_mode == "group":
             # Nếu đang chat group, reload để cập nhật avatar thành viên
             self.reload_current_chat()

    @QtCore.Slot()
    def reload_current_chat(self):
        if self.current_receiver_id and self.current_receiver_name:
            self.select_chat_by_id(self.current_receiver_id, self.current_receiver_name, self.current_mode)

    @QtCore.Slot(int, str)
    def handle_status_update_ui(self, user_id, status):
        # Cập nhật cache
        self.user_statuses[user_id] = status
        
        # 1. Update List Items
        # Duyệt qua danh sách bên trái để tìm item của user_id
        for i in range(self.chat_list_layout.count()):
            item = self.chat_list_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, ChatListItem):
                if widget.user_id == user_id:
                     widget.set_online(status == "online")
                     break # Found
        
        # 2. Update Header nếu đang chat với người đó
        if self.current_mode == "user" and self.current_receiver_id == user_id:
            self.update_header_status_display(user_id, status)

    def update_header_status_display(self, user_id, status):
        """Cập nhật nhãn trạng thái trên header chat."""
        if status == "online":
            self.header_status_label.setText("<span style='color: #2ecc71;'>● Đang hoạt động</span>")
            self.header_status_label.show()
        else:
            last_active = self.last_active_times.get(user_id)
            if last_active:
                # Chuyển đổi timestamp string sang định dạng dễ đọc
                try:
                    # Giả định last_active là ISO format string (e.g., "2023-10-27T10:30:00.123456")
                    from datetime import datetime
                    dt_object = datetime.fromisoformat(last_active)
                    now = datetime.now()
                    diff = now - dt_object

                    if diff.total_seconds() < 60:
                        time_str = "vừa mới"
                    elif diff.total_seconds() < 3600:
                        minutes = int(diff.total_seconds() / 60)
                        time_str = f"{minutes} phút trước"
                    elif diff.total_seconds() < 86400:
                        hours = int(diff.total_seconds() / 3600)
                        time_str = f"{hours} giờ trước"
                    else:
                        time_str = dt_object.strftime("%H:%M %d/%m") # VD: 10:30 27/10
                    
                    self.header_status_label.setText(f"Hoạt động {time_str}")
                    self.header_status_label.show()
                except ValueError:
                    self.header_status_label.setText("Offline")
                    self.header_status_label.show()
            else:
                self.header_status_label.setText("Offline")
                self.header_status_label.show()

    def display_incoming_message(self, message, sender_name, message_type, target_id, sender_id=None, sender_avatar=None, is_system=False):
        is_img = (message_type == 'image')
        is_voice = (message_type == 'voice')
        is_video = (message_type == 'video')
        is_call_log = (message_type == 'call_log')
        
        # Ưu tiên dùng avatar từ message (mới nhất), nếu không có thì dùng cache
        avatar = sender_avatar
        if not avatar and sender_id and sender_id in self.user_avatars:
            avatar = self.user_avatars[sender_id]
        elif not avatar and self.current_mode == "user" and target_id in self.user_avatars:
            avatar = self.user_avatars[target_id]
        
        if is_system:
             self.add_system_message(message)
             return

        self.add_message_to_chat(message, sender_name, False, is_img, is_voice, is_video, is_call_log, avatar)

    def refresh_self_profile(self):
        try:
            resp = self.controller.get_profile()
            if resp.get('status') == 'success':
                self.display_name = resp.get('display_name', self.display_name)
                self.self_avatar = resp.get('avatar')
                self.self_is_invisible = resp.get('is_invisible', False)
                if self.self_avatar:
                    try:
                        pix = QtGui.QPixmap()
                        pix.loadFromData(base64.b64decode(self.self_avatar))
                        # Tạo avatar tròn cho sidebar
                        rounded = QtGui.QPixmap(50, 50)
                        rounded.fill(QtCore.Qt.GlobalColor.transparent)
                        painter = QtGui.QPainter(rounded)
                        painter.setRenderHint(QtGui.QPainter.Antialiasing)
                        path = QtGui.QPainterPath()
                        path.addEllipse(0, 0, 50, 50)
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, pix.scaled(50, 50, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                        painter.end()
                        self.sidebar_avatar.setPixmap(rounded)
                    except:
                        self.sidebar_avatar.setText("😊")
        except Exception as e:
            print(e)

    def show_emoji_picker(self):
        emojis = ["😊", "😂", "❤️", "👍", "🎉", "😍", "😢", "😎"]
        menu = QtWidgets.QMenu(self)
        for e in emojis:
            action = menu.addAction(e)
            action.triggered.connect(lambda chk, em=e: self.message_input.insert(em))
        menu.exec(QtGui.QCursor.pos())

    def start_recording(self):
        self.is_recording = True
        self.frames = []
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True,
                                          frames_per_buffer=1024)
            threading.Thread(target=self.record_audio, daemon=True).start()
            self.message_input.setPlaceholderText("🔴 Đang ghi âm...")
        except Exception as e:
            print(e)

    def record_audio(self):
        while self.is_recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
            except:
                break

    def stop_recording(self):
        if not self.is_recording: return
        self.is_recording = False
        self.message_input.setPlaceholderText("Nhập tin nhắn...")
        if self.stream: self.stream.stop_stream(); self.stream.close()
        if self.audio: self.audio.terminate()
        if self.frames:
            buffer = io.BytesIO()
            wf = wave.open(buffer, 'wb')
            wf.setnchannels(1);
            wf.setsampwidth(2);
            wf.setframerate(44100)
            wf.writeframes(b''.join(self.frames));
            wf.close()
            
            # Kiểm tra giới hạn kích thước (10MB)
            voice_data_bytes = buffer.getvalue()
            if len(voice_data_bytes) > 10 * 1024 * 1024:
                 QtWidgets.QMessageBox.warning(self, "Ghi âm quá dài", "File ghi âm quá lớn (>10MB). Vui lòng ghi âm ngắn hơn.")
                 return

            voice_b64 = base64.b64encode(voice_data_bytes).decode('utf-8')
            if self.current_receiver_id:
                if self.current_mode == "user": 
                    self.controller.send_voice(self.current_receiver_id, voice_b64, "voice.wav")
                else:
                    self.controller.send_group_message(self.current_receiver_id, "", is_voice=True, voice_data=voice_b64)
                    
                self.add_message_to_chat(voice_b64, "Bạn", True, is_voice=True, avatar_base64=self.self_avatar)
                self.add_message_to_chat(voice_b64, "Bạn", True, is_voice=True, avatar_base64=self.self_avatar)

    def add_member_to_group(self):
        if not self.current_receiver_id or self.current_mode != "group": return
        
        # Lấy danh sách thành viên hiện tại để lọc
        current_members = self.controller.get_group_members(self.current_receiver_id)
        current_member_ids = [str(uid) for uid in current_members]

        all_users = [
            u for u in self.controller.get_users()
            if str(u['user_id']) != str(self.user_id) and str(u['user_id']) not in current_member_ids
        ]
        
        # Tái sử dụng CreateGroupDialog nhưng để chọn item
        dialog = CreateGroupDialog(self, all_users, is_add_mode=True)
        # Tiêu đề được xử lý bởi is_add_mode
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            _, member_ids = dialog.get_data()
            if member_ids:
                resp = self.controller.add_group_member(self.current_receiver_id, member_ids)
                if resp.get("status") == "success":
                   # Success handled by notification or just ok
                   pass
                else:
                   QtWidgets.QMessageBox.critical(self, "Lỗi", resp.get("message", "Lỗi thêm thành viên"))

    def leave_group(self):
        if not self.current_receiver_id or self.current_mode != "group": return
        
        reply = QtWidgets.QMessageBox.question(
            self, 'Rời nhóm', 
            "Bạn có chắc chắn muốn rời nhóm?\nNếu bạn là thành viên cuối cùng, nhóm sẽ bị giải tán.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
            
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            resp = self.controller.leave_group(self.current_receiver_id)
            if resp.get("status") == "success":
                self.switch_to_group_mode() # Reload view
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", resp.get("message", "Lỗi rời nhóm"))

    def open_profile_dialog(self):
        d = ProfileDialog(self.controller, self.display_name, self.self_avatar, self.self_is_invisible, self)
        if d.exec():
            # Lưu lại thông tin chat hiện tại
            saved_receiver_id = self.current_receiver_id
            saved_receiver_name = self.current_receiver_name
            saved_mode = self.current_mode
            
            # Refresh profile của chính mình
            self.refresh_self_profile()
            
            # Load lại danh sách theo mode hiện tại
            if self.current_mode == "user":
                self.load_users()
            elif self.current_mode == "group":
                self.load_groups()
            
            # Khôi phục lại chat hiện tại
            if saved_receiver_id and saved_receiver_name:
                QtCore.QTimer.singleShot(100, lambda: self.select_chat_by_id(
                    saved_receiver_id, saved_receiver_name, saved_mode))
                QtCore.QTimer.singleShot(200, lambda: self.reload_current_chat() if self.current_receiver_id else None)


    def view_group_members(self):
        """Hiển thị danh sách thành viên nhóm dưới dạng Menu dội xuống"""
        if not self.current_receiver_id or self.current_mode != "group": return

        # 1. Fetch mới nhất từ server
        members_ids = self.controller.get_group_members(self.current_receiver_id)
        if not members_ids: return

        # 2. Tạo Menu
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #ddd; border-radius: 5px; padding: 5px; }
            QMenu::item { padding: 8px 20px; font-size: 14px; color: black; }
            QMenu::item:selected { background-color: #f0f2f5; color: black; }
        """)

        # 3. Populate
        # Convert IDs to Names logic
        # We need a way to get name from ID even if not in cache.
        # Ideally get_users() contains all.
        
        # Get all users map for lookup
        all_users_map = {u['user_id']: u['display_name'] for u in self.controller.get_users()}
        
        # Add Title Action (Disabled)
        title_action = QtGui.QAction(f"Thành viên ({len(members_ids)})", self)
        title_action.setEnabled(False)
        title_font = title_action.font()
        title_font.setBold(True)
        title_action.setFont(title_font)
        menu.addAction(title_action)
        menu.addSeparator()

        for mid in members_ids:
            name = all_users_map.get(mid, f"User {mid}")
            if str(mid) == str(self.user_id):
                name += " (Bạn)"
            
            action = QtGui.QAction(name, self)
            # Optional: Add icon/avatar? For now just text.
            menu.addAction(action)

        # 4. Show Menu button relative position
        menu.exec(self.btn_view_members.mapToGlobal(QtCore.QPoint(0, self.btn_view_members.height())))

    def logout(self):
        reply = QtWidgets.QMessageBox.question(self, 'Đăng xuất', 'Bạn có chắc chắn muốn đăng xuất?',
                                               QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                               QtWidgets.QMessageBox.StandardButton.No)

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Stop message check loop FIRST
            self._message_check_running = False
            
            # Close AI window if open
            if self.ai_chat_window:
                self.ai_chat_window.close()
                self.ai_chat_window = None
            
            # Stop controller (this closes socket and stops receive thread)
            self.controller.stop()
            
            # Give threads time to exit
            import time
            time.sleep(0.3)
            
            self.app.show_login()
            self.close()

    def closeEvent(self, event):
        self._message_check_running = False
        if self.controller:
            self.controller.stop()
        event.accept()