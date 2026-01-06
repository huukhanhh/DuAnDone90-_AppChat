# server/controllers/moderation_controller.py
# Server-side moderation controller - sử dụng Decision Engine (AI + Rule-based)
#
# Chức năng: Kiểm tra tin nhắn đến từ client trước khi broadcast
# Đảm bảo client không thể bypass moderation
#
# Luồng xử lý:
# 1. AI classifier đánh giá: NOT / OFFENSIVE
# 2. Nếu OFFENSIVE → Rule-based tìm từ vi phạm
# 3. Quyết định:
#    - ALLOW: Broadcast bình thường
#    - WARN: Broadcast tin đã che từ xấu
#    - BLOCK: Không broadcast nội dung gốc

import os


class ServerModerationController:
    """
    Controller kiểm duyệt nội dung phía server.
    Sử dụng ModerationDecisionEngine (AI-first + Rule-based).
    
    Đảm bảo:
    - Client không thể bypass bằng cách gửi tin nhắn vi phạm trực tiếp
    - Tin nhắn được kiểm tra lại trước khi broadcast cho các client khác
    """
    
    def __init__(self, badwords_path: str = None):
        """
        Khởi tạo controller với đường dẫn file từ cấm.
        
        Args:
            badwords_path: Đường dẫn tới file badwords.txt
        """
        if badwords_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(base_dir))
            badwords_path = os.path.join(project_root, "common", "moderation", "badwords.txt")
        
        self.badwords_path = badwords_path
        
        # EAGER LOAD Decision Engine (AI model) ngay khi server khởi động
        # Để tránh lag tin nhắn đầu tiên
        self._engine = None
        self._initialized = False
        self._rule_engine_fallback = None
        
        # Load ngay lập tức
        self._load_engine()
    
    def _load_engine(self):
        """Load Decision Engine ngay khi khởi tạo (eager loading)."""
        try:
            from common.moderation.ai_classifier import ToxicAIClassifier
            from common.moderation.text_filter import TextModerationEngine
            from common.moderation.decision_engine import ModerationDecisionEngine
            
            print("[SERVER_MODERATION] Loading Decision Engine...")
            ai_engine = ToxicAIClassifier()
            rule_engine = TextModerationEngine(self.badwords_path)
            self._engine = ModerationDecisionEngine(ai_engine, rule_engine)
            self._initialized = True
            print("[SERVER_MODERATION] Decision Engine loaded successfully")
        except Exception as e:
            print(f"[SERVER_MODERATION] Lỗi khởi tạo Decision Engine: {e}")
            # Fallback: dùng rule-based only
            from common.moderation.text_filter import TextModerationEngine
            self._rule_engine_fallback = TextModerationEngine(self.badwords_path)
            self._initialized = True
    
    def _ensure_initialized(self):
        """Đảm bảo engine đã được khởi tạo (backward compatibility)."""
        if not self._initialized:
            self._load_engine()
    
    def check_incoming_text(self, msg: dict) -> dict:
        """
        Kiểm tra tin nhắn văn bản nhận được từ client.
        
        Đảm bảo client không thể bypass moderation.
        
        Args:
            msg: Request dict từ client, có field "message" chứa nội dung
            
        Returns:
            dict với format:
            {
                "action": "ALLOW" | "WARN" | "BLOCK",
                "final_text": str | None,  # Tin nhắn sau khi che (None nếu BLOCK)
                "hits": list,  # Từ vi phạm
                "score": float  # AI score
            }
        """
        self._ensure_initialized()
        
        text = msg.get("message", "")
        
        if not text or not text.strip():
            return {
                "action": "ALLOW",
                "final_text": text,
                "hits": [],
                "score": 0.0
            }
        
        try:
            if self._engine:
                # Dùng Decision Engine (AI + Rule-based)
                result = self._engine.moderate(text)
                return result
            else:
                # Fallback: chỉ dùng rule-based
                rule_result = self._rule_engine_fallback.check(text)
                hits = rule_result.get("hits", [])
                
                if hits:
                    censored = self._rule_engine_fallback.censor_text(text, hits)
                    return {
                        "action": "WARN",
                        "final_text": censored,
                        "hits": hits,
                        "score": 0.0
                    }
                else:
                    return {
                        "action": "ALLOW",
                        "final_text": text,
                        "hits": [],
                        "score": 0.0
                    }
        except Exception as e:
            print(f"[SERVER_MODERATION] Lỗi kiểm duyệt: {e}")
            # Fallback: cho phép nếu có lỗi
            return {
                "action": "ALLOW",
                "final_text": text,
                "hits": [],
                "score": 0.0
            }
    
    def check_incoming_image(self, msg: dict) -> dict:
        """
        Kiểm tra ảnh nhận được.
        
        STUB: Chưa có model NSFW detection, luôn ALLOW.
        TODO: Thêm model NSFW detection ở phiên bản sau.
        
        Args:
            msg: Request dict từ client, có field "image_data"
            
        Returns:
            dict với format chuẩn (luôn ALLOW)
        """
        return {
            "action": "ALLOW",
            "final_text": None,
            "hits": [],
            "score": 0.0
        }
