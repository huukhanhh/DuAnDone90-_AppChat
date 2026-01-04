# client/views/notification_toast.py
"""
Toast Notification System for Chat App
- NotificationToast: UI component with smooth animation
- NotificationManager: Manages stack of toasts (max 3, oldest auto-dismiss)
"""

from PySide6 import QtWidgets, QtCore, QtGui
import base64


class NotificationToast(QtWidgets.QWidget):
    """
    Toast notification widget with smooth slide animation.
    Shows sender name, message preview, and avatar.
    """
    clicked = QtCore.Signal(int, str)  # target_id, mode ("user" or "group")
    closed = QtCore.Signal(object)  # self reference for manager cleanup
    
    MAX_PREVIEW_LENGTH = 50
    TOAST_WIDTH = 340
    TOAST_HEIGHT = 85
    AUTO_DISMISS_MS = 7000  # 7 giây
    ANIMATION_DURATION = 400  # 400ms cho animation mượt
    
    def __init__(self, sender_id, sender_name, sender_avatar, message, msg_type, 
                 group_id=None, moderation=None, parent=None):
        super().__init__(parent)
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.group_id = group_id
        self.target_id = group_id if group_id else sender_id
        self.mode = "group" if group_id else "user"
        self._is_closing = False
        
        # Window flags: Tool window, stay on top, no focus steal
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | 
            QtCore.Qt.Tool |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        
        self.setFixedSize(self.TOAST_WIDTH, self.TOAST_HEIGHT)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
        # Process message based on type and moderation
        preview = self._format_preview(message, msg_type, moderation)
        
        self._setup_ui(sender_name, sender_avatar, preview)
        self._setup_animation()
        
        # Auto dismiss timer
        self.dismiss_timer = QtCore.QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.close_toast)
    
    def _format_preview(self, message, msg_type, moderation):
        """Format message preview based on type and moderation."""
        # Handle moderation
        if moderation:
            action = moderation.get("action", "ALLOW")
            if action == "BLOCK":
                return "🚫 Tin nhắn đã bị ẩn."
            elif action == "WARN":
                text = moderation.get("final_text", message)
                return f"⚠ {text}"
        
        # Handle different message types
        if msg_type == "image":
            return "📷 Đã gửi một ảnh"
        elif msg_type == "voice":
            return "🎤 Đã gửi tin nhắn thoại"
        elif msg_type == "video":
            return "🎬 Đã gửi video"
        elif msg_type == "file":
            return f"📎 Đã gửi file: {message[:25]}..." if len(str(message)) > 25 else f"📎 {message}"
        elif msg_type == "call_log":
            return "📞 Cuộc gọi"
        else:
            # Text message - truncate if needed
            text = str(message) if message else ""
            if len(text) > self.MAX_PREVIEW_LENGTH:
                return text[:self.MAX_PREVIEW_LENGTH] + "..."
            return text if text else "Tin nhắn mới"
    
    def _setup_ui(self, sender_name, sender_avatar, preview):
        """Setup the toast UI with clean styling."""
        # Main container - use solid background, no complex effects
        self.container = QtWidgets.QFrame(self)
        self.container.setGeometry(0, 0, self.TOAST_WIDTH, self.TOAST_HEIGHT)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #d0d0d0;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(self.container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        
        # Avatar
        avatar_label = QtWidgets.QLabel()
        avatar_label.setFixedSize(50, 50)
        avatar_label.setAlignment(QtCore.Qt.AlignCenter)
        
        if sender_avatar:
            try:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(base64.b64decode(sender_avatar))
                # Create circular avatar
                rounded = QtGui.QPixmap(50, 50)
                rounded.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addEllipse(0, 0, 50, 50)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pixmap.scaled(50, 50, 
                    QtCore.Qt.KeepAspectRatioByExpanding, 
                    QtCore.Qt.SmoothTransformation))
                painter.end()
                avatar_label.setPixmap(rounded)
            except:
                self._set_default_avatar(avatar_label)
        else:
            self._set_default_avatar(avatar_label)
        
        layout.addWidget(avatar_label)
        
        # Text content
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sender name (bold)
        name_label = QtWidgets.QLabel(sender_name or "Unknown")
        name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #1a1a1a;
            background: transparent;
        """)
        text_layout.addWidget(name_label)
        
        # Message preview
        preview_label = QtWidgets.QLabel(preview)
        preview_label.setStyleSheet("""
            font-size: 13px;
            color: #555555;
            background: transparent;
        """)
        preview_label.setWordWrap(True)
        preview_label.setMaximumHeight(40)
        text_layout.addWidget(preview_label)
        
        layout.addLayout(text_layout, 1)
        
        # Close button
        close_btn = QtWidgets.QPushButton("×")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 20px;
                font-weight: bold;
                color: #aaaaaa;
                border-radius: 13px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
                color: #333333;
            }
        """)
        close_btn.clicked.connect(self.close_toast)
        layout.addWidget(close_btn, 0, QtCore.Qt.AlignTop)
    
    def _set_default_avatar(self, label):
        """Set default avatar icon."""
        label.setText("💬")
        label.setStyleSheet("""
            font-size: 26px; 
            background-color: #667eea; 
            border-radius: 25px;
            color: white;
        """)
    
    def _setup_animation(self):
        """Setup smooth position animation."""
        self.pos_anim = QtCore.QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(self.ANIMATION_DURATION)
        self.pos_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
    
    def slide_in(self, start_pos, end_pos):
        """Slide toast in from right."""
        self.pos_anim.stop()
        self.pos_anim.setStartValue(start_pos)
        self.pos_anim.setEndValue(end_pos)
        
        self.move(start_pos)
        self.show()
        self.pos_anim.start()
        
        # Start auto-dismiss timer
        self.dismiss_timer.start(self.AUTO_DISMISS_MS)
    
    def move_to(self, new_pos):
        """Smoothly move to new position."""
        if not self._is_closing:
            self.pos_anim.stop()
            self.pos_anim.setStartValue(self.pos())
            self.pos_anim.setEndValue(new_pos)
            self.pos_anim.start()
    
    def close_toast(self):
        """Close the toast with slide-out animation."""
        if self._is_closing:
            return
        self._is_closing = True
        self.dismiss_timer.stop()
        
        # Slide out to right
        self.pos_anim.stop()
        self.pos_anim.setStartValue(self.pos())
        end_pos = QtCore.QPoint(self.pos().x() + self.TOAST_WIDTH + 50, self.pos().y())
        self.pos_anim.setEndValue(end_pos)
        self.pos_anim.finished.connect(self._on_close_finished)
        self.pos_anim.start()
    
    def _on_close_finished(self):
        """Called when close animation completes."""
        self.closed.emit(self)
        self.close()
        self.deleteLater()
    
    def mousePressEvent(self, event):
        """Handle click to navigate to chat."""
        if event.button() == QtCore.Qt.LeftButton and not self._is_closing:
            self.clicked.emit(self.target_id, self.mode)
            self.close_toast()


class NotificationManager(QtCore.QObject):
    """
    Manages a stack of toast notifications.
    - New toast appears at bottom
    - Pushes older toasts UP
    - Maximum 3 visible, oldest auto-removed
    """
    notification_clicked = QtCore.Signal(int, str)  # target_id, mode
    
    MAX_VISIBLE = 3
    TOAST_SPACING = 12
    MARGIN_RIGHT = 25
    MARGIN_BOTTOM = 25
    
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.toasts = []  # Active toast list (oldest first)
    
    def show_notification(self, sender_id, sender_name, sender_avatar, 
                         message, msg_type, group_id=None, moderation=None):
        """Show a new toast notification."""
        # Create toast
        toast = NotificationToast(
            sender_id, sender_name, sender_avatar,
            message, msg_type, group_id, moderation,
            parent=None  # No parent = independent window
        )
        
        # Connect signals
        toast.clicked.connect(self._on_toast_clicked)
        toast.closed.connect(self._on_toast_closed)
        
        # Add to list (new toast at end = bottom position)
        self.toasts.append(toast)
        
        # Remove oldest if exceeded max
        while len(self.toasts) > self.MAX_VISIBLE:
            oldest = self.toasts.pop(0)
            oldest.close_toast()
        
        # Calculate positions and show
        self._show_and_reposition_all()
    
    def _show_and_reposition_all(self):
        """Position all toasts (newest at bottom, oldest at top)."""
        parent_geo = self.parent_widget.geometry()
        
        for i, toast in enumerate(self.toasts):
            # Calculate position (index 0 = top, last index = bottom)
            position_from_bottom = len(self.toasts) - 1 - i
            y_offset = position_from_bottom * (NotificationToast.TOAST_HEIGHT + self.TOAST_SPACING)
            
            end_x = parent_geo.right() - NotificationToast.TOAST_WIDTH - self.MARGIN_RIGHT
            end_y = parent_geo.bottom() - NotificationToast.TOAST_HEIGHT - self.MARGIN_BOTTOM - y_offset
            end_pos = QtCore.QPoint(end_x, end_y)
            
            if not toast.isVisible():
                # New toast - slide in from right
                start_x = parent_geo.right() + 50
                start_pos = QtCore.QPoint(start_x, end_y)
                toast.slide_in(start_pos, end_pos)
            else:
                # Existing toast - move up smoothly
                toast.move_to(end_pos)
    
    def _on_toast_clicked(self, target_id, mode):
        """Forward click event to parent."""
        self.notification_clicked.emit(target_id, mode)
    
    def _on_toast_closed(self, toast):
        """Remove toast from list and reposition remaining."""
        if toast in self.toasts:
            self.toasts.remove(toast)
            # Reposition remaining toasts after a short delay
            QtCore.QTimer.singleShot(100, self._show_and_reposition_all)
