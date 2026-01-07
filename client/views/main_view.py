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
from client.controllers.moderation_controller import ClientModerationController
from client.views.notification_toast import NotificationManager
from config.config import BADWORDS_PATH
from client.ui.camera_capture_dialog import CameraCaptureDialog


# Helper function to show styled QMessageBox with white background
def _show_styled_message(parent, msg_type, title, message):
    """
    Hiển thị QMessageBox với style nền trắng để dễ đọc.
    msg_type: 'information', 'warning', 'critical'
    """
    msg_box = QtWidgets.QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    
    if msg_type == 'information':
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
    elif msg_type == 'warning':
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    elif msg_type == 'critical':
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: white;
        }
        QMessageBox QLabel {
            color: #333;
            font-size: 13px;
        }
        QMessageBox QPushButton {
            background-color: #667eea;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 5px;
            min-width: 80px;
            font-size: 12px;
        }
        QMessageBox QPushButton:hover {
            background-color: #5a6fd6;
        }
    """)
    msg_box.exec()



class ChatListItem(QtWidgets.QWidget):
    def __init__(self, user_id, display_name, last_message="", avatar_base64=None, item_type="user", timestamp="", parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.item_type = item_type
        self.display_name = display_name
        self.avatar_base64 = avatar_base64
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(12)
        
        # Avatar với viền tròn
        avatar_label = QtWidgets.QLabel()
        avatar_label.setFixedSize(48, 48)
        avatar_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if self.avatar_base64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(self.avatar_base64))
                # Tạo pixmap tròn
                rounded = QtGui.QPixmap(48, 48)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 48, 48)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(48, 48, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                avatar_label.setPixmap(rounded)
                avatar_label.setStyleSheet("background-color: transparent;")
            except Exception:
                avatar_label.setText("👤")
                avatar_label.setStyleSheet("background-color: #e8e8e8; border-radius: 24px; font-size: 20px;")
        else:
            avatar_label.setText("👤")
            avatar_label.setStyleSheet("background-color: #e8e8e8; border-radius: 24px; font-size: 20px;")
        layout.addWidget(avatar_label)

        # Info Layout (Name + Last Message)
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Top row: Name + Timestamp
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(8)
        
        name_label = QtWidgets.QLabel(display_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a1a1a;")
        top_row.addWidget(name_label)
        
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setStyleSheet("color: #22c55e; font-size: 8px;")  # Green dot
        self.status_dot.hide()  # Default hidden
        top_row.addWidget(self.status_dot)
        top_row.addStretch()
        
        # Timestamp
        self.time_label = QtWidgets.QLabel(timestamp)
        self.time_label.setStyleSheet("font-size: 12px; color: #9ca3af;")
        top_row.addWidget(self.time_label)
        
        info_layout.addLayout(top_row)

        # Bottom row: Last message with typing indicator support
        bottom_row = QtWidgets.QHBoxLayout()
        self.last_msg_label = QtWidgets.QLabel(last_message if last_message else "Bắt đầu trò chuyện...")
        self.last_msg_label.setStyleSheet("font-size: 13px; color: #6b7280;")
        self.last_msg_label.setWordWrap(False)
        bottom_row.addWidget(self.last_msg_label)
        bottom_row.addStretch()
        
        # Check mark for sent/read status
        self.check_mark = QtWidgets.QLabel("✓")
        self.check_mark.setStyleSheet("color: #22c55e; font-size: 12px;")
        self.check_mark.hide()  # Default hidden
        bottom_row.addWidget(self.check_mark)
        
        info_layout.addLayout(bottom_row)
        layout.addLayout(info_layout, 1)
        
        self.setLayout(layout)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("""
            ChatListItem { 
                background-color: transparent; 
                border-bottom: 1px solid rgba(0,0,0,0.06); 
            } 
            ChatListItem:hover { 
                background-color: rgba(0,0,0,0.03); 
            }
        """)
    
    def set_typing(self, is_typing, name=""):
        """Hiển thị trạng thái đang gõ"""
        if is_typing:
            self.last_msg_label.setText(f"<span style='color: #22c55e;'>... đang soạn tin</span>")
        else:
            self.last_msg_label.setText("Nhấn để xem tin nhắn")

    def set_online(self, is_online):
        if is_online:
            self.status_dot.show()
            self.check_mark.show()
        else:
            self.status_dot.hide()
            self.check_mark.hide()
    
    def set_timestamp(self, timestamp):
        """Cập nhật timestamp"""
        self.time_label.setText(timestamp)


class WaveformWidget(QtWidgets.QWidget):
    """Custom waveform visualization widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0  # 0-100
        self.bars = [0.3, 0.5, 0.8, 0.6, 0.9, 0.4, 0.7, 0.5, 0.8, 0.3, 0.6, 0.9, 0.5, 0.7, 0.4, 0.8, 0.6, 0.3, 0.7, 0.5]
        self.setMinimumHeight(30)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
    def setProgress(self, value):
        self.progress = max(0, min(100, value))
        self.update()
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        bar_count = len(self.bars)
        bar_width = max(3, (w - (bar_count - 1) * 2) // bar_count)
        spacing = 2
        
        progress_x = (self.progress / 100) * w
        
        for i, bar_height_ratio in enumerate(self.bars):
            x = i * (bar_width + spacing)
            bar_h = int(h * bar_height_ratio * 0.8)
            y = (h - bar_h) // 2
            
            # Color based on progress
            if x < progress_x:
                painter.setBrush(QtGui.QColor("#ffffff"))
            else:
                painter.setBrush(QtGui.QColor(255, 255, 255, 100))
            
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(int(x), y, bar_width, bar_h, 2, 2)
        
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.progress = int((event.position().x() / self.width()) * 100)
            self.update()
            self.parent().seek_to_progress(self.progress)


class VoiceMessageWidget(QtWidgets.QWidget):
    """Voice message with glassmorphism, gradient play button, waveform visualization, and speech-to-text"""
    def __init__(self, voice_data, is_self=False, parent=None):
        super().__init__(parent)
        self.voice_data = voice_data
        self.is_self = is_self
        self.is_playing = False
        self.total_duration = 0
        self.audio_player = QtMultimedia.QMediaPlayer()
        self.audio_output = QtMultimedia.QAudioOutput()
        self.audio_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.temp_file = None
        self.transcribed_text = None
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # Audio player container
        self.player_widget = QtWidgets.QWidget()
        self.player_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.player_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 rgba(102, 126, 234, 0.9), 
                    stop:1 rgba(118, 75, 162, 0.9));
                border-radius: 25px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(self.player_widget)
        layout.setContentsMargins(8, 8, 12, 8)
        layout.setSpacing(10)
        
        # Gradient circular play button (35px)
        self.play_button = QtWidgets.QPushButton("▶")
        self.play_button.setFixedSize(35, 35)
        self.play_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.play_button.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #ffffff, stop:1 #e0e0e0);
                border: none; 
                border-radius: 17px; 
                color: #667eea; 
                font-size: 14px;
                font-weight: bold;
                padding-left: 2px;
            } 
            QPushButton:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #f0f0f0, stop:1 #d0d0d0);
            }
            QPushButton:pressed {
                background: #d0d0d0;
            }
        """)
        self.play_button.clicked.connect(self.toggle_play)
        layout.addWidget(self.play_button)
        
        # Waveform visualization
        self.waveform = WaveformWidget(self)
        self.waveform.setFixedHeight(30)
        layout.addWidget(self.waveform, 1)
        
        # Duration label - white text
        self.time_label = QtWidgets.QLabel("0:00")
        self.time_label.setStyleSheet("""
            color: #ffffff; 
            font-size: 12px; 
            font-weight: bold;
            background: transparent;
        """)
        self.time_label.setFixedWidth(36)
        layout.addWidget(self.time_label)
        
        # Transcribe button
        self.transcribe_btn = QtWidgets.QPushButton("📝")
        self.transcribe_btn.setFixedSize(30, 30)
        self.transcribe_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.transcribe_btn.setToolTip("Chuyển thành văn bản")
        self.transcribe_btn.setStyleSheet("""
            QPushButton { 
                background: rgba(255, 255, 255, 0.2);
                border: none; 
                border-radius: 15px; 
                color: white; 
                font-size: 14px;
            } 
            QPushButton:hover { 
                background: rgba(255, 255, 255, 0.4);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.transcribe_btn.clicked.connect(self.transcribe_audio)
        layout.addWidget(self.transcribe_btn)
        
        main_layout.addWidget(self.player_widget)
        
        # Transcription text label (hidden initially)
        self.text_label = QtWidgets.QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("""
            background-color: rgba(102, 126, 234, 0.1);
            color: #333;
            padding: 8px 12px;
            border-radius: 10px;
            font-size: 12px;
        """)
        self.text_label.setVisible(False)
        self.text_label.setMaximumWidth(300)
        main_layout.addWidget(self.text_label)
        
        # Connections
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.audio_player.positionChanged.connect(self.on_position_changed)
        self.audio_player.durationChanged.connect(self.on_duration_changed)
        self.audio_player.playbackStateChanged.connect(self.on_state_changed)
        
        # Size
        self.player_widget.setFixedHeight(50)
        self.setMinimumWidth(180)
        self.setMaximumWidth(320)

    def seek_to_progress(self, progress):
        """Called by waveform when clicked"""
        if self.total_duration > 0:
            pos = int((progress / 100) * self.total_duration)
            self.audio_player.setPosition(pos)
            if not self.is_playing:
                self.play_voice()

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
                with open(self.temp_file, 'wb') as f: 
                    f.write(audio_bytes)
            self.audio_player.setSource(QtCore.QUrl.fromLocalFile(self.temp_file))
            self.audio_player.play()
        except Exception as e:
            print(f"Lỗi phát voice: {e}")

    def stop_voice(self):
        self.audio_player.stop()

    def on_position_changed(self, position):
        if self.total_duration > 0:
            progress = int((position / self.total_duration) * 100)
            self.waveform.setProgress(progress)
            seconds = position // 1000
            self.time_label.setText(f"{seconds // 60}:{seconds % 60:02d}")

    def on_duration_changed(self, duration):
        if duration > 0:
            self.total_duration = duration
            seconds = duration // 1000
            self.time_label.setText(f"{seconds // 60}:{seconds % 60:02d}")

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
                self.waveform.setProgress(0)
                if self.total_duration > 0:
                    seconds = self.total_duration // 1000
                    self.time_label.setText(f"{seconds // 60}:{seconds % 60:02d}")

    def update_progress(self):
        if self.total_duration > 0:
            pos = self.audio_player.position()
            self.waveform.setProgress(int((pos / self.total_duration) * 100))

    def transcribe_audio(self):
        """Chuyển đổi giọng nói thành văn bản sử dụng Google Speech Recognition"""
        if self.transcribed_text:
            # Already transcribed, toggle visibility
            self.text_label.setVisible(not self.text_label.isVisible())
            return
        
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setText("⏳")
        
        # Run in thread to avoid blocking UI
        def do_transcribe():
            try:
                import speech_recognition as sr
                
                # Ensure temp file exists
                if self.temp_file is None or not os.path.exists(self.temp_file):
                    audio_bytes = base64.b64decode(self.voice_data)
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    self.temp_file = os.path.join(temp_dir, f"temp_voice_{id(self)}.wav")
                    with open(self.temp_file, 'wb') as f: 
                        f.write(audio_bytes)
                
                recognizer = sr.Recognizer()
                with sr.AudioFile(self.temp_file) as source:
                    audio = recognizer.record(source)
                
                # Use Google Speech Recognition (supports Vietnamese)
                text = recognizer.recognize_google(audio, language="vi-VN")
                return ("success", text)
            except sr.UnknownValueError:
                return ("error", "Không nhận diện được giọng nói")
            except sr.RequestError as e:
                return ("error", f"Lỗi kết nối: {e}")
            except Exception as e:
                return ("error", f"Lỗi: {e}")
        
        def on_complete(result):
            status, text = result
            self.transcribe_btn.setEnabled(True)
            self.transcribe_btn.setText("📝")
            
            if status == "success":
                self.transcribed_text = text
                self.text_label.setText(f"📝 {text}")
                self.text_label.setVisible(True)
            else:
                _show_styled_message(self, 'warning', "Không thể chuyển đổi", text)
        
        # Use QThread for async operation
        class TranscribeWorker(QtCore.QThread):
            finished = QtCore.Signal(tuple)
            
            def run(self):
                result = do_transcribe()
                self.finished.emit(result)
        
        self.worker = TranscribeWorker()
        self.worker.finished.connect(on_complete)
        self.worker.start()

    def cleanup(self):
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                if self.audio_player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
                    self.audio_player.stop()
                os.remove(self.temp_file)
            except:
                pass


class FileMessageWidget(QtWidgets.QWidget):
    def __init__(self, filename, file_data, file_size, is_self=False, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.file_data = file_data
        self.file_size = file_size
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QtWidgets.QLabel("📄")
        icon_label.setStyleSheet("font-size: 20px; color: white;")
        layout.addWidget(icon_label)
        
        # Info (Name + Size)
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QtWidgets.QLabel(filename)
        name_label.setStyleSheet("font-weight: bold; color: white;")
        info_layout.addWidget(name_label)
        
        size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
        size_label = QtWidgets.QLabel(size_str)
        size_label.setStyleSheet("font-size: 10px; color: #eee;")
        info_layout.addWidget(size_label)
        
        layout.addLayout(info_layout)
        
        # Download Button
        self.btn_download = QtWidgets.QPushButton("⬇")
        self.btn_download.setFixedSize(30, 30)
        self.btn_download.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_download.setStyleSheet("""
            QPushButton { 
                background-color: rgba(255,255,255,0.2); 
                border: none; 
                border-radius: 15px; 
                color: white; 
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: rgba(255,255,255,0.4); 
            }
        """)
        self.btn_download.clicked.connect(self.download_file)
        layout.addWidget(self.btn_download)
        
        self.setStyleSheet("background: transparent;")
        self.setFixedWidth(250)
        
    def download_file(self):
        try:
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu file", self.filename)
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(base64.b64decode(self.file_data))
                _show_styled_message(self, 'information', "Thành công", "Đã lưu file thành công!")
        except Exception as e:
            _show_styled_message(self, 'critical', "Lỗi", f"Không thể lưu file: {e}")

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton: self.clicked.emit()
        super().mousePressEvent(event)


class ImageMessageWidget(QtWidgets.QWidget):
    """Widget hiển thị ảnh với nút tải về."""
    def __init__(self, image_data_base64, is_self=False, parent=None):
        super().__init__(parent)
        self.image_data = image_data_base64
        self.is_self = is_self
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Image Container
        img_container = QtWidgets.QWidget()
        img_layout = QtWidgets.QVBoxLayout(img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image Label
        self.img_label = QtWidgets.QLabel()
        try:
            p = QtGui.QPixmap()
            p.loadFromData(base64.b64decode(image_data_base64))
            self.img_label.setPixmap(p.scaled(250, 250, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
        except:
            self.img_label.setText("Lỗi ảnh")
        self.img_label.setStyleSheet("border-radius: 10px;")
        img_layout.addWidget(self.img_label)
        
        layout.addWidget(img_container)
        
        # Download Button
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_download = QtWidgets.QPushButton("⬇")
        self.btn_download.setFixedHeight(28)
        self.btn_download.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_download.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {'#667eea' if is_self else '#7f8c8d'}; 
                border: none; 
                border-radius: 14px; 
                color: white; 
                font-size: 11px;
                padding: 5px 15px;
            }} 
            QPushButton:hover {{ 
                background-color: {'#5a6fd6' if is_self else '#6c7a89'}; 
            }}
        """)
        self.btn_download.clicked.connect(self.download_image)
        
        if is_self:
            btn_layout.addStretch()
        btn_layout.addWidget(self.btn_download)
        if not is_self:
            btn_layout.addStretch()
        
        layout.addWidget(btn_container)
        
    def download_image(self):
        try:
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Lưu ảnh", "image.jpg", "Image Files (*.jpg *.png)"
            )
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(base64.b64decode(self.image_data))
                _show_styled_message(self, 'information', "Thành công", "Đã lưu ảnh thành công!")
        except Exception as e:
            _show_styled_message(self, 'critical', "Lỗi", f"Không thể lưu ảnh: {e}")


class LocationMessageWidget(QtWidgets.QWidget):
    """Widget hiển thị vị trí với bản đồ mô phỏng và link Google Maps."""
    stop_sharing_signal = QtCore.Signal()  # Signal khi dừng chia sẻ
    
    def __init__(self, lat, lng, address="", is_self=False, duration_minutes=0, 
                 location_id=0, receiver_id=None, main_view=None, parent=None):
        super().__init__(parent)
        self.lat = lat
        self.lng = lng
        self.address = address
        self.is_self = is_self
        self.duration_minutes = duration_minutes
        self.is_active = True
        self.location_id = location_id  # Timestamp để nhận diện
        self.receiver_id = receiver_id  # ID người nhận
        self.main_view = main_view  # Reference để gửi signal
        
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === MAP PREVIEW (Vẽ mô phỏng bản đồ) ===
        self.map_widget = MapPreviewWidget(self)
        self.map_widget.setFixedSize(240, 120)
        self.map_widget.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.map_widget.mousePressEvent = lambda e: self.open_maps()
        main_layout.addWidget(self.map_widget)
        
        # === INFO SECTION ===
        info_container = QtWidgets.QWidget()
        info_container.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {'#667eea' if is_self else '#7f8c8d'}, 
                stop:1 {'#764ba2' if is_self else '#95a5a6'});
        """)
        info_layout = QtWidgets.QVBoxLayout(info_container)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)
        
        # Header: Icon + Title
        header = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel("📍")
        icon_label.setStyleSheet("font-size: 18px; background: transparent;")
        header.addWidget(icon_label)
        
        title_label = QtWidgets.QLabel("Đang chia sẻ vị trí")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: white; background: transparent;")
        header.addWidget(title_label)
        header.addStretch()
        info_layout.addLayout(header)
        
        # Address
        if address:
            addr_label = QtWidgets.QLabel(address)
            addr_label.setWordWrap(True)
            addr_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 11px; background: transparent;")
            addr_label.setMaximumWidth(220)
            info_layout.addWidget(addr_label)
        
        # Buttons row
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # Open Maps button
        maps_btn = QtWidgets.QPushButton("🗺️ Xem bản đồ")
        maps_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        maps_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.25);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 11px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.35); }
        """)
        maps_btn.clicked.connect(self.open_maps)
        btn_layout.addWidget(maps_btn)
        
        # Stop sharing button (only for sender)
        if is_self:
            self.stop_btn = QtWidgets.QPushButton("⏹ Dừng")
            self.stop_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.stop_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(231, 76, 60, 0.8);
                    border: none;
                    border-radius: 12px;
                    color: white;
                    font-size: 11px;
                    padding: 6px 12px;
                }
                QPushButton:hover { background-color: rgba(231, 76, 60, 1); }
            """)
            self.stop_btn.clicked.connect(self.stop_sharing)
            btn_layout.addWidget(self.stop_btn)
        
        btn_layout.addStretch()
        info_layout.addLayout(btn_layout)
        
        main_layout.addWidget(info_container)
        
        # Overall styling
        self.setStyleSheet("""
            LocationMessageWidget {
                background: #2c3e50;
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
            }
        """)
        self.setFixedWidth(240)
        
        # Auto-hide timer (if duration set)
        if duration_minutes > 0:
            QtCore.QTimer.singleShot(duration_minutes * 60 * 1000, self.auto_stop)
    
    def open_maps(self):
        """Mở Google Maps trong trình duyệt."""
        import webbrowser
        url = f"https://www.google.com/maps?q={self.lat},{self.lng}"
        webbrowser.open(url)
    
    def stop_sharing(self):
        """Dừng chia sẻ vị trí."""
        self.is_active = False
        self.stop_sharing_signal.emit()
        
        # Gửi signal tới receiver để xóa widget
        if self.main_view and self.receiver_id and self.location_id:
            self.main_view.controller.send_signal(self.receiver_id, "stop_location", {
                "location_id": self.location_id
            })
            # Xóa cả bubble ở sender
            self.main_view.remove_location_widget(self.location_id)
        
        _show_styled_message(self.main_view if self.main_view else self, 'information', "Vị trí", "Đã dừng chia sẻ vị trí")
    
    def auto_stop(self):
        """Tự động dừng khi hết thời gian."""
        if self.is_active:
            self.is_active = False
            
            # Gửi signal tới receiver để xóa widget
            if self.main_view and self.receiver_id and self.location_id:
                self.main_view.controller.send_signal(self.receiver_id, "stop_location", {
                    "location_id": self.location_id
                })
                # Xóa cả bubble ở sender
                self.main_view.remove_location_widget(self.location_id)



class MapPreviewWidget(QtWidgets.QWidget):
    """Widget vẽ bản đồ mô phỏng với marker."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #e8f4f8; border-top-left-radius: 15px; border-top-right-radius: 15px;")
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Background - light map color
        painter.fillRect(0, 0, w, h, QtGui.QColor("#e8f4f8"))
        
        # Draw roads (simple grid pattern)
        road_pen = QtGui.QPen(QtGui.QColor("#d0d8dc"), 3)
        painter.setPen(road_pen)
        
        # Horizontal roads
        painter.drawLine(0, h//3, w, h//3)
        painter.drawLine(0, 2*h//3, w, 2*h//3)
        
        # Vertical roads  
        painter.drawLine(w//4, 0, w//4, h)
        painter.drawLine(w//2, 0, w//2, h)
        painter.drawLine(3*w//4, 0, 3*w//4, h)
        
        # Main road (thicker)
        main_road_pen = QtGui.QPen(QtGui.QColor("#bdc3c7"), 6)
        painter.setPen(main_road_pen)
        painter.drawLine(0, h//2, w, h//2)
        
        # Draw marker pin
        cx, cy = w//2, h//2
        
        # Pin shadow
        painter.setBrush(QtGui.QColor(0, 0, 0, 30))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(cx-8, cy+15, 16, 6)
        
        # Pin body (gradient)
        gradient = QtGui.QRadialGradient(cx, cy-10, 20)
        gradient.setColorAt(0, QtGui.QColor("#e74c3c"))
        gradient.setColorAt(1, QtGui.QColor("#c0392b"))
        painter.setBrush(gradient)
        
        # Pin shape (circle + triangle)
        path = QtGui.QPainterPath()
        path.addEllipse(cx-12, cy-24, 24, 24)
        path.moveTo(cx-8, cy-5)
        path.lineTo(cx, cy+12)
        path.lineTo(cx+8, cy-5)
        path.closeSubpath()
        painter.drawPath(path)
        
        # Inner white circle
        painter.setBrush(QtGui.QColor("white"))
        painter.drawEllipse(cx-5, cy-17, 10, 10)


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

        # Download Button
        self.btn_download = QtWidgets.QPushButton("⬇")
        self.btn_download.setFixedSize(30, 30)
        self.btn_download.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.btn_download.setToolTip("Tải video")
        self.btn_download.setStyleSheet("""
            QPushButton { border: none; font-size: 14px; color: #667eea; background: rgba(102, 126, 234, 0.1); border-radius: 15px; }
            QPushButton:hover { background: rgba(102, 126, 234, 0.2); }
        """)
        self.btn_download.clicked.connect(self.download_video)
        c_layout.addWidget(self.btn_download)

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

    def download_video(self):
        try:
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Lưu video", "video.mp4", "Video Files (*.mp4)"
            )
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(base64.b64decode(self.video_data))
                _show_styled_message(self, 'information', "Thành công", "Đã lưu video thành công!")
        except Exception as e:
            _show_styled_message(self, 'critical', "Lỗi", f"Không thể lưu video: {e}")

# ====================================================================
# CLASS MAIN VIEW CHÍNH - ĐÃ SỬA LỖI CRASH UI THREAD
# ====================================================================
class MainView(QtWidgets.QMainWindow):
    # Khai báo các tín hiệu để giao tiếp giữa luồng mạng và luồng giao diện
    message_received = QtCore.Signal(str, str, str, int, int, str, bool, str, int)  # content, sender_name, message_type, target_id, sender_id, sender_avatar, is_system, file_data, file_size
    profile_updated_signal = QtCore.Signal(int, str, object)  # uid, name, avatar (avatar cũng gửi kèm)
    new_group_signal = QtCore.Signal()
    status_updated_signal = QtCore.Signal(int, str) # uid, status
    signal_received = QtCore.Signal(dict) # Tín hiệu mới cho các sự kiện P2P
    force_logout_signal = QtCore.Signal(str)  # message - Tín hiệu bị đăng xuất từ thiết bị khác
    show_notification_signal = QtCore.Signal(int, str, str, str, str, object, object)  # sender_id, sender_name, avatar, content, msg_type, group_id, moderation

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
        
        # Khởi tạo Moderation Controller
        self.moderation_controller = ClientModerationController(BADWORDS_PATH)
        # Warm-up AI model in background to prevent lag on first message
        threading.Thread(target=self.moderation_controller._ensure_initialized, daemon=True).start()
        
        # Danh sách location_id đã bị dừng (để không load lại từ DB)
        self.stopped_location_ids = set()

        self.setWindowTitle("Python Chat App")
        self.resize(1100, 750)
        
        # Căn giữa màn hình
        qr = self.frameGeometry()
        cp = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        # UI Setup - Soft gradient outer frame with mint/green loang effect
        central_widget = QtWidgets.QWidget()
        central_widget.setStyleSheet("""
            QWidget#central_widget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #d4e7d4, stop:0.25 #c8dfc8, 
                    stop:0.5 #bcd7bc, stop:0.75 #d0e3d0, 
                    stop:1 #e0ede0);
            }
        """)
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)
        
        # Outer frame layout with padding
        outer_layout = QtWidgets.QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)
        
        # Inner container for 3-column layout
        inner_container = QtWidgets.QWidget()
        inner_container.setStyleSheet("background: transparent;")
        main_layout = QtWidgets.QHBoxLayout(inner_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setup_sidebar()
        main_layout.addWidget(self.sidebar_widget)

        # Ngăn xếp nội dung chính (Main Content Stack)
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        
        # --- Trang 0: Chat Cá nhân/Nhóm (Splitter) ---
        self.chat_container = QtWidgets.QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QtWidgets.QHBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(0)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: transparent; }")

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
        outer_layout.addWidget(inner_container)

        # Thiết lập Logic
        self.controller.current_user_id = self.user_id

        # KẾT NỐI TÍN HIỆU (RẤT QUAN TRỌNG ĐỂ KHÔNG BỊ CRASH)
        self.message_received.connect(self.display_incoming_message)
        self.profile_updated_signal.connect(self.handle_profile_update_ui)
        self.status_updated_signal.connect(self.handle_status_update_ui)
        self.new_group_signal.connect(self.load_groups)
        self.signal_received.connect(self.on_signal_received) # Connect new signal
        self.force_logout_signal.connect(self.handle_force_logout)  # Single Session Enforcement
        
        # Notification Manager (Toast Notifications)
        self.notification_manager = NotificationManager(self)
        self.show_notification_signal.connect(self._show_toast_notification)
        self.notification_manager.notification_clicked.connect(self._on_notification_clicked)

        self.current_receiver_id = None
        self.current_receiver_name = None
        self.self_avatar = None
        self.user_avatars = {}
        self.user_names = {}  # Cache tên hiển thị của user
        self.user_statuses = {} # Cache trạng thái online/offline
        self.last_active_times = {} # Cache thời gian: user_id -> timestamp string
        self.current_chat_id = None # user_id or group_id
        self.active_call_dialog = None # Theo dõi dialog cuộc gọi đang diễn ra
        self.incoming_dialog = None # Theo dõi dialog cuộc gọi đến
        self.call_target_id = None  # ID của người đang gọi (để gửi audio)

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

    def setup_sidebar(self):
        """Setup navigation sidebar (Column 1) - Minimal icons with hover effects only"""
        self.sidebar_widget = QtWidgets.QWidget()
        self.sidebar_widget.setFixedWidth(90)  # 1.5x larger
        self.sidebar_widget.setStyleSheet("""
            QWidget { 
                background: transparent;
            }
            QPushButton {
                background-color: transparent;
                border-radius: 18px;
                font-size: 24px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.5);
            }
            QPushButton[active="true"] {
                background-color: rgba(255, 255, 255, 0.7);
            }
        """)
        layout = QtWidgets.QVBoxLayout(self.sidebar_widget)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        # User Avatar (FIRST - at top)
        self.sidebar_avatar = ClickableLabel()
        self.sidebar_avatar.setFixedSize(56, 56)
        self.sidebar_avatar.setStyleSheet("""
            background-color: rgba(255,255,255,0.8); 
            border-radius: 28px; 
            border: 2px solid rgba(255,255,255,0.9);
        """)
        self.sidebar_avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sidebar_avatar.setToolTip("Hồ sơ cá nhân")
        self.sidebar_avatar.clicked.connect(self.open_profile_dialog)
        layout.addWidget(self.sidebar_avatar, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        layout.addSpacing(15)

        # Chat 1-1 Button - Just icon, hover shows soft background
        self.btn_chat_one = QtWidgets.QPushButton("💬")
        self.btn_chat_one.setFixedSize(56, 56)
        self.btn_chat_one.setToolTip("Chat cá nhân")
        self.btn_chat_one.setProperty("active", True)
        self.btn_chat_one.clicked.connect(self.switch_to_user_mode)
        layout.addWidget(self.btn_chat_one, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Group Chat Button
        self.btn_chat_group = QtWidgets.QPushButton("👥")
        self.btn_chat_group.setFixedSize(56, 56)
        self.btn_chat_group.setToolTip("Chat nhóm")
        self.btn_chat_group.clicked.connect(self.switch_to_group_mode)
        layout.addWidget(self.btn_chat_group, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # AI Chat Button
        self.btn_ai_chat = QtWidgets.QPushButton("🤖")
        self.btn_ai_chat.setFixedSize(56, 56)
        self.btn_ai_chat.setToolTip("Gemini AI Assistant")
        self.btn_ai_chat.clicked.connect(self.open_ai_chat)
        layout.addWidget(self.btn_ai_chat, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Settings Button
        self.btn_settings = QtWidgets.QPushButton("⚙️")
        self.btn_settings.setFixedSize(56, 56)
        self.btn_settings.setToolTip("Cài đặt")
        self.btn_settings.clicked.connect(self.open_profile_dialog)
        layout.addWidget(self.btn_settings, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        # Logout Button (at bottom) - Soft effect on hover
        self.btn_logout = QtWidgets.QPushButton("⏻")
        self.btn_logout.setFixedSize(56, 56)
        self.btn_logout.setToolTip("Đăng xuất")
        self.btn_logout.setStyleSheet("""
            QPushButton { 
                background-color: rgba(255, 200, 200, 0.4); 
                border-radius: 18px; 
                font-size: 24px; 
            }
            QPushButton:hover { 
                background-color: rgba(255, 180, 180, 0.6); 
            }
        """)
        self.btn_logout.clicked.connect(self.logout)
        layout.addWidget(self.btn_logout, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)



    def setup_user_list(self):
        """Setup chat list panel (Column 2) - Search + Chat list"""
        self.user_list_widget = QtWidgets.QWidget()
        self.user_list_widget.setMinimumWidth(280)
        self.user_list_widget.setStyleSheet("""
            QWidget#user_list_widget { 
                background-color: #f8f6f0; 
                border-top-left-radius: 15px;
                border-bottom-left-radius: 15px;
            }
        """)
        self.user_list_widget.setObjectName("user_list_widget")
        layout = QtWidgets.QVBoxLayout(self.user_list_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with title
        header_container = QtWidgets.QWidget()
        header_container.setFixedHeight(55)
        header_container.setStyleSheet("""
            QWidget { 
                background-color: transparent; 
                border-bottom: 1px solid rgba(0,0,0,0.08);
            }
        """)
        header_layout = QtWidgets.QHBoxLayout(header_container)
        header_layout.setContentsMargins(20, 0, 15, 0)

        lbl_title = QtWidgets.QLabel("Tin nhắn")
        lbl_title.setStyleSheet("""
            font-size: 22px; 
            font-weight: bold; 
            color: #2c3e50;
            background: transparent;
        """)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        # Add group button (shown in group mode)
        self.btn_add_group = QtWidgets.QPushButton("+")
        self.btn_add_group.setFixedSize(32, 32)
        self.btn_add_group.setStyleSheet("""
            QPushButton { 
                background-color: #667eea; 
                color: white; 
                border-radius: 16px; 
                font-weight: bold; 
                font-size: 18px; 
            }
            QPushButton:hover { 
                background-color: #5a6fd6; 
            }
        """)
        self.btn_add_group.setToolTip("Tạo nhóm mới")
        self.btn_add_group.clicked.connect(self.open_create_group_dialog)
        self.btn_add_group.hide()
        header_layout.addWidget(self.btn_add_group)
        layout.addWidget(header_container)

        # Search box with icon
        search_container = QtWidgets.QWidget()
        search_container.setStyleSheet("background-color: transparent; padding: 8px 12px;")
        search_layout = QtWidgets.QHBoxLayout(search_container)
        search_layout.setContentsMargins(12, 10, 12, 10)

        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("🔍 Tìm kiếm...")
        self.search_box.setStyleSheet("""
            QLineEdit { 
                border: none; 
                border-radius: 18px; 
                padding: 10px 16px; 
                background-color: rgba(0,0,0,0.05); 
                color: #333333;
                font-size: 13px;
            }
            QLineEdit:focus { 
                background-color: rgba(255,255,255,0.8);
            }
        """)
        self.search_box.textChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_box)
        layout.addWidget(search_container)

        # Chat list scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent; 
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.15);
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0,0,0,0.25);
            }
        """)
        scroll_content = QtWidgets.QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.chat_list_layout = QtWidgets.QVBoxLayout(scroll_content)
        self.chat_list_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_list_layout.setSpacing(0)
        self.chat_list_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def setup_chat_area(self):
        self.chat_area_widget = QtWidgets.QWidget()
        self.chat_area_widget.setObjectName("chat_area_widget")
        self.chat_area_widget.setStyleSheet("""
            QWidget#chat_area_widget {
                background-color: #ffffff;
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }
        """)
        layout = QtWidgets.QVBoxLayout(self.chat_area_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_header = QtWidgets.QWidget()
        self.chat_header.setFixedHeight(65)
        self.chat_header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid rgba(0,0,0,0.06);")
        h_layout = QtWidgets.QHBoxLayout(self.chat_header)
        h_layout.setContentsMargins(15, 8, 15, 8)
        h_layout.setSpacing(12)
        
        # Header Avatar
        self.header_avatar = QtWidgets.QLabel()
        self.header_avatar.setFixedSize(45, 45)
        self.header_avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.header_avatar.setText("👤")
        self.header_avatar.setStyleSheet("background-color: #e8e8e8; border-radius: 22px; font-size: 18px;")
        h_layout.addWidget(self.header_avatar)

        # Container cho Text (Name + Status)
        text_container = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout(text_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)

        self.header_name_label = QtWidgets.QLabel("Chọn một người để chat")
        self.header_name_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1a1a1a;")
        v_layout.addWidget(self.header_name_label)

        # Status row with green dot
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(5)
        
        self.header_status_dot = QtWidgets.QLabel("●")
        self.header_status_dot.setStyleSheet("color: #22c55e; font-size: 10px;")
        self.header_status_dot.hide()
        status_row.addWidget(self.header_status_dot)
        
        self.header_status_label = QtWidgets.QLabel("")
        self.header_status_label.setStyleSheet("font-size: 13px; color: #22c55e;")
        self.header_status_label.hide()
        status_row.addWidget(self.header_status_label)
        status_row.addStretch()
        v_layout.addLayout(status_row)

        h_layout.addWidget(text_container)
        
        h_layout.addStretch()
        
        # Nút Gọi (Trên cùng bên phải)
        self.btn_call_header = QtWidgets.QPushButton("📞")
        self.btn_call_header.setFixedSize(38, 38)
        self.btn_call_header.setStyleSheet("""
            QPushButton { background-color: #f3f4f6; border-radius: 19px; font-size: 18px; border: none; }
            QPushButton:hover { background-color: #e5e7eb; }
        """)
        self.btn_call_header.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_call_header.clicked.connect(self.start_call)
        self.btn_call_header.hide()
        h_layout.addWidget(self.btn_call_header)
        
        # Nút Video Call
        self.btn_video_call = QtWidgets.QPushButton("📹")
        self.btn_video_call.setFixedSize(38, 38)
        self.btn_video_call.setStyleSheet("""
            QPushButton { background-color: #f3f4f6; border-radius: 19px; font-size: 18px; border: none; }
            QPushButton:hover { background-color: #e5e7eb; }
        """)
        self.btn_video_call.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_video_call.hide()
        h_layout.addWidget(self.btn_video_call)

        # Nút Gửi Vị Trí (Header - cho chat cá nhân)
        self.btn_location_header = QtWidgets.QPushButton("📍")
        self.btn_location_header.setFixedSize(38, 38)
        self.btn_location_header.setToolTip("Gửi vị trí hiện tại")
        self.btn_location_header.setStyleSheet("""
            QPushButton { background-color: #f3f4f6; border-radius: 19px; font-size: 18px; border: none; }
            QPushButton:hover { background-color: #e5e7eb; }
            QPushButton:disabled { background-color: #e5e7eb; color: #999; }
        """)
        self.btn_location_header.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_location_header.clicked.connect(self.send_location)
        self.btn_location_header.hide()
        h_layout.addWidget(self.btn_location_header)

        # Nút Thêm Thành Viên
        self.btn_add_member = QtWidgets.QPushButton("➕")
        self.btn_add_member.setFixedSize(38, 38)
        self.btn_add_member.setToolTip("Thêm thành viên")
        self.btn_add_member.setStyleSheet("QPushButton { background-color: #f3f4f6; border-radius: 19px; font-size: 16px; border: none; } QPushButton:hover { background-color: #e5e7eb; }")
        self.btn_add_member.clicked.connect(self.add_member_to_group)
        self.btn_add_member.hide()
        h_layout.addWidget(self.btn_add_member)

        # Nút Rời Nhóm
        self.btn_leave_group = QtWidgets.QPushButton("🚪")
        self.btn_leave_group.setFixedSize(38, 38)
        self.btn_leave_group.setToolTip("Rời nhóm")
        self.btn_leave_group.setStyleSheet("QPushButton { background-color: #fef2f2; border-radius: 19px; font-size: 16px; border: none; } QPushButton:hover { background-color: #fee2e2; }")
        self.btn_leave_group.clicked.connect(self.leave_group)
        self.btn_leave_group.hide()
        h_layout.addWidget(self.btn_leave_group)

        # Nút Xem Thành Viên
        self.btn_view_members = QtWidgets.QPushButton("📄")
        self.btn_view_members.setFixedSize(38, 38)
        self.btn_view_members.setToolTip("Xem danh sách thành viên")
        self.btn_view_members.setStyleSheet("QPushButton { background-color: #f3f4f6; border-radius: 19px; font-size: 16px; border: none; } QPushButton:hover { background-color: #e5e7eb; }")
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

        # ==========================================
        # INPUT BAR - Blends with chat area background
        # Elements float above the background
        # ==========================================
        input_container = QtWidgets.QWidget()
        input_container.setObjectName("input_container")
        input_container.setStyleSheet("""
            QWidget#input_container { 
                background-color: transparent;
            }
        """)
        input_container.setFixedHeight(75)
        inp_layout = QtWidgets.QHBoxLayout(input_container)
        inp_layout.setContentsMargins(20, 8, 20, 18)
        inp_layout.setSpacing(10)

        # Floating icon button style - appears to float on chat background
        floating_btn_style = """
            QPushButton { 
                background-color: rgba(248, 248, 248, 0.95);
                border: none;
                border-radius: 22px;
                font-size: 20px;
            }
            QPushButton:hover { 
                background-color: rgba(240, 240, 240, 1.0);
            }
            QPushButton:pressed {
                background-color: rgba(230, 230, 230, 1.0);
            }
        """

        # Image button - Neumorphic floating
        self.btn_img = QtWidgets.QPushButton("🖼️")
        self.btn_img.setFixedSize(44, 44)
        self.btn_img.setToolTip("Gửi ảnh")
        self.btn_img.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_img.setStyleSheet(floating_btn_style)
        self.btn_img.clicked.connect(self.send_image)
        inp_layout.addWidget(self.btn_img)
        
        # Camera button - Capture photo directly
        self.btn_camera = QtWidgets.QPushButton("📷")
        self.btn_camera.setFixedSize(44, 44)
        self.btn_camera.setToolTip("Chụp ảnh")
        self.btn_camera.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_camera.setStyleSheet(floating_btn_style)
        self.btn_camera.clicked.connect(self.capture_photo)
        inp_layout.addWidget(self.btn_camera)
        
        # Video button - Neumorphic floating
        self.btn_vid = QtWidgets.QPushButton("🎬")
        self.btn_vid.setFixedSize(44, 44)
        self.btn_vid.setToolTip("Gửi video")
        self.btn_vid.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_vid.setStyleSheet(floating_btn_style)
        self.btn_vid.clicked.connect(self.send_video)
        inp_layout.addWidget(self.btn_vid)
        
        # File button - Neumorphic floating
        self.btn_file = QtWidgets.QPushButton("📎")
        self.btn_file.setFixedSize(44, 44)
        self.btn_file.setToolTip("Gửi file (txt, pdf, docx, xlsx)")
        self.btn_file.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_file.setStyleSheet(floating_btn_style)
        self.btn_file.clicked.connect(self.send_file)
        inp_layout.addWidget(self.btn_file)

        # Mic button - Neumorphic floating
        self.btn_mic = QtWidgets.QPushButton("🎤")
        self.btn_mic.setFixedSize(44, 44)
        self.btn_mic.setToolTip("Giữ để ghi âm")
        self.btn_mic.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_mic.setStyleSheet("""
            QPushButton { 
                background-color: #ffffff;
                border: none;
                border-radius: 22px;
                font-size: 20px;
            }
            QPushButton:hover { 
                background-color: #fafafa;
            }
            QPushButton:pressed {
                background-color: #ffe0e0;
            }
        """)
        self.btn_mic.pressed.connect(self.start_recording)
        self.btn_mic.released.connect(self.stop_recording)
        inp_layout.addWidget(self.btn_mic)

        # Message input - Pill-shaped Neumorphic style with floating effect
        self.message_input = QtWidgets.QLineEdit()
        self.message_input.setPlaceholderText("Nhập tin nhắn...")
        self.message_input.setStyleSheet("""
            QLineEdit { 
                background-color: #ffffff;
                border: none;
                border-radius: 25px; 
                padding: 14px 22px; 
                font-size: 14px; 
                color: #333333; 
            }
            QLineEdit:focus {
                background-color: #ffffff;
            }
            QLineEdit::placeholder {
                color: #aaaaaa;
            }
        """)
        self.message_input.setMinimumHeight(50)
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.textChanged.connect(self.handle_typing_input)
        inp_layout.addWidget(self.message_input)

        # Emoji button - Neumorphic floating
        self.btn_emoji = QtWidgets.QPushButton("😊")
        self.btn_emoji.setFixedSize(44, 44)
        self.btn_emoji.setToolTip("Emoji")
        self.btn_emoji.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_emoji.setStyleSheet(floating_btn_style)
        self.btn_emoji.clicked.connect(self.show_emoji_picker)
        inp_layout.addWidget(self.btn_emoji)
        
        # Send button - Gradient blue/purple Neumorphic
        self.btn_send = QtWidgets.QPushButton("➤")
        self.btn_send.setFixedSize(44, 44)
        self.btn_send.setToolTip("Gửi")
        self.btn_send.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; 
                font-size: 18px; 
                border-radius: 22px;
                border: none;
            } 
            QPushButton:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #5a6fd6, stop:1 #6a3f92);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #4e5fc6, stop:1 #5a3582);
            }
        """)
        self.btn_send.clicked.connect(self.send_message)
        inp_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

    def _create_icon_button(self, text, color, tooltip):
        """Create floating icon button with rounded background"""
        btn = QtWidgets.QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(38, 38)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: rgba(255, 255, 255, 0.9); 
                color: {color}; 
                font-size: 16px; 
                border-radius: 19px;
                border: 1px solid rgba(0,0,0,0.08);
            }} 
            QPushButton:hover {{ 
                background-color: #ffffff;
                border: 1px solid {color}50;
            }}
            QPushButton:pressed {{
                background-color: {color}15;
            }}
        """)
        return btn

    # --- Logic ---
    def switch_to_user_mode(self):
        self.current_mode = "user"
        self._clear_chat_ui()
        self.stack.setCurrentIndex(0)
        
        # Update button active states
        self.btn_chat_one.setProperty("active", True)
        self.btn_chat_group.setProperty("active", False)
        self.btn_ai_chat.setProperty("active", False)
        if hasattr(self, 'btn_settings'): self.btn_settings.setProperty("active", False)
        # Refresh styles
        self.btn_chat_one.style().unpolish(self.btn_chat_one)
        self.btn_chat_one.style().polish(self.btn_chat_one)
        self.btn_chat_group.style().unpolish(self.btn_chat_group)
        self.btn_chat_group.style().polish(self.btn_chat_group)
        self.btn_ai_chat.style().unpolish(self.btn_ai_chat)
        self.btn_ai_chat.style().polish(self.btn_ai_chat)
        
        self.btn_add_group.hide()
        self.header_name_label.setText("Chọn một người để chat")
        if hasattr(self, 'header_status_dot'): self.header_status_dot.hide()
        self.header_status_label.hide()
        if hasattr(self, 'header_avatar'): 
            self.header_avatar.setText("👤")
            self.header_avatar.setStyleSheet("background-color: #e8e8e8; border-radius: 22px; font-size: 18px;")
        if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
        if hasattr(self, 'btn_video_call'): self.btn_video_call.hide()

        self.load_users()

    def switch_to_group_mode(self):
        self.current_mode = "group"
        self._clear_chat_ui()
        self.stack.setCurrentIndex(0)
        
        # Update button active states
        self.btn_chat_one.setProperty("active", False)
        self.btn_chat_group.setProperty("active", True)
        self.btn_ai_chat.setProperty("active", False)
        if hasattr(self, 'btn_settings'): self.btn_settings.setProperty("active", False)
        # Refresh styles
        self.btn_chat_one.style().unpolish(self.btn_chat_one)
        self.btn_chat_one.style().polish(self.btn_chat_one)
        self.btn_chat_group.style().unpolish(self.btn_chat_group)
        self.btn_chat_group.style().polish(self.btn_chat_group)
        self.btn_ai_chat.style().unpolish(self.btn_ai_chat)
        self.btn_ai_chat.style().polish(self.btn_ai_chat)
        
        self.btn_add_group.show()
        self.header_name_label.setText("Chọn một nhóm để chat")
        if hasattr(self, 'header_status_dot'): self.header_status_dot.hide()
        self.header_status_label.hide()
        if hasattr(self, 'header_avatar'): 
            self.header_avatar.setText("👥")
            self.header_avatar.setStyleSheet("background-color: #e8e8e8; border-radius: 22px; font-size: 18px;")
        if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
        if hasattr(self, 'btn_video_call'): self.btn_video_call.hide()

        if hasattr(self, 'btn_add_member'): self.btn_add_member.hide()
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
        self.stack.setCurrentIndex(1)  # Chuyển sang chat AI
        
        # Update button active states
        self.btn_chat_one.setProperty("active", False)
        self.btn_chat_group.setProperty("active", False)
        self.btn_ai_chat.setProperty("active", True)
        if hasattr(self, 'btn_settings'): self.btn_settings.setProperty("active", False)
        
        # Refresh styles
        self.btn_chat_one.style().unpolish(self.btn_chat_one)
        self.btn_chat_one.style().polish(self.btn_chat_one)
        self.btn_chat_group.style().unpolish(self.btn_chat_group)
        self.btn_chat_group.style().polish(self.btn_chat_group)
        self.btn_ai_chat.style().unpolish(self.btn_ai_chat)
        self.btn_ai_chat.style().polish(self.btn_ai_chat)


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

        # Cập nhật header name (không cần icon nữa vì có avatar)
        self.header_name_label.setText(display_name)
        
        # Cập nhật header avatar
        avatar = None
        if item_type == "user":
            avatar = self.user_avatars.get(target_id)
        # Set avatar
        if avatar:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(avatar))
                rounded = QtGui.QPixmap(45, 45)
                rounded.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 45, 45)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(45, 45, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                self.header_avatar.setPixmap(rounded)
                self.header_avatar.setStyleSheet("background-color: transparent;")
            except:
                self.header_avatar.setText("👤")
                self.header_avatar.setStyleSheet("background-color: #e8e8e8; border-radius: 22px; font-size: 18px;")
        else:
            self.header_avatar.setText("👥" if item_type == "group" else "👤")
            self.header_avatar.setStyleSheet("background-color: #e8e8e8; border-radius: 22px; font-size: 18px;")
        
        # Cập nhật trạng thái hiển thị trên Header (chỉ cho mode user)
        if item_type == "user":
            status = self.user_statuses.get(target_id, "offline")
            self.update_header_status_display(target_id, status)
        else:
            self.header_status_dot.hide()
            self.header_status_label.hide()

        # Hiện/Ẩn các nút action tùy theo mode
        if item_type == "group":
            # Ẩn các nút chat 1-1
            if hasattr(self, 'btn_call_header'): self.btn_call_header.hide()
            if hasattr(self, 'btn_video_call'): self.btn_video_call.hide()

            # Hiện các nút nhóm và location
            if hasattr(self, 'btn_add_member'): self.btn_add_member.show()
            if hasattr(self, 'btn_location_header'): self.btn_location_header.show()
            if hasattr(self, 'btn_view_members'): self.btn_view_members.show()
            if hasattr(self, 'btn_leave_group'): self.btn_leave_group.show()
        else:
            # Hiện các nút chat 1-1 và location
            if hasattr(self, 'btn_call_header'): self.btn_call_header.show()
            if hasattr(self, 'btn_video_call'): self.btn_video_call.show()
            if hasattr(self, 'btn_location_header'): self.btn_location_header.show()

            # Ẩn các nút nhóm
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
                elif msg.get("is_file"):
                    self.add_message_to_chat(msg["message"], name, is_self, is_file=True, file_data=msg.get("file_data"), file_size=msg.get("file_size", 0), avatar_base64=avatar)
                elif msg.get("is_system"):
                     self.add_system_message(msg["message"])
                else:
                    # Auto-detect location snapshot message
                    content = msg.get("message", "")
                    is_location = False
                    try:
                        if content.startswith('{"type":"location"') or content.startswith('{"type": "location"'):
                            data = json.loads(content)
                            if data.get("type") == "location":
                                import time
                                ts = data.get("ts", 0)
                                duration = data.get("duration", 0)
                                
                                # Kiểm tra nếu location đã bị dừng thủ công
                                if ts in self.stopped_location_ids:
                                    continue
                                
                                # Kiểm tra xem location đã hết hạn chưa
                                if duration > 0 and ts > 0:
                                    expire_time = ts + (duration * 60)
                                    if time.time() > expire_time:
                                        # Tin nhắn vị trí đã hết hạn, bỏ qua không hiển thị
                                        continue
                                
                                is_location = True
                    except:
                        pass
                    
                    self.add_message_to_chat(content, name, is_self, is_location=is_location, avatar_base64=avatar)
            
            # Buộc cuộn xuống dưới cùng sau khi cập nhật layout
            QtCore.QTimer.singleShot(100, self.scroll_to_bottom)

        except Exception as e:
            print(f"Lỗi load history: {e}")

    def scroll_to_bottom(self):
        js = self.chat_scroll.verticalScrollBar()
        js.setValue(js.maximum())

    def add_message_to_chat(self, message, sender_name, is_self=False, is_image=False, is_voice=False, is_video=False, is_call_log=False, is_file=False, file_data=None, file_size=0,
                            avatar_base64=None, is_location=False):
        try:
            bubble = self.create_message_bubble(message, sender_name, is_self, is_image, is_voice, is_video, is_call_log, is_file, file_data, file_size,
                                                avatar_base64, is_location)
            self.chat_messages_layout.insertWidget(self.chat_messages_layout.count() - 1, bubble)
            QtCore.QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()))
        except Exception as e:
            print(f"Lỗi add msg: {e}")

    def create_message_bubble(self, message, sender_name, is_self, is_image, is_voice, is_video, is_call_log, is_file, file_data, file_size, avatar_base64, is_location=False):
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
            # VoiceMessageWidget has its own styling built-in
            content_layout.addWidget(msg_widget)
        elif is_video:
            msg_widget = VideoMessageWidget(message, is_self)
            content_layout.addWidget(msg_widget)
        elif is_file:
            msg_widget = FileMessageWidget(message, file_data, file_size, is_self)
            # Gradient background for file similar to voice
            msg_widget.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {'#667eea' if is_self else '#7f8c8d'}, stop:1 {'#764ba2' if is_self else '#95a5a6'}); border-radius: 15px;")
            content_layout.addWidget(msg_widget)
        elif is_image:
            msg_widget = ImageMessageWidget(message, is_self)
            content_layout.addWidget(msg_widget)
        elif is_location:
            # Parse location JSON và hiển thị widget
            try:
                loc_data = json.loads(message)
                lat = loc_data.get("lat", 0)
                lng = loc_data.get("lng", 0)
                address = loc_data.get("address", "")
                location_id = loc_data.get("ts", 0)  # Dùng timestamp làm ID
                duration = loc_data.get("duration", 0)
                
                msg_widget = LocationMessageWidget(
                    lat, lng, address, is_self,
                    duration_minutes=duration,
                    location_id=location_id,
                    receiver_id=self.current_receiver_id if is_self else None,
                    main_view=self if is_self else None
                )
                content_layout.addWidget(msg_widget)
            except:
                # Fallback nếu parse lỗi
                lbl_msg = QtWidgets.QLabel(f"📍 Vị trí: {message}")
                lbl_msg.setWordWrap(True)
                lbl_msg.setStyleSheet(
                    f"background-color: {'#667eea' if is_self else 'white'}; color: {'white' if is_self else 'black'}; padding: 10px 15px; border-radius: 15px;")
                content_layout.addWidget(lbl_msg)
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
        
        # === MODERATION CHECK (Decision Engine: AI + Rule-based) ===
        mod_result = self.moderation_controller.check_outgoing_text(msg)
        action = mod_result.get("action", "ALLOW")
        
        # --- MỨC 3: BLOCK (Chặn hoàn toàn) ---
        if action == "BLOCK":
            QtWidgets.QMessageBox.critical(
                self, 
                "Tin nhắn bị chặn", 
                mod_result.get("reason", "Tin nhắn vi phạm tiêu chuẩn cộng đồng.")
            )
            # KHÔNG gửi tin nhắn, chỉ xóa input
            self.message_input.clear()
            return
        
        # --- MỨC 2: WARN (Cảnh báo, che từ xấu) ---
        if action == "WARN":
            QtWidgets.QMessageBox.warning(
                self, 
                "Cảnh báo", 
                mod_result.get("reason", "Tin nhắn có ngôn từ không phù hợp.")
            )
            # Gửi tin nhắn đã che từ xấu
            message_to_send = mod_result.get("final_text", msg)
        else:
            # --- MỨC 1: ALLOW (Gửi bình thường) ---
            message_to_send = msg
        
        # === END MODERATION CHECK ===
        
        try:
            if self.current_mode == "user":
                resp = self.controller.send_message(self.current_receiver_id, message_to_send)
            else:
                resp = self.controller.send_group_message(self.current_receiver_id, message_to_send)
            
            if resp:
                # === XỬ LÝ PHẢN HỒI TỪ SERVER ===
                if resp.get("status") == "success":
                    self.add_message_to_chat(message_to_send, "Bạn", True, avatar_base64=self.self_avatar)
                    self.message_input.clear()
                    
                elif resp.get("code") == "MESSAGE_BLOCKED":
                    # SERVER ĐÃ CHẶN TIN NHẮN (Vi phạm nghiêm trọng - Layer 1: SEVERE)
                    server_msg = resp.get("message", "Tin nhắn bị chặn do vi phạm nghiêm trọng.")
                    hits = resp.get("hits", [])
                    
                    # Hiển thị cảnh báo nghiêm trọng
                    warning_text = f"{server_msg}\n\nTin nhắn của bạn sẽ KHÔNG được gửi đi."
                    if hits:
                        warning_text += f"\n\nTừ vi phạm: {', '.join(hits)}"
                    
                    QtWidgets.QMessageBox.critical(
                        self,
                        "⛔ TIN NHẮN BỊ CHẶN",
                        warning_text
                    )
                    self.message_input.clear()
                    
                else:
                    # Lỗi khác từ server
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Lỗi",
                        resp.get("message", "Không thể gửi tin nhắn.")
                    )
        except Exception as e:
            print(e)

    def capture_photo(self):
        """Mở dialog chụp ảnh từ camera."""
        if not self.current_receiver_id:
            return
        dialog = CameraCaptureDialog(self)
        dialog.photo_ready.connect(self._on_photo_captured)
        dialog.exec()
    
    def _on_photo_captured(self, image_data_b64):
        """Xử lý khi user chụp và confirm ảnh."""
        if self.current_mode == "user":
            self.controller.send_image(self.current_receiver_id, image_data_b64, "camera_capture.jpg")
            self.add_message_to_chat(image_data_b64, "Bạn", True, is_image=True, avatar_base64=self.self_avatar)
        else:
            self.controller.send_group_message(self.current_receiver_id, "", is_image=True, image_data=image_data_b64)
            self.add_message_to_chat(image_data_b64, "Bạn", True, is_image=True, avatar_base64=self.self_avatar)

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

    def send_file(self):
        """Gửi file tài liệu (txt, pdf, docx, xlsx) trong chat 1-1."""
        if not self.current_receiver_id: return
        if self.current_mode != "user":
            QtWidgets.QMessageBox.warning(self, "Thông báo", "Chức năng gửi file chỉ hỗ trợ chat 1-1.")
            return
        
        # Định dạng file được phép
        ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx', '.xlsx'}
        
        # Giới hạn kích thước (bytes)
        SIZE_LIMITS = {
            '.txt': 2 * 1024 * 1024,      # 2MB cho txt
            '.pdf': 10 * 1024 * 1024,     # 10MB
            '.docx': 10 * 1024 * 1024,    # 10MB
            '.xlsx': 10 * 1024 * 1024,    # 10MB
        }
        
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            "Chọn file", 
            "", 
            "Documents (*.txt *.pdf *.docx *.xlsx)"
        )
        
        if not file_path:
            return
        
        # Lấy extension
        filename = os.path.basename(file_path)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        # Kiểm tra định dạng
        if ext not in ALLOWED_EXTENSIONS:
            QtWidgets.QMessageBox.warning(
                self, 
                "Định dạng không hỗ trợ", 
                f"Chỉ hỗ trợ các định dạng: txt, pdf, docx, xlsx\n\nFile của bạn: {ext}"
            )
            return
        
        # Kiểm tra kích thước
        file_size = os.path.getsize(file_path)
        max_size = SIZE_LIMITS.get(ext, 10 * 1024 * 1024)
        
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            current_mb = file_size / (1024 * 1024)
            QtWidgets.QMessageBox.warning(
                self, 
                "File quá lớn", 
                f"File {ext} không được vượt quá {max_mb:.0f}MB.\n\nFile của bạn: {current_mb:.1f}MB"
            )
            return
        
        try:
            with open(file_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            
            resp = self.controller.send_file(self.current_receiver_id, data, filename, file_size)
            
            if resp and resp.get("status") == "success":
                # Hiển thị tin nhắn file đã gửi
                self.add_message_to_chat(filename, "Bạn", True, is_file=True, file_data=data, file_size=file_size, avatar_base64=self.self_avatar)
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", "Không thể gửi file. Vui lòng thử lại.")
        except Exception as e:
            print(f"Lỗi gửi file: {e}")
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể gửi file: {e}")

    def send_location(self):
        """Gửi vị trí hiện tại của người dùng."""
        if not self.current_receiver_id: 
            return
        
        # Dialog chọn thời gian chia sẻ
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("📍 Chia sẻ vị trí")
        dialog.setModal(True)
        dialog.resize(280, 180)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("Chọn thời gian chia sẻ:")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Duration options
        duration_combo = QtWidgets.QComboBox()
        duration_combo.addItems([
            "1 phút",
            "2 phút",
            "5 phút",
            "Cho đến khi tôi dừng"
        ])
        duration_combo.setCurrentIndex(1)  # Default 2 phút
        duration_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(duration_combo)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        share_btn = QtWidgets.QPushButton("📍 Chia sẻ")
        share_btn.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a6fd6; }
        """)
        
        cancel_btn = QtWidgets.QPushButton("Hủy")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                padding: 10px 20px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        
        btn_layout.addStretch()
        btn_layout.addWidget(share_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        share_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        
        # Get duration in minutes
        duration_map = {0: 1, 1: 2, 2: 5, 3: 0}  # 0 = unlimited
        duration_minutes = duration_map.get(duration_combo.currentIndex(), 2)
        
        self.btn_location_header.setEnabled(False)
        self.btn_location_header.setText("⏳")
        
        def get_location():
            """
            Lấy vị trí chính xác bằng nhiều phương pháp:
            1. PowerShell + Windows Location API (chính xác nhất, dùng GPS/WiFi)
            2. ipinfo.io (IP geolocation, fallback)
            3. geocoder.ip (last fallback)
            """
            try:
                # === METHOD 1: PowerShell + Windows Location API ===
                try:
                    import subprocess
                    import sys
                    
                    if sys.platform == 'win32':
                        # PowerShell script để lấy vị trí từ Windows Location API
                        ps_script = '''
Add-Type -AssemblyName System.Device
$watcher = New-Object System.Device.Location.GeoCoordinateWatcher
$watcher.Start()
$count = 0
while ($watcher.Status -ne "Ready" -and $count -lt 50) {
    Start-Sleep -Milliseconds 100
    $count++
}
if ($watcher.Status -eq "Ready") {
    $coord = $watcher.Position.Location
    if ($coord.Latitude -ne [double]::NaN) {
        Write-Output "$($coord.Latitude),$($coord.Longitude)"
    }
}
$watcher.Stop()
'''
                        result = subprocess.run(
                            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                            capture_output=True, text=True, timeout=8,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        
                        output = result.stdout.strip()
                        if output and ',' in output:
                            parts = output.split(',')
                            if len(parts) == 2:
                                lat, lng = float(parts[0]), float(parts[1])
                                
                                # Reverse geocode để lấy địa chỉ
                                import geocoder
                                g = geocoder.osm([lat, lng], method='reverse')
                                address = g.address if g.ok else f"Lat: {lat:.6f}, Lng: {lng:.6f}"
                                
                                return {
                                    "success": True,
                                    "lat": lat,
                                    "lng": lng,
                                    "address": address,
                                    "method": "Windows GPS"
                                }
                except Exception as e:
                    print(f"[Location] PowerShell Windows API failed: {e}")
                
                # === METHOD 2: WiFi-based via ipinfo.io (free, better than IP) ===
                try:
                    import requests
                    
                    # ipinfo.io cho kết quả chính xác hơn geocoder.ip('me')
                    response = requests.get('https://ipinfo.io/json', timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        loc = data.get('loc', '').split(',')
                        if len(loc) == 2:
                            lat, lng = float(loc[0]), float(loc[1])
                            city = data.get('city', '')
                            region = data.get('region', '')
                            country = data.get('country', '')
                            address = ', '.join(filter(None, [city, region, country])) or "Không xác định"
                            
                            return {
                                "success": True,
                                "lat": lat,
                                "lng": lng,
                                "address": address,
                                "method": "IP Geolocation"
                            }
                except Exception as e:
                    print(f"[Location] ipinfo.io failed: {e}")
                
                # === METHOD 3: Fallback to geocoder (least accurate) ===
                import geocoder
                g = geocoder.ip('me')
                if g.ok:
                    return {
                        "success": True,
                        "lat": g.latlng[0],
                        "lng": g.latlng[1],
                        "address": g.address or g.city or "Không xác định",
                        "method": "IP Fallback"
                    }
                else:
                    return {"success": False, "error": "Không thể lấy vị trí từ bất kỳ nguồn nào"}
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        def on_location_ready(result):
            self.btn_location_header.setEnabled(True)
            self.btn_location_header.setText("📍")
            
            if result.get("success"):
                lat = result["lat"]
                lng = result["lng"]
                address = result["address"]
                
                # Tạo Location Snapshot JSON
                import time
                location_data = json.dumps({
                    "type": "location",
                    "lat": lat,
                    "lng": lng,
                    "address": address,
                    "ts": int(time.time()),
                    "duration": duration_minutes
                })
                
                if self.current_mode == "user":
                    self.controller.send_message(self.current_receiver_id, location_data)
                    self.add_message_to_chat(location_data, "Bạn", True, is_location=True, avatar_base64=self.self_avatar)
                else:
                    self.controller.send_group_message(self.current_receiver_id, location_data)
                    self.add_message_to_chat(location_data, "Bạn", True, is_location=True, avatar_base64=self.self_avatar)
            else:
                _show_styled_message(self, 'warning', "Không thể lấy vị trí", result.get("error", "Lỗi không xác định"))
        
        # Run in thread
        class LocationWorker(QtCore.QThread):
            finished = QtCore.Signal(dict)
            
            def run(self):
                result = get_location()
                self.finished.emit(result)
        
        self.location_worker = LocationWorker()
        self.location_worker.finished.connect(on_location_ready)
        self.location_worker.start()


    def start_call(self):
        if not self.current_receiver_id:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn người để gọi.")
            return
        
        # 1. Hiện ActiveCallDialog (Trạng thái Người gọi)
        self.call_target_id = self.current_receiver_id  # Lưu target ID để gửi audio
        self.active_call_dialog = ActiveCallDialog(self.current_receiver_name, self.user_avatars.get(self.current_receiver_id), is_caller=True, parent=self)
        self.active_call_dialog.hangup_signal.connect(lambda: self.end_call_remote(self.current_receiver_id))
        self.active_call_dialog.audio_data_signal.connect(self._send_audio_data)  # Kết nối audio streaming
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
            
            self.call_target_id = None  # Reset call target
            
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
        
        elif signal_type == "audio_data":
            # Nhận audio data từ người gọi và phát qua loa
            if self.active_call_dialog:
                try:
                    audio_b64 = msg.get("audio", "")
                    if audio_b64:
                        import base64
                        audio_bytes = base64.b64decode(audio_b64)
                        self.active_call_dialog.play_audio_data(audio_bytes)
                except Exception as e:
                    print(f"[AudioCall] Error playing received audio: {e}")
        
        elif signal_type == "stop_location":
            # Xóa LocationMessageWidget ở receiver khi sender dừng chia sẻ
            location_id = msg.get("location_id", 0)
            if location_id:
                self.remove_location_widget(location_id)

    def remove_location_widget(self, location_id):
        """Tìm và xóa toàn bộ tin nhắn vị trí (cả bubble) theo location_id - xóa sạch không để tồn dư."""
        # Đánh dấu đã dừng để không load lại từ DB
        self.stopped_location_ids.add(location_id)
        
        for i in range(self.chat_messages_layout.count()):
            item = self.chat_messages_layout.itemAt(i)
            if item and item.widget():
                bubble = item.widget()
                # Tìm LocationMessageWidget bên trong bubble
                for child in bubble.findChildren(LocationMessageWidget):
                    if hasattr(child, 'location_id') and child.location_id == location_id:
                        child.is_active = False
                        
                        # Cleanup tất cả children trước
                        for w in bubble.findChildren(QtWidgets.QWidget):
                            w.setParent(None)
                            w.deleteLater()
                        
                        # Xóa khỏi layout
                        self.chat_messages_layout.removeWidget(bubble)
                        
                        # Xóa bubble
                        bubble.setParent(None)
                        bubble.deleteLater()
                        
                        # Force update layout
                        self.chat_messages_layout.update()
                        QtCore.QCoreApplication.processEvents()
                        return

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
        self.call_target_id = sender_id  # Lưu target ID để gửi audio
        self.active_call_dialog = ActiveCallDialog(name, avatar, is_caller=False, parent=self)
        self.active_call_dialog.audio_data_signal.connect(self._send_audio_data)  # Kết nối audio streaming
        self.active_call_dialog.start_timer()
        self.active_call_dialog.show()
        
        # 3. Gửi tín hiệu chấp nhận
        self.controller.send_signal(sender_id, "call_accepted")
        
        # Xử lý dập máy
        self.active_call_dialog.hangup_signal.connect(lambda: self.end_call_remote(sender_id))
    
    def _send_audio_data(self, audio_bytes: bytes):
        """Gửi audio data đến người đang gọi."""
        if self.call_target_id:
            try:
                import base64
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                self.controller.send_signal(self.call_target_id, "audio_data", {
                    "audio": audio_b64
                })
            except Exception as e:
                print(f"[AudioCall] Error sending audio: {e}")

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
        
        # 4. Reset call target
        self.call_target_id = None


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
                        new_avatar = msg.get("avatar")  # Server giờ gửi avatar
                        # EMIT SIGNAL với đầy đủ thông tin (KHÔNG GỌI HÀM UI TRỰC TIẾP)
                        self.profile_updated_signal.emit(updated_uid, new_name, new_avatar)
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
                    file_data = None
                    file_size = 0

                    if msg.get('is_image'):
                        t = 'image'; content = msg.get('image_data')
                    elif msg.get('is_voice'):
                        t = 'voice'; content = msg.get('voice_data')
                    elif msg.get('is_video'):
                        t = 'video'; content = msg.get('video_data')
                    elif msg.get('is_file'):
                        t = 'file'
                        # Content is filename from server
                        file_data = msg.get('file_data')
                        file_size = int(msg.get('file_size', 0))
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
                        self.message_received.emit(content, sender_name, t, target_id_for_signal, sender_id, sender_avatar, is_system, file_data, file_size)
                    else:
                        # Show toast notification for messages from other chats
                        moderation = msg.get('moderation')  # May contain {action, final_text}
                        self.show_notification_signal.emit(
                            sender_id, sender_name, sender_avatar, 
                            content, t, group_id, moderation
                        )
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

    @QtCore.Slot(int, str, object)
    def handle_profile_update_ui(self, user_id, display_name, avatar):
        """
        Cập nhật UI khi nhận profile update notification.
        
        Tối ưu cho multi-client:
        - Không gọi get_users() blocking trên UI thread
        - Dùng data từ notification để update cache ngay
        - Background sync để đảm bảo đồng bộ đầy đủ
        """
        try:
            # 1. Cập nhật cache NGAY TỪ NOTIFICATION (không cần network call)
            if display_name:
                self.user_names[user_id] = display_name
            if avatar is not None:  # None check vì avatar có thể là "" (empty string)
                self.user_avatars[user_id] = avatar
            
            # 1b. CẬP NHẬT all_users LIST (để update_list_display hoạt động ngay)
            for user in self.all_users:
                if user.get("user_id") == user_id:
                    if display_name:
                        user["display_name"] = display_name
                    if avatar is not None:
                        user["avatar"] = avatar
                    break
            
            # 2. Cập nhật sidebar nếu là bản thân
            if user_id == self.user_id:
                self.display_name = display_name
                # Refresh sidebar avatar
                if avatar:
                    try:
                        pix = QtGui.QPixmap()
                        pix.loadFromData(base64.b64decode(avatar))
                        rounded = QtGui.QPixmap(45, 45)
                        rounded.fill(QtCore.Qt.GlobalColor.transparent)
                        painter = QtGui.QPainter(rounded)
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                        path = QtGui.QPainterPath()
                        path.addEllipse(0, 0, 45, 45)
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, pix.scaled(45, 45, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                        painter.end()
                        self.sidebar_avatar.setIcon(QtGui.QIcon(rounded))
                        self.self_avatar = avatar
                    except Exception as e:
                        print(f"[ProfileUpdate] Error updating sidebar avatar: {e}")

            # 3. Cập nhật Header nếu đang chat với người đó
            if self.current_mode == "user" and self.current_receiver_id == user_id:
                self.current_receiver_name = display_name
                self.header_name_label.setText(display_name)
                # Cập nhật avatar header
                if avatar:
                    try:
                        pix = QtGui.QPixmap()
                        pix.loadFromData(base64.b64decode(avatar))
                        rounded = QtGui.QPixmap(45, 45)
                        rounded.fill(QtCore.Qt.GlobalColor.transparent)
                        painter = QtGui.QPainter(rounded)
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                        path = QtGui.QPainterPath()
                        path.addEllipse(0, 0, 45, 45)
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, pix.scaled(45, 45, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                        painter.end()
                        self.header_avatar.setPixmap(rounded)
                    except:
                        pass

            # 4. Reload danh sách UI (chỉ cập nhật display, không fetch lại)
            try:
                self.update_list_display(self.search_box.text())
            except Exception as e:
                print(f"[ProfileUpdate] Error updating list: {e}")

            # 5. Reload chat hiện tại nếu cần (để cập nhật avatar trong tin nhắn)
            if self.current_receiver_id and (self.current_receiver_id == user_id or user_id == self.user_id):
                try:
                    self.reload_current_chat()
                except Exception as e:
                    print(f"[ProfileUpdate] Error reloading chat: {e}")

        except Exception as e:
            print(f"[ProfileUpdate] Error in handle_profile_update_ui: {e}")
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
            self.header_status_dot.show()
            self.header_status_label.setText("Online")
            self.header_status_label.setStyleSheet("font-size: 13px; color: #22c55e;")
            self.header_status_label.show()
        else:
            self.header_status_dot.hide()
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
                    self.header_status_label.setStyleSheet("font-size: 13px; color: #6b7280;")
                    self.header_status_label.show()
                except ValueError:
                    self.header_status_label.setText("Offline")
                    self.header_status_label.setStyleSheet("font-size: 13px; color: #6b7280;")
                    self.header_status_label.show()
            else:
                self.header_status_label.setText("Offline")
                self.header_status_label.setStyleSheet("font-size: 13px; color: #6b7280;")
                self.header_status_label.show()

    def display_incoming_message(self, message, sender_name, message_type, target_id, sender_id=None, sender_avatar=None, is_system=False, file_data=None, file_size=0):
        is_img = (message_type == 'image')
        is_voice = (message_type == 'voice')
        is_video = (message_type == 'video')
        is_file = (message_type == 'file')
        is_call_log = (message_type == 'call_log')
        
        # Auto-detect Location Snapshot message
        is_location = False
        if message_type == 'text' or message_type is None:
            try:
                if message.startswith('{"type":"location"') or message.startswith('{"type": "location"'):
                    data = json.loads(message)
                    if data.get("type") == "location":
                        is_location = True
            except:
                pass
        
        # Ưu tiên dùng avatar từ message (mới nhất), nếu không có thì dùng cache
        avatar = sender_avatar
        if not avatar and sender_id and sender_id in self.user_avatars:
            avatar = self.user_avatars[sender_id]
        elif not avatar and self.current_mode == "user" and target_id in self.user_avatars:
            avatar = self.user_avatars[target_id]
        
        if is_system:
             self.add_system_message(message)
             return

        self.add_message_to_chat(message, sender_name, False, is_img, is_voice, is_video, is_call_log, is_file, file_data, file_size, avatar, is_location)

    def refresh_self_profile(self):
        try:
            resp = self.controller.get_profile()
            if resp.get('status') == 'success':
                self.display_name = resp.get('display_name', self.display_name)
                self.self_avatar = resp.get('avatar')
                if self.self_avatar:
                    try:
                        pix = QtGui.QPixmap()
                        pix.loadFromData(base64.b64decode(self.self_avatar))
                        # Tạo avatar tròn cho sidebar (56x56 để khớp với sidebar_avatar size mới)
                        size = 56
                        rounded = QtGui.QPixmap(size, size)
                        rounded.fill(QtCore.Qt.GlobalColor.transparent)
                        painter = QtGui.QPainter(rounded)
                        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                        path = QtGui.QPainterPath()
                        path.addEllipse(0, 0, size, size)
                        painter.setClipPath(path)
                        # Scale và center ảnh
                        scaled = pix.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation)
                        x = (scaled.width() - size) // 2
                        y = (scaled.height() - size) // 2
                        painter.drawPixmap(0, 0, scaled, x, y, size, size)
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
        d = ProfileDialog(self.controller, self.display_name, self.self_avatar, self)
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

    # =====================================================
    # TOAST NOTIFICATION HANDLERS
    # =====================================================
    @QtCore.Slot(int, str, str, str, str, object, object)
    def _show_toast_notification(self, sender_id, sender_name, sender_avatar, 
                                  content, msg_type, group_id, moderation):
        """Show toast notification for messages from other chats."""
        self.notification_manager.show_notification(
            sender_id, sender_name, sender_avatar,
            content, msg_type, group_id, moderation
        )
    
    @QtCore.Slot(int, str)
    def _on_notification_clicked(self, target_id, mode):
        """Handle click on toast notification - navigate to the chat."""
        # Get display name from appropriate cache
        if mode == "group":
            # Tìm tên nhóm từ danh sách groups đã cache
            display_name = "Unknown"
            for group in self.all_groups:
                if group.get("id") == target_id:
                    display_name = group.get("name", "Unknown")
                    break
        else:
            # Lấy tên user từ cache
            display_name = self.user_names.get(target_id, "Unknown")
        
        # Use existing method to select and load chat
        item_type = "group" if mode == "group" else "user"
        self.select_chat_by_id(target_id, display_name, item_type)
        
        # Bring window to front
        self.raise_()
        self.activateWindow()