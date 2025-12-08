from PySide6 import QtWidgets, QtCore, QtGui
import base64

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
        self.btn_reject.setIcon(QtGui.QIcon()) # TODO: Add icon if available, else text
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
    hangup_signal = QtCore.Signal()

    def __init__(self, peer_name, avatar_base64=None, is_caller=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuộc gọi")
        self.setFixedSize(300, 450)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #2c3e50; color: white;")
        
        self.seconds = 0
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_timer)

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
        
        # Timer Label (Hidden initially if caller)
        self.timer_lbl = QtWidgets.QLabel("00:00")
        self.timer_lbl.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(self.timer_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        # Hangup Button
        self.btn_hangup = QtWidgets.QPushButton("📞")
        self.btn_hangup.setFixedSize(70, 70)
        self.btn_hangup.setStyleSheet("""
            QPushButton { background-color: #e74c3c; border-radius: 35px; font-size: 30px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        # Note: Rotating text via stylesheet isn't easy, using Icon is better, but emoji works for now. 
        # Actually rotate property in stylesheet doesn't work for standard widgets. 
        # I'll just use the Hangup Emoji or Icon.
        self.btn_hangup.setText("❌") 

        self.btn_hangup.clicked.connect(self.on_hangup)
        layout.addWidget(self.btn_hangup, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()

    def start_timer(self):
        self.status_lbl.setText("Đang gọi")
        self.timer.start(1000)

    def update_timer(self):
        self.seconds += 1
        mins, secs = divmod(self.seconds, 60)
        self.timer_lbl.setText(f"{mins:02d}:{secs:02d}")

    def on_hangup(self):
        self.timer.stop()
        self.hangup_signal.emit()
        self.accept() # Close dialog
