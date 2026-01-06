from PySide6 import QtWidgets, QtCore, QtGui
import base64
import threading
import pyaudio

class IncomingCallDialog(QtWidgets.QDialog):
    accept_signal = QtCore.Signal()
    reject_signal = QtCore.Signal()

    def __init__(self, caller_name, avatar_base64=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuộc gọi đến")
        self.setFixedSize(300, 400)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #2c3e50; color: white;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)

        # Avatar
        avatar_lbl = QtWidgets.QLabel()
        avatar_lbl.setFixedSize(120, 120)
        avatar_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        if avatar_base64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(avatar_base64))
                # Circular Avatar
                rounded = QtGui.QPixmap(120, 120)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 120, 120)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(120, 120, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                avatar_lbl.setPixmap(rounded)
            except:
                avatar_lbl.setText("👤")
                avatar_lbl.setStyleSheet("font-size: 60px; background-color: #ecf0f1; color: #7f8c8d; border-radius: 60px;")
        else:
            avatar_lbl.setText("👤")
            avatar_lbl.setStyleSheet("font-size: 60px; background-color: #ecf0f1; color: #7f8c8d; border-radius: 60px;")
        
        layout.addWidget(avatar_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Name
        name_lbl = QtWidgets.QLabel(caller_name)
        name_lbl.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(name_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        status_lbl = QtWidgets.QLabel("Đang gọi cho bạn...")
        status_lbl.setStyleSheet("font-size: 14px; color: #bdc3c7;")
        layout.addWidget(status_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(30)

        # Reject Button
        self.btn_reject = QtWidgets.QPushButton()
        self.btn_reject.setIcon(QtGui.QIcon())
        self.btn_reject.setText("❌")
        self.btn_reject.setFixedSize(60, 60)
        self.btn_reject.setStyleSheet("""
            QPushButton { background-color: #e74c3c; border-radius: 30px; font-size: 24px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_reject.clicked.connect(self.on_reject)
        btn_layout.addWidget(self.btn_reject)

        # Accept Button
        self.btn_accept = QtWidgets.QPushButton()
        self.btn_accept.setText("📞")
        self.btn_accept.setFixedSize(60, 60)
        self.btn_accept.setStyleSheet("""
            QPushButton { background-color: #2ecc71; border-radius: 30px; font-size: 24px; }
            QPushButton:hover { background-color: #27ae60; }
        """)
        self.btn_accept.clicked.connect(self.on_accept)
        btn_layout.addWidget(self.btn_accept)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def on_accept(self):
        self.accept_signal.emit()
        self.accept()

    def on_reject(self):
        self.reject_signal.emit()
        self.reject()


class ActiveCallDialog(QtWidgets.QDialog):
    """Dialog cuộc gọi đang diễn ra với tính năng audio streaming."""
    
    hangup_signal = QtCore.Signal()
    audio_data_signal = QtCore.Signal(bytes)  # Signal để gửi audio data ra ngoài

    # Audio parameters
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000  # 16kHz phù hợp cho voice

    def __init__(self, peer_name, avatar_base64=None, is_caller=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuộc gọi")
        self.setFixedSize(300, 450)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #2c3e50; color: white;")
        
        self.seconds = 0
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        
        # Audio components
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        self.audio_running = False
        self.audio_thread = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)

        # Avatar
        avatar_lbl = QtWidgets.QLabel()
        avatar_lbl.setFixedSize(100, 100)
        avatar_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if avatar_base64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(avatar_base64))
                rounded = QtGui.QPixmap(100, 100)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 100, 100)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pix.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation))
                painter.end()
                avatar_lbl.setPixmap(rounded)
            except:
                avatar_lbl.setText("👤")
                avatar_lbl.setStyleSheet("font-size: 50px; background-color: #ecf0f1; color: #7f8c8d; border-radius: 50px;")
        else:
            avatar_lbl.setText("👤")
            avatar_lbl.setStyleSheet("font-size: 50px; background-color: #ecf0f1; color: #7f8c8d; border-radius: 50px;")
        layout.addWidget(avatar_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Name
        name_lbl = QtWidgets.QLabel(peer_name)
        name_lbl.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(name_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Status / Timer
        self.status_lbl = QtWidgets.QLabel("Đang kết nối..." if is_caller else "Đã kết nối")
        self.status_lbl.setStyleSheet("font-size: 16px; color: #bdc3c7;")
        layout.addWidget(self.status_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Timer Label
        self.timer_lbl = QtWidgets.QLabel("00:00")
        self.timer_lbl.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(self.timer_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        # Hangup Button
        self.btn_hangup = QtWidgets.QPushButton("❌")
        self.btn_hangup.setFixedSize(70, 70)
        self.btn_hangup.setStyleSheet("""
            QPushButton { background-color: #e74c3c; border-radius: 35px; font-size: 30px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_hangup.clicked.connect(self.on_hangup)
        layout.addWidget(self.btn_hangup, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()

    def start_timer(self):
        """Bắt đầu timer và audio streaming khi cuộc gọi được kết nối."""
        self.status_lbl.setText("Đang gọi")
        self.timer.start(1000)
        # Bắt đầu audio streaming
        self.start_audio_stream()

    def update_timer(self):
        self.seconds += 1
        mins, secs = divmod(self.seconds, 60)
        self.timer_lbl.setText(f"{mins:02d}:{secs:02d}")

    def start_audio_stream(self):
        """Bắt đầu capture và playback audio."""
        if self.audio_running:
            return
            
        try:
            self.audio = pyaudio.PyAudio()
            
            # Input stream (microphone) - capture audio
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Output stream (speaker) - playback audio
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            self.audio_running = True
            
            # Bắt đầu thread để capture audio
            self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
            self.audio_thread.start()
            
            print("[AudioCall] Audio streaming started")
            
        except Exception as e:
            print(f"[AudioCall] Error starting audio stream: {e}")
            self.audio_running = False

    def _audio_capture_loop(self):
        """Thread loop để capture audio từ microphone và emit signal."""
        while self.audio_running:
            try:
                if self.input_stream and self.input_stream.is_active():
                    # Đọc audio data từ microphone
                    data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                    if data and self.audio_running:
                        # Emit signal với audio data để gửi cho người nhận
                        self.audio_data_signal.emit(data)
            except Exception as e:
                if self.audio_running:
                    print(f"[AudioCall] Audio capture error: {e}")
                break

    def play_audio_data(self, data: bytes):
        """Phát audio data nhận được từ người gọi.
        
        Args:
            data: Raw audio bytes (PCM 16-bit mono 16kHz)
        """
        try:
            if self.output_stream and self.output_stream.is_active() and self.audio_running:
                self.output_stream.write(data)
        except Exception as e:
            print(f"[AudioCall] Audio playback error: {e}")

    def stop_audio_stream(self):
        """Dừng audio streaming và cleanup resources."""
        self.audio_running = False
        
        # Đợi thread kết thúc
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1.0)
        
        # Đóng input stream
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
            self.input_stream = None
        
        # Đóng output stream
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None
        
        # Terminate PyAudio
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
            self.audio = None
        
        print("[AudioCall] Audio streaming stopped")

    def on_hangup(self):
        """Dập máy - dừng audio và đóng dialog."""
        self.timer.stop()
        self.stop_audio_stream()
        self.hangup_signal.emit()
        self.accept()

    def closeEvent(self, event):
        """Cleanup khi dialog bị đóng."""
        self.timer.stop()
        self.stop_audio_stream()
        super().closeEvent(event)
