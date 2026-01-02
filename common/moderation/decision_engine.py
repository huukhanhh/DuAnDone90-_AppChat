# common/moderation/decision_engine.py
# Decision Engine cho hệ thống chat moderation
# Kiến trúc: AI-first + Rule-based hỗ trợ WARN
#
# Logic quyết định:
# 1. AI quyết định: NOT → ALLOW, OFFENSIVE → tiếp tục
# 2. Rule-based phân loại từ: NHẸ (insult) / CỰC NẶNG (curse)
# 3. Có từ CỰC NẶNG → BLOCK (không che, chặn hoàn toàn)
# 4. Chỉ có từ NHẸ → WARN (che từ vi phạm, giữ từ bình thường)

from typing import Optional


# ========== DANH SÁCH TỪ CỰC NẶNG (Profanity/Curse) ==========
# Các từ này sẽ dẫn đến BLOCK ngay lập tức
SEVERE_WORDS = {
    # Đit và biến thể
    "dit", "ditme", "ditmemay", "ditcon", "ditba", "ditcha",
    "djt", "d1t", "đit", "đitme",
    
    # Đu và biến thể
    "du", "duma", "ducon",
    
    # DM và biến thể
    "dm", "dmm", "dmmm", "dcm", "dcmm",
    
    # Lon và biến thể
    "lon", "loz", "lol", "cailon", "conlon",
    
    # CC và biến thể
    "cac", "cak", "concac", "caiconcac",
    
    # Boi và biến thể
    "buoi", "daubuoi",
    
    # Fuc* và biến thể
    "fuck", "fck", "fuk",
}


class ModerationDecisionEngine:
    """
    Decision Engine cho hệ thống chat moderation.
    
    Kiến trúc: AI-first + Rule-based hỗ trợ WARN
    
    Luồng xử lý:
    1. AI classifier quyết định: NOT (cho phép) / OFFENSIVE (vi phạm)
    2. Nếu OFFENSIVE → Rule-based tìm từ vi phạm
    3. Phân loại từ:
       - Có từ CỰC NẶNG → BLOCK (chặn hoàn toàn)
       - Chỉ có từ NHẸ → WARN (che từ vi phạm)
    
    Ưu điểm:
    - Tránh over-block các câu chỉ có từ nhẹ như "sao mày ngu thế"
    - BLOCK dành cho vi phạm nghiêm trọng (profanity)
    - WARN cho phép gửi tin nhắn sau khi che từ xấu
    """
    
    def __init__(self, ai_engine, rule_engine):
        """
        Khởi tạo Decision Engine.
        
        Args:
            ai_engine: ToxicAIClassifier instance
            rule_engine: TextModerationEngine instance (rule-based)
        """
        self.ai_engine = ai_engine
        self.rule_engine = rule_engine
    
    def moderate(self, text: str) -> dict:
        """
        Kiểm duyệt văn bản.
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            dict với format:
            {
                "action": "ALLOW" | "WARN" | "BLOCK",
                "final_text": str | None,  # None nếu BLOCK
                "label": "NOT" | "OFFENSIVE",
                "score": float,
                "hits": list[str]  # Danh sách từ vi phạm
            }
        """
        # Xử lý text rỗng
        if not text or not text.strip():
            return self._create_result("ALLOW", text, "NOT", 0.0, [])
        
        # ========== BƯỚC 1: AI CLASSIFIER (QUYẾT ĐỊNH CHÍNH) ==========
        ai_result = self.ai_engine.check(text)
        label = ai_result.get("label", "NOT")
        score = ai_result.get("score", 0.0)
        
        # Nếu AI cho rằng KHÔNG vi phạm → ALLOW ngay
        if label == "NOT":
            return self._create_result("ALLOW", text, label, score, [])
        
        # ========== BƯỚC 2: RULE-BASED TÌM TỪ VI PHẠM ==========
        rule_result = self.rule_engine.check(text)
        hits = rule_result.get("hits", [])
        
        # ========== BƯỚC 3: PHÂN LOẠI TỪ VI PHẠM ==========
        has_severe = self._has_severe_words(hits)
        
        # ========== BƯỚC 4: QUYẾT ĐỊNH CUỐI CÙNG ==========
        if has_severe:
            # Có từ CỰC NẶNG → BLOCK (chặn hoàn toàn, không che)
            return self._create_result("BLOCK", None, label, score, hits)
        
        elif hits:
            # Chỉ có từ NHẸ → WARN (che từ vi phạm, giữ từ bình thường)
            censored_text = self.rule_engine.censor_text(text, hits)
            return self._create_result("WARN", censored_text, label, score, hits)
        
        else:
            # AI nói OFFENSIVE nhưng rule-based không tìm được từ nào
            # → ALLOW (tin tưởng Rule-based hơn, tránh false positive)
            # Ví dụ: "hi", "chào" có thể bị AI đánh nhầm
            return self._create_result("ALLOW", text, label, score, [])
    
    def _has_severe_words(self, hits: list) -> bool:
        """
        Kiểm tra xem có từ CỰC NẶNG trong danh sách hits không.
        
        Args:
            hits: Danh sách từ vi phạm (đã normalize)
            
        Returns:
            True nếu có ít nhất 1 từ cực nặng
        """
        for hit in hits:
            # Kiểm tra trực tiếp
            if hit.lower() in SEVERE_WORDS:
                return True
            
            # Kiểm tra xem hit có CHỨA từ cực nặng không
            # (cho trường hợp ghép như "ditmemay")
            for severe in SEVERE_WORDS:
                if severe in hit.lower():
                    return True
        
        return False
    
    def _create_result(self, action: str, final_text: Optional[str], 
                       label: str, score: float, hits: list) -> dict:
        """Tạo result dict chuẩn."""
        return {
            "action": action,
            "final_text": final_text,
            "label": label,
            "score": round(score, 4),
            "hits": hits
        }


# ========== TEST BLOCK ==========
if __name__ == "__main__":
    import sys
    sys.path.insert(0, r'd:\Python_VsCode\Chat_Client-Server')
    
    from common.moderation.ai_classifier import ToxicAIClassifier
    from common.moderation.text_filter import TextModerationEngine
    
    print("=" * 100)
    print("ModerationDecisionEngine - Test Suite")
    print("Logic: AI-first + Rule-based phân loại từ nhẹ/nặng")
    print("=" * 100)
    
    # Khởi tạo engines
    ai_engine = ToxicAIClassifier()
    rule_engine = TextModerationEngine(r'd:\Python_VsCode\Chat_Client-Server\common\moderation\badwords.txt')
    
    # Khởi tạo Decision Engine
    moderation_engine = ModerationDecisionEngine(ai_engine, rule_engine)
    
    # Test cases bắt buộc
    test_cases = [
        # Định dạng: (input, expected_action, expected_output_contains)
        ("Xin chào bạn", "ALLOW", "Xin chào bạn"),
        ("Nói chuyện ngu quá", "WARN", "***"),
        ("Sao mày ngu thế", "WARN", "***"),
        ("Địt mẹ mày", "BLOCK", None),
        ("d i t m e", "BLOCK", None),
        ("dit me", "BLOCK", None),
        
        # Thêm test cases
        ("Mày là đồ ngu", "WARN", "***"),
        ("Đồ con chó", "WARN", "***"),
        ("Thằng khốn nạn", "WARN", None),  # AI phát hiện, rule-based không có
        ("Tôi yêu bạn", "ALLOW", "Tôi yêu bạn"),
    ]
    
    print("\n" + "-" * 100)
    print(f"{'Input':<30} {'Expected':<10} {'Actual':<10} {'Final Text':<30} {'Status'}")
    print("-" * 100)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        input_text, expected_action, expected_output = test
        
        result = moderation_engine.moderate(input_text)
        actual_action = result["action"]
        final_text = result["final_text"]
        hits = result["hits"]
        score = result["score"]
        
        # Kiểm tra kết quả
        action_match = actual_action == expected_action
        
        if action_match:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        # Hiển thị
        final_display = str(final_text)[:28] if final_text else "None"
        input_display = input_text[:28] if len(input_text) > 28 else input_text
        
        print(f"{input_display:<30} {expected_action:<10} {actual_action:<10} {final_display:<30} {status}")
        
        if hits:
            print(f"    -> Hits: {hits}, Score: {score:.4f}")
    
    print("-" * 100)
    print(f"\nKết quả: {passed}/{passed+failed} tests passed")
    
    if failed > 0:
        print("\n⚠️ Một số test FAIL có thể do:")
        print("  - AI có thể đánh giá khác với expected")
        print("  - Từ vi phạm chưa có trong badwords.txt")
    
    print("\n" + "=" * 100)
    print("GIẢI THÍCH LOGIC TRÁNH OVER-BLOCK:")
    print("=" * 100)
    print("""
1. AI là tầng quyết định CHÍNH:
   - NOT (không vi phạm) → ALLOW ngay, không gọi rule-based
   - OFFENSIVE (vi phạm) → gọi rule-based để tìm từ cụ thể

2. Rule-based phân loại từ theo MỨC ĐỘ:
   - Từ NHẸ (insult): ngu, dốt, chó... → WARN (che từ, cho gửi)
   - Từ CỰC NẶNG (profanity): địt, dm, lồn... → BLOCK (chặn hoàn toàn)

3. Tại sao tránh được over-block:
   - Câu "sao mày ngu thế" có từ "ngu" (từ NHẸ) → WARN thay vì BLOCK
   - Chỉ BLOCK khi có từ CỰC NẶNG như "địt mẹ"
   - Score AI KHÔNG được dùng để quyết định WARN/BLOCK
   - Mức độ từ vi phạm mới quyết định WARN/BLOCK
""")
    print("=" * 100)
