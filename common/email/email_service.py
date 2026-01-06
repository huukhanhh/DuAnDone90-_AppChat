# common/email/email_service.py
"""
Email service for sending OTP codes via SMTP.

Uses Gmail SMTP by default. For Gmail, you need to use an App Password:
https://myaccount.google.com/apppasswords
"""

import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


class OTPManager:
    """
    Quản lý OTP codes với thời hạn.
    
    Lưu trữ OTP trong memory với format:
    {user_id: (otp_code, expiry_time)}
    """
    
    def __init__(self, expiry_minutes: int = 5):
        self.expiry_minutes = expiry_minutes
        self._storage: Dict[int, Tuple[str, datetime]] = {}
    
    def generate_otp(self, user_id: int) -> str:
        """Tạo OTP 6 số và lưu vào storage."""
        otp_code = ''.join(random.choices(string.digits, k=6))
        expiry_time = datetime.now() + timedelta(minutes=self.expiry_minutes)
        self._storage[user_id] = (otp_code, expiry_time)
        logger.info(f"OTP generated for user {user_id}, expires at {expiry_time}")
        return otp_code
    
    def verify_otp(self, user_id: int, otp_code: str) -> Tuple[bool, str]:
        """
        Xác thực OTP.
        
        Returns:
            (success: bool, message: str)
        """
        if user_id not in self._storage:
            return False, "Không tìm thấy mã OTP. Vui lòng yêu cầu mã mới."
        
        stored_otp, expiry_time = self._storage[user_id]
        
        # Kiểm tra hết hạn
        if datetime.now() > expiry_time:
            del self._storage[user_id]
            return False, "Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới."
        
        # Kiểm tra khớp
        if otp_code != stored_otp:
            return False, "Mã OTP không đúng."
        
        # OTP hợp lệ - xóa khỏi storage
        del self._storage[user_id]
        return True, "OTP hợp lệ"
    
    def clear_otp(self, user_id: int):
        """Xóa OTP của user (nếu có)."""
        if user_id in self._storage:
            del self._storage[user_id]


class EmailService:
    """
    Service gửi email OTP qua SMTP.
    """
    
    def __init__(self, smtp_server: str, smtp_port: int, 
                 sender_email: str, sender_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
    
    def send_otp(self, to_email: str, otp_code: str, display_name: str = "") -> bool:
        """
        Gửi email chứa mã OTP.
        
        Args:
            to_email: Email người nhận
            otp_code: Mã OTP 6 số
            display_name: Tên người dùng (optional)
        
        Returns:
            True nếu gửi thành công, False nếu thất bại
        """
        try:
            # Tạo email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = '🔐 Mã xác thực đổi mật khẩu - AppChat'
            msg['From'] = f'AppChat <{self.sender_email}>'
            msg['To'] = to_email
            
            # Nội dung text
            text_content = f"""
Xin chào {display_name or 'bạn'},

Bạn đã yêu cầu đổi mật khẩu cho tài khoản AppChat.

Mã xác thực của bạn là: {otp_code}

Mã này có hiệu lực trong 5 phút.

Nếu bạn không yêu cầu đổi mật khẩu, vui lòng bỏ qua email này.

Trân trọng,
AppChat Team
            """
            
            # Nội dung HTML (đẹp hơn)
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #1a73e8; margin: 0;">🔐 Xác thực đổi mật khẩu</h1>
        </div>
        
        <p>Xin chào <strong>{display_name or 'bạn'}</strong>,</p>
        
        <p>Bạn đã yêu cầu đổi mật khẩu cho tài khoản AppChat.</p>
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 20px; border-radius: 10px; 
                    text-align: center; margin: 25px 0;">
            <p style="margin: 0 0 10px 0; font-size: 14px;">Mã xác thực của bạn:</p>
            <p style="font-size: 36px; font-weight: bold; letter-spacing: 8px; margin: 0;">
                {otp_code}
            </p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            ⏱️ Mã này có hiệu lực trong <strong>5 phút</strong>.
        </p>
        
        <p style="color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
            Nếu bạn không yêu cầu đổi mật khẩu, vui lòng bỏ qua email này.
        </p>
        
        <p style="color: #666;">Trân trọng,<br><strong>AppChat Team</strong></p>
    </div>
</body>
</html>
            """
            
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # Gửi email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, to_email, msg.as_string())
            
            logger.info(f"OTP email sent to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending OTP: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending OTP email: {e}")
            return False


# Singleton instances
_otp_manager: Optional[OTPManager] = None
_email_service: Optional[EmailService] = None


def get_otp_manager() -> OTPManager:
    """Get singleton OTPManager instance."""
    global _otp_manager
    if _otp_manager is None:
        _otp_manager = OTPManager(expiry_minutes=5)
    return _otp_manager


def get_email_service() -> Optional[EmailService]:
    """
    Get singleton EmailService instance.
    Returns None if not configured.
    """
    global _email_service
    if _email_service is None:
        try:
            from config.config import EMAIL_CONFIG
            _email_service = EmailService(
                smtp_server=EMAIL_CONFIG.get("smtp_server", "smtp.gmail.com"),
                smtp_port=EMAIL_CONFIG.get("smtp_port", 587),
                sender_email=EMAIL_CONFIG["sender_email"],
                sender_password=EMAIL_CONFIG["sender_password"]
            )
        except (ImportError, KeyError) as e:
            logger.warning(f"Email service not configured: {e}")
            return None
    return _email_service
