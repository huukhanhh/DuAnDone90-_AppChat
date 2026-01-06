# server/controllers/face_auth_controller.py
"""
Controller xác thực FaceID - Xử lý đăng ký FaceID và FACE_LOGIN.
Hỗ trợ: FACE_STATUS, FACE_ENROLL, FACE_DISABLE, FACE_LOGIN

Controller này quản lý các bản ghi xác thực khuôn mặt cho người dùng đã đăng nhập
và cung cấp phương thức đăng nhập mới qua FaceID (FACE_LOGIN).
"""

import logging
import base64
import time

# Import các model DB
from server.models.user_face_auth_model import UserFaceAuthModel
from server.models.user_model import UserModel

# Import codec chuyển đổi embedding
from common.face.embedding_codec import b64_to_embedding, bytes_to_embedding, normalize_embedding

logger = logging.getLogger(__name__)


def cosine_similarity(a, b) -> float:
    """
    Tính độ tương đồng cosine giữa hai vector đã chuẩn hóa.
    Giả sử các vector đã được chuẩn hóa L2.
    
    Công thức: cos(a,b) = a · b (tích vô hướng)
    Giá trị: -1 (ngược hướng) đến 1 (cùng hướng)
    """
    return float(a.dot(b))


class FaceAuthController:
    """
    Controller phía server để quản lý đăng ký và đăng nhập FaceID.
    
    Các phương thức enrollment yêu cầu session đã xác thực.
    FACE_LOGIN là điểm vào đăng nhập mới (không cần xác thực trước).
    """
    
    # Hằng số giới hạn số lần thử
    MAX_FACE_LOGIN_ATTEMPTS = 5  # Số lần thất bại tối đa
    LOCK_DURATION_SECONDS = 30  # Thời gian khóa sau khi vượt quá
    
    def __init__(self):
        """Khởi tạo với UserFaceAuthModel và UserModel để truy cập DB."""
        self.model = UserFaceAuthModel()
        self.user_model = UserModel()
        
        # Rate limiting: socket -> {"count": int, "locked_until": float}
        # Theo dõi số lần thất bại của mỗi socket
        self.face_login_failures = {}
        
        logger.info("[FaceAuth] Controller đã khởi tạo")
    
    def _check_auth(self, user_id, result_type: str) -> dict | None:
        """
        Kiểm tra người dùng đã xác thực chưa.
        
        Returns:
            dict response lỗi nếu chưa xác thực, None nếu đã xác thực.
        """
        if user_id is None:
            return {
                "type": result_type,
                "ok": False,
                "reason": "UNAUTHORIZED"
            }
        return None
    
    def _check_rate_limit(self, client_socket) -> bool:
        """
        Kiểm tra client socket có bị rate-limit không.
        
        Returns:
            True nếu BỊ KHÓA (nên từ chối), False nếu OK để tiếp tục.
        """
        if client_socket not in self.face_login_failures:
            return False
        
        info = self.face_login_failures[client_socket]
        now = time.time()
        
        # Kiểm tra có đang bị khóa không
        if info.get("locked_until", 0) > now:
            return True  # Vẫn đang bị khóa
        
        # Khóa đã hết hạn, reset nếu cần
        if info.get("locked_until", 0) <= now and info.get("count", 0) >= self.MAX_FACE_LOGIN_ATTEMPTS:
            # Khóa đã hết hạn, reset bộ đếm
            self.face_login_failures[client_socket] = {"count": 0, "locked_until": 0}
        
        return False
    
    def _record_failure(self, client_socket):
        """Ghi nhận một lần FACE_LOGIN thất bại và khóa nếu vượt ngưỡng."""
        if client_socket not in self.face_login_failures:
            self.face_login_failures[client_socket] = {"count": 0, "locked_until": 0}
        
        info = self.face_login_failures[client_socket]
        info["count"] = info.get("count", 0) + 1
        
        if info["count"] >= self.MAX_FACE_LOGIN_ATTEMPTS:
            info["locked_until"] = time.time() + self.LOCK_DURATION_SECONDS
            logger.warning(f"[FaceAuth] Socket bị khóa {self.LOCK_DURATION_SECONDS}s sau {info['count']} lần thất bại")
    
    def _clear_failures(self, client_socket):
        """Xóa bộ đếm thất bại khi đăng nhập thành công."""
        if client_socket in self.face_login_failures:
            del self.face_login_failures[client_socket]
    
    def handle_face_login(self, client_socket, payload: dict, server_instance) -> dict:
        """
        Xử lý request FACE_LOGIN - Phương thức đăng nhập MỚI qua FaceID.
        Đây là điểm vào không cần xác thực trước.
        
        Request: {
            "action": "FACE_LOGIN",
            "email": "user@example.com",
            "embedding_b64": "...",
            "embedding_dim": 128|512
        }
        
        Response thành công: Cùng định dạng với password login thành công
        {
            "status": "success",
            "user_id": ...,
            "display_name": ...,
            "avatar": ...,
            "is_invisible": ...,
            "last_active_at": null
        }
        
        Response thất bại:
        {
            "status": "error",
            "action": "FACE_LOGIN_RESULT",
            "ok": false,
            "reason": "NOT_FOUND" | "NOT_ENABLED" | "NOT_MATCH" | "DIM_MISMATCH" | "LOCKED" | "BAD_REQUEST"
        }
        
        Các lý do thất bại:
        - NOT_FOUND: Email không tồn tại
        - NOT_ENABLED: Tài khoản chưa bật FaceID
        - NOT_MATCH: Khuôn mặt không khớp
        - DIM_MISMATCH: Kích thước embedding không khớp
        - LOCKED: Thử quá nhiều lần, tạm khóa
        - BAD_REQUEST: Thiếu dữ liệu hoặc dữ liệu không hợp lệ
        """
        def fail_response(reason: str) -> dict:
            return {
                "status": "error",
                "action": "FACE_LOGIN_RESULT",
                "ok": False,
                "reason": reason
            }
        
        # 1. Kiểm tra rate limit
        if self._check_rate_limit(client_socket):
            logger.debug(f"[FaceAuth] FACE_LOGIN bị từ chối - socket đang BỊ KHÓA")
            return fail_response("LOCKED")
        
        try:
            # 2. Validate các trường bắt buộc
            email = payload.get("email")
            embedding_b64 = payload.get("embedding_b64")
            embedding_dim = payload.get("embedding_dim")
            
            if not email or not embedding_b64 or embedding_dim is None:
                self._record_failure(client_socket)
                return fail_response("BAD_REQUEST")
            
            try:
                embedding_dim = int(embedding_dim)
            except (ValueError, TypeError):
                self._record_failure(client_socket)
                return fail_response("BAD_REQUEST")
            
            # 3. Tìm user theo email
            user_id = self.user_model.get_user_id(email)
            if user_id is None:
                logger.debug(f"[FaceAuth] FACE_LOGIN: email không tồn tại: {email}")
                self._record_failure(client_socket)
                return fail_response("NOT_FOUND")
            
            # 4. Lấy bản ghi face auth đang active
            face_record = self.model.get_active_face_auth_by_user_id(user_id)
            if face_record is None:
                logger.debug(f"[FaceAuth] FACE_LOGIN: không có bản ghi face active cho user_id={user_id}")
                self._record_failure(client_socket)
                return fail_response("NOT_ENABLED")
            
            if not face_record.get("is_enabled", False):
                logger.debug(f"[FaceAuth] FACE_LOGIN: face auth bị tắt cho user_id={user_id}")
                self._record_failure(client_socket)
                return fail_response("NOT_ENABLED")
            
            # 5. Kiểm tra dimension khớp
            stored_dim = face_record.get("embedding_dim")
            if embedding_dim != stored_dim:
                logger.debug(f"[FaceAuth] FACE_LOGIN: dim không khớp user_id={user_id}, "
                           f"request={embedding_dim}, lưu trữ={stored_dim}")
                self._record_failure(client_socket)
                return fail_response("DIM_MISMATCH")
            
            # 6. Giải mã embeddings
            try:
                vec_in = b64_to_embedding(embedding_b64, embedding_dim)
            except Exception as e:
                logger.warning(f"[FaceAuth] FACE_LOGIN: dữ liệu embedding không hợp lệ: {e}")
                self._record_failure(client_socket)
                return fail_response("BAD_REQUEST")
            
            try:
                vec_db = bytes_to_embedding(face_record["embedding"], stored_dim)
            except Exception as e:
                logger.error(f"[FaceAuth] FACE_LOGIN: lỗi giải mã embedding lưu trữ: {e}")
                self._record_failure(client_socket)
                return fail_response("BAD_REQUEST")
            
            # 7. Chuẩn hóa cả hai vector
            vec_in = normalize_embedding(vec_in)
            vec_db = normalize_embedding(vec_db)
            
            # 8. Tính độ tương đồng cosine
            similarity = cosine_similarity(vec_in, vec_db)
            threshold = float(face_record.get("threshold", 0.7))
            
            logger.debug(f"[FaceAuth] FACE_LOGIN user_id={user_id}: similarity={similarity:.4f}, threshold={threshold}")
            
            # 9. Kiểm tra khớp
            if similarity < threshold:
                logger.info(f"[FaceAuth] FACE_LOGIN: KHÔNG KHỚP cho user_id={user_id}, sim={similarity:.4f} < thresh={threshold}")
                self._record_failure(client_socket)
                return fail_response("NOT_MATCH")
            
            # === THÀNH CÔNG ===
            logger.info(f"[FaceAuth] FACE_LOGIN THÀNH CÔNG cho user_id={user_id}, email={email}")
            
            # 10. Cập nhật last_used_at
            self.model.touch_last_used(user_id)
            
            # 11. Xóa bộ đếm thất bại
            self._clear_failures(client_socket)
            
            # 12. Lấy thông tin profile cho response (giống password login)
            display_name = self.user_model.get_display_name(user_id)
            avatar = self.user_model.get_avatar(user_id)
            
            # Lấy is_invisible từ profile
            profile = self.user_model.get_profile(user_id)
            is_invisible = profile.get("is_invisible", False) if profile.get("status") == "success" else False
            
            # 13. Trả về response thành công CÙNG ĐỊNH DẠNG với password login
            return {
                "status": "success",
                "user_id": user_id,
                "display_name": display_name,
                "avatar": avatar,
                "is_invisible": is_invisible,
                "last_active_at": None  # Login nghĩa là đang active
            }
            
        except Exception as e:
            logger.error(f"[FaceAuth] FACE_LOGIN lỗi: {e}")
            self._record_failure(client_socket)
            return fail_response("BAD_REQUEST")
    
    def handle_face_status(self, user_id, payload: dict) -> dict:
        """
        Xử lý request FACE_STATUS.
        Trả về trạng thái đăng ký FaceID hiện tại cho user đã xác thực.
        
        Request: { "action": "FACE_STATUS" }
        Response: {
            "type": "FACE_STATUS_RESULT",
            "ok": true,
            "enabled": true|false,      # FaceID có đang bật không
            "has_face": true|false,     # Đã từng đăng ký FaceID chưa
            "model_name": string|null,  # Tên model đang dùng
            "updated_at": string|null   # Thời gian cập nhật cuối
        }
        """
        # Kiểm tra authentication
        auth_error = self._check_auth(user_id, "FACE_STATUS_RESULT")
        if auth_error:
            return auth_error
        
        try:
            record = self.model.get_face_auth_by_user_id(user_id)
            
            if record is None:
                # Chưa đăng ký FaceID
                return {
                    "type": "FACE_STATUS_RESULT",
                    "ok": True,
                    "enabled": False,
                    "has_face": False,
                    "model_name": None,
                    "updated_at": None
                }
            else:
                # FaceID đã tồn tại
                return {
                    "type": "FACE_STATUS_RESULT",
                    "ok": True,
                    "enabled": record.get("is_enabled", False),
                    "has_face": True,
                    "model_name": record.get("model_name"),
                    "updated_at": record.get("updated_at")
                }
        except Exception as e:
            logger.error(f"[FaceAuth] Lỗi lấy status cho user_id={user_id}: {e}")
            return {
                "type": "FACE_STATUS_RESULT",
                "ok": False,
                "reason": "SERVER_ERROR"
            }
    
    def handle_face_enroll(self, user_id, payload: dict) -> dict:
        """
        Xử lý request FACE_ENROLL.
        Đăng ký hoặc cập nhật FaceID cho user đã xác thực.
        
        Request: {
            "action": "FACE_ENROLL",
            "embedding_b64": "...",        # Embedding mã hóa base64
            "embedding_dim": 128|512,      # Số chiều embedding
            "model_name": "Facenet512",    # Tên model sử dụng
            "threshold": 0.70              # Ngưỡng similarity
        }
        Response thành công: { "type": "FACE_ENROLL_RESULT", "ok": true }
        Response thất bại: { "type": "FACE_ENROLL_RESULT", "ok": false, "reason": "..." }
        """
        # Kiểm tra authentication
        auth_error = self._check_auth(user_id, "FACE_ENROLL_RESULT")
        if auth_error:
            return auth_error
        
        try:
            # Validate các trường bắt buộc
            embedding_b64 = payload.get("embedding_b64")
            embedding_dim = payload.get("embedding_dim")
            model_name = payload.get("model_name")
            threshold = payload.get("threshold")
            
            # Validate sự có mặt
            if not embedding_b64 or embedding_dim is None or not model_name or threshold is None:
                return {
                    "type": "FACE_ENROLL_RESULT",
                    "ok": False,
                    "reason": "BAD_REQUEST"
                }
            
            # Validate kiểu dữ liệu
            try:
                embedding_dim = int(embedding_dim)
                threshold = float(threshold)
            except (ValueError, TypeError):
                return {
                    "type": "FACE_ENROLL_RESULT",
                    "ok": False,
                    "reason": "BAD_REQUEST"
                }
            
            if not isinstance(model_name, str) or len(model_name.strip()) == 0:
                return {
                    "type": "FACE_ENROLL_RESULT",
                    "ok": False,
                    "reason": "BAD_REQUEST"
                }
            
            # Giải mã base64 sang bytes
            try:
                embedding_bytes = base64.b64decode(embedding_b64)
            except Exception as e:
                logger.warning(f"[FaceAuth] Base64 không hợp lệ từ user_id={user_id}: {e}")
                return {
                    "type": "FACE_ENROLL_RESULT",
                    "ok": False,
                    "reason": "BAD_REQUEST"
                }
            
            # Validate độ dài byte khớp với dimension
            expected_len = embedding_dim * 4  # float32 = 4 bytes
            if len(embedding_bytes) != expected_len:
                logger.warning(f"[FaceAuth] Dimension không khớp cho user_id={user_id}: "
                             f"mong đợi {expected_len} bytes, nhận được {len(embedding_bytes)}")
                return {
                    "type": "FACE_ENROLL_RESULT",
                    "ok": False,
                    "reason": "BAD_REQUEST"
                }
            
            # Upsert vào database
            self.model.upsert_face_auth(
                user_id=user_id,
                embedding_bytes=embedding_bytes,
                embedding_dim=embedding_dim,
                model_name=model_name.strip(),
                threshold=threshold
            )
            
            logger.info(f"[FaceAuth] Đã enroll user_id={user_id} dim={embedding_dim} model={model_name}")
            
            return {
                "type": "FACE_ENROLL_RESULT",
                "ok": True
            }
            
        except Exception as e:
            logger.error(f"[FaceAuth] Lỗi khi enroll cho user_id={user_id}: {e}")
            return {
                "type": "FACE_ENROLL_RESULT",
                "ok": False,
                "reason": "SERVER_ERROR"
            }
    
    def handle_face_disable(self, user_id, payload: dict) -> dict:
        """
        Xử lý request FACE_DISABLE.
        Tắt FaceID cho user đã xác thực (idempotent - gọi nhiều lần không sao).
        
        Request: { "action": "FACE_DISABLE" }
        Response: { "type": "FACE_DISABLE_RESULT", "ok": true }
        """
        # Kiểm tra authentication
        auth_error = self._check_auth(user_id, "FACE_DISABLE_RESULT")
        if auth_error:
            return auth_error
        
        try:
            self.model.disable_face_auth(user_id)
            logger.info(f"[FaceAuth] Đã tắt FaceID cho user_id={user_id}")
            
            return {
                "type": "FACE_DISABLE_RESULT",
                "ok": True
            }
        except Exception as e:
            logger.error(f"[FaceAuth] Lỗi khi tắt FaceID cho user_id={user_id}: {e}")
            return {
                "type": "FACE_DISABLE_RESULT",
                "ok": False,
                "reason": "SERVER_ERROR"
            }
