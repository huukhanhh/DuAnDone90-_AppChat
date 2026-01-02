# client/controllers/moderation_controller.py
# Client-side moderation controller - sử dụng Decision Engine (AI + Rule-based)
#
# Luồng xử lý:
# 1. AI classifier đánh giá: NOT / OFFENSIVE
# 2. Nếu OFFENSIVE → Rule-based tìm từ vi phạm
# 3. Quyết định:
#    - ALLOW: Gửi bình thường
#    - WARN: Gửi tin đã che từ xấu + hiện cảnh báo
#    - BLOCK: Không gửi + hiện thông báo chặn

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
        
        # Lazy load Decision Engine (AI model nặng)
        self._engine = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy load Decision Engine khi cần."""
        if not self._initialized:
            try:
                from common.moderation.ai_classifier import ToxicAIClassifier
                from common.moderation.text_filter import TextModerationEngine
                from common.moderation.decision_engine import ModerationDecisionEngine
                
                ai_engine = ToxicAIClassifier()
                rule_engine = TextModerationEngine(self.badwords_path)
                self._engine = ModerationDecisionEngine(ai_engine, rule_engine)
                self._initialized = True
            except Exception as e:
                print(f"[MODERATION] Lỗi khởi tạo Decision Engine: {e}")
                # Fallback: dùng rule-based only
                from common.moderation.text_filter import TextModerationEngine
                self._rule_engine_fallback = TextModerationEngine(self.badwords_path)
                self._initialized = True
    
    def check_outgoing_text(self, text: str) -> dict:
        """
        Kiểm tra tin nhắn văn bản trước khi gửi.
        
        Sử dụng Decision Engine với logic:
        - AI quyết định: NOT → ALLOW, OFFENSIVE → Rule-based
        - Rule-based phân loại: Từ nhẹ → WARN, Từ nặng → BLOCK
        
        Args:
            text: Nội dung tin nhắn
            
        Returns:
            dict với format:
            {
                "action": "ALLOW" | "WARN" | "BLOCK",
                "final_text": str | None,  # Tin nhắn sau khi che (None nếu BLOCK)
                "reason": str,  # Thông báo hiển thị cho user
                "hits": list,  # Từ vi phạm
                "score": float  # AI score
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
            if self._engine:
                # Dùng Decision Engine (AI + Rule-based)
                result = self._engine.moderate(text)
                
                # Thêm reason thân thiện cho user
                if result["action"] == "WARN":
                    result["reason"] = "Tin nhắn có ngôn từ không phù hợp. Vui lòng điều chỉnh hành vi."
                elif result["action"] == "BLOCK":
                    result["reason"] = "Tin nhắn đã bị chặn do vi phạm tiêu chuẩn cộng đồng."
                else:
                    result["reason"] = ""
                
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
        except Exception as e:
            print(f"[MODERATION] Lỗi kiểm duyệt: {e}")
            # Cho phép gửi nếu có lỗi (không block user)
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
