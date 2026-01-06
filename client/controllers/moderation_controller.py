# client/controllers/moderation_controller.py
# Client-side moderation controller - CHỈ DÙNG RULE-BASED (nhẹ)
#
# Kiến trúc (01/2026):
# - Client: Chỉ rule-based (nhanh, nhẹ, không load AI model)
# - Server: AI + Rule-based (đầy đủ, chính xác)
#
# Luồng xử lý client:
# 1. Rule-based tìm từ vi phạm trong badwords.txt
# 2. Quyết định:
#    - ALLOW: Gửi bình thường
#    - WARN: Gửi tin đã che từ xấu + hiện cảnh báo
# (BLOCK chỉ xảy ra ở server-side với AI model)

import os


class ClientModerationController:
    """
    Controller kiểm duyệt nội dung phía client.
    Sử dụng ModerationDecisionEngine (AI-first + Rule-based).
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
        
        # Client chỉ dùng Rule-based moderation (nhẹ)
        # AI moderation đã có ở Server side rồi
        self._engine = None
        self._rule_engine = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Load Rule-based engine (nhẹ, không cần AI model)."""
        if not self._initialized:
            try:
                from common.moderation.text_filter import TextModerationEngine
                self._rule_engine = TextModerationEngine(self.badwords_path)
                self._initialized = True
                print("[CLIENT_MODERATION] Rule-based engine loaded (lightweight)")
            except Exception as e:
                print(f"[CLIENT_MODERATION] Lỗi khởi tạo engine: {e}")
                self._initialized = True
    
    def check_outgoing_text(self, text: str) -> dict:
        """
        Kiểm tra tin nhắn văn bản trước khi gửi.
        
        Client chỉ dùng Rule-based (nhẹ).
        AI moderation được Server xử lý.
        
        Args:
            text: Nội dung tin nhắn
            
        Returns:
            dict với format:
            {
                "action": "ALLOW" | "WARN",
                "final_text": str,  # Tin nhắn sau khi che
                "reason": str,  # Thông báo hiển thị cho user
                "hits": list,  # Từ vi phạm
                "score": float  # Luôn là 0.0 (không dùng AI)
            }
        """
        self._ensure_initialized()
        
        if not text or not text.strip():
            return {
                "action": "ALLOW",
                "final_text": text,
                "reason": "",
                "hits": [],
                "score": 0.0
            }
        
        try:
            if self._rule_engine:
                rule_result = self._rule_engine.check(text)
                hits = rule_result.get("hits", [])
                
                if hits:
                    censored = self._rule_engine.censor_text(text, hits)
                    return {
                        "action": "WARN",
                        "final_text": censored,
                        "reason": "Tin nhắn có từ ngữ không phù hợp.",
                        "hits": hits,
                        "score": 0.0
                    }
                else:
                    return {
                        "action": "ALLOW",
                        "final_text": text,
                        "reason": "",
                        "hits": [],
                        "score": 0.0
                    }
            else:
                # Engine chưa khởi tạo được, cho phép gửi
                return {
                    "action": "ALLOW",
                    "final_text": text,
                    "reason": "",
                    "hits": [],
                    "score": 0.0
                }
        except Exception as e:
            print(f"[CLIENT_MODERATION] Lỗi kiểm duyệt: {e}")
            return {
                "action": "ALLOW",
                "final_text": text,
                "reason": "",
                "hits": [],
                "score": 0.0
            }
    
    def check_outgoing_image(self, image_payload) -> dict:
        """
        Kiểm tra ảnh trước khi gửi.
        
        STUB: Chưa có model NSFW detection, luôn ALLOW.
        TODO: Thêm model NSFW detection ở phiên bản sau.
        
        Args:
            image_payload: Dữ liệu ảnh (bytes hoặc base64 string)
            
        Returns:
            dict với format chuẩn (luôn ALLOW)
        """
        return {
            "action": "ALLOW",
            "final_text": None,
            "reason": "",
            "hits": [],
            "score": 0.0
        }
