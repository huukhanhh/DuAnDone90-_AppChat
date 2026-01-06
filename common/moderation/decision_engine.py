# common/moderation/decision_engine.py
# Multi-Layer Smart Detection Engine v2.1
# Phiên bản: 2.1 (01/2026) - Fix Over-Censoring
#
# Kiến trúc: Hybrid Waterfall với Early Return
# 
# THAY ĐỔI QUAN TRỌNG (v2.1):
# - Đảo thứ tự Layer: Context Check chạy TRƯỚC Pattern Check
# - Thêm Mitigation Logic: Không tha bổng nếu có INSULT_PREFIX
#
# Luồng mới:
# Layer 1: Severe Words Detection -> BLOCK
# Layer 2: Positive Context Detection -> ALLOW (NEW POSITION)
# Layer 3: Insult Pattern Detection -> WARN
# Layer 4: AI Fallback -> WARN/ALLOW

from typing import Optional, Set, List, Dict, Any
from functools import lru_cache
import re


# ============================================================================
# LAYER 1: SEVERE WORDS (Block ngay lập tức)
# ============================================================================
SEVERE_WORDS: Set[str] = {
    # Đit và biến thể
    "dit", "ditme", "ditmemay", "ditcon", "ditba", "ditcha",
    "djt", "d1t",
    
    # DM và biến thể
    "dm", "dmm", "dmmm", "dcm", "dcmm",
    
    # Lon và biến thể
    "lon", "loz", "cailon", "conlon",
    
    # Cac và biến thể
    "cac", "cak", "cc", "concac", "caiconcac",
    
    # Buoi
    "buoi", "daubuoi",
    
    # VCL, VL
    "vcl", "vl",
    
    # English profanity
    "fuck", "fck", "fuk",
}


# ============================================================================
# LAYER 2 (Old) / LAYER 3 (New): INSULT PATTERN DETECTION
# ============================================================================
INSULT_PREFIXES: List[str] = ["thằng", "đồ", "con", "lũ", "bọn", "tụi", "cái"]

# Normalized versions (không dấu) - dùng cho matching
INSULT_PREFIXES_NORMALIZED: Set[str] = {"thang", "do", "con", "lu", "bon", "tui", "cai"}


# ============================================================================
# LAYER 3 (Old) / LAYER 2 (New): POSITIVE CONTEXT DETECTION
# ============================================================================
# Từ động vật (normalized)
ANIMAL_WORDS: Set[str] = {"cho", "meo", "heo", "lon", "ga", "khi", "bo", "chuot", "trau", "tho", "vit"}

# Mở rộng ngữ cảnh tích cực (normalized)
POSITIVE_CONTEXTS: List[str] = [
    # Tính từ mô tả tích cực
    "de thuong", "dang yeu", "cute", "xinh", "dep", "ngoan", "gioi", 
    "thong minh", "khon", "lanh",
    
    # Động từ chăm sóc
    "nuoi", "cham", "yeu", "thich", "cung", "om", "be",
    
    # Chỉ định từ (demonstratives) - cho phép "con chó này"
    "nay", "kia", "do", "ay",
    
    # Sở hữu
    "nha", "cua", "cua toi", "cua em", "nha toi",
    
    # Mô tả ngoại hình động vật
    "beo", "gay", "tot", "khoe", "den", "trang", "vang", "nau", "xam",
    
    # Từ khác
    "toi nghiep", "dang thuong", "thu cung"
]


# ============================================================================
# VIETNAMESE NORMALIZATION
# ============================================================================
VIETNAMESE_DIACRITICS = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'đ': 'd',
}


def _normalize_text(text: str) -> str:
    """Chuẩn hóa văn bản: lowercase, bỏ dấu tiếng Việt."""
    if not text:
        return ""
    
    result = text.lower()
    for vn_char, ascii_char in VIETNAMESE_DIACRITICS.items():
        result = result.replace(vn_char, ascii_char)
    
    return result


def _normalize_text_keep_words(text: str) -> List[str]:
    """Chuẩn hóa và tách thành danh sách từ."""
    normalized = _normalize_text(text)
    # Loại bỏ ký tự đặc biệt, giữ lại chữ và số
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    return cleaned.split()


# ============================================================================
# MAIN CLASS: ModerationDecisionEngine v2.1
# ============================================================================
class ModerationDecisionEngine:
    """
    Multi-Layer Smart Detection Engine v2.1
    
    ===== HYBRID WATERFALL với Early Return =====
    
    Thứ tự xử lý MỚI (v2.1 - Fix Over-Censoring):
    
    1. Layer 1 - SEVERE:   Severe Words Detection    -> BLOCK
    2. Layer 2 - CONTEXT:  Positive Context Detection -> ALLOW  ⬆️ (Moved UP)
    3. Layer 3 - PATTERN:  Insult Pattern Detection   -> WARN   ⬇️ (Moved DOWN)
    4. Layer 4 - AI:       AI Fallback               -> WARN/ALLOW
    
    Thay đổi quan trọng:
    - Context Check chạy TRƯỚC Pattern Check để bảo vệ câu vô hại
    - Mitigation: Không tha bổng nếu câu chứa INSULT_PREFIX
      (Ví dụ: "Thằng chó ngoan" vẫn bị chặn dù có từ "ngoan")
    """
    
    # Threshold cho AI
    AI_CONFIDENCE_THRESHOLD: float = 0.85
    
    def __init__(self, ai_engine: Any, rule_engine: Any) -> None:
        """
        Khởi tạo Decision Engine v2.1.
        
        Args:
            ai_engine: ToxicAIClassifier instance
            rule_engine: TextModerationEngine instance
        """
        self.ai_engine = ai_engine
        self.rule_engine = rule_engine
        
        # Build badwords set từ rule_engine để check pattern
        self._badwords_set: Set[str] = self._build_badwords_set()
        
        print("[DECISION_ENGINE] v2.1 - Hybrid Waterfall initialized")
        print(f"[DECISION_ENGINE] Layer Order: SEVERE -> CONTEXT -> PATTERN -> AI")
    
    def _build_badwords_set(self) -> Set[str]:
        """Xây dựng set các từ cấm từ rule_engine."""
        badwords = set()
        if hasattr(self.rule_engine, 'short_words'):
            badwords.update(self.rule_engine.short_words)
        if hasattr(self.rule_engine, 'long_words'):
            badwords.update(self.rule_engine.long_words)
        return badwords
    
    # ========================================================================
    # MAIN METHOD: moderate()
    # ========================================================================
    def moderate(self, text: str) -> Dict[str, Any]:
        """
        Kiểm duyệt văn bản với kiến trúc Hybrid Waterfall v2.1.
        
        Luồng xử lý MỚI:
        1. SEVERE    -> BLOCK (chặn từ tục ngay)
        2. CONTEXT   -> ALLOW (bảo vệ ngữ cảnh tích cực - CHẠY TRƯỚC)
        3. PATTERN   -> WARN  (phát hiện insult pattern)
        4. AI        -> WARN/ALLOW (fallback)
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            dict: {
                "action": "ALLOW" | "WARN" | "BLOCK",
                "final_text": str | None,
                "label": str,
                "score": float,
                "hits": List[str],
                "layer": str
            }
        """
        # Empty text -> ALLOW
        if not text or not text.strip():
            return self._create_result("ALLOW", text, "NOT", 0.0, [], "EMPTY")
        
        # Bước 0: Lấy hits từ rule_engine (dùng cho nhiều layer)
        rule_result = self.rule_engine.check(text)
        hits: List[str] = rule_result.get("hits", [])
        
        # ================================================================
        # LAYER 1: SEVERE WORDS DETECTION (Unchanged position)
        # ================================================================
        if self._check_severe_words(hits):
            return self._create_result(
                action="BLOCK",
                final_text=None,
                label="OFFENSIVE",
                score=1.0,
                hits=hits,
                layer="L1_SEVERE"
            )
        
        # ================================================================
        # LAYER 2: POSITIVE CONTEXT DETECTION (⬆️ MOVED UP from Layer 3)
        # 
        # Lý do: Bảo vệ ngữ cảnh tích cực TRƯỚC KHI check pattern
        # Ví dụ: "Con chó dễ thương" -> ALLOW ngay ở đây
        # ================================================================
        if self._check_positive_context(text):
            return self._create_result(
                action="ALLOW",
                final_text=text,
                label="NOT",
                score=0.0,
                hits=[],
                layer="L2_POSITIVE_CONTEXT"
            )
        
        # ================================================================
        # LAYER 3: INSULT PATTERN DETECTION (⬇️ MOVED DOWN from Layer 2)
        # ================================================================
        if self._check_insult_patterns(text, hits):
            censored = self.rule_engine.censor_text(text, hits) if hits else text
            return self._create_result(
                action="WARN",
                final_text=censored,
                label="OFFENSIVE",
                score=0.9,
                hits=hits,
                layer="L3_PATTERN"
            )
        
        # ================================================================
        # LAYER 4: AI FALLBACK
        # ================================================================
        return self._layer4_ai_check(text, hits)
    
    # ========================================================================
    # LAYER 1: SEVERE WORDS CHECK
    # ========================================================================
    def _check_severe_words(self, hits: List[str]) -> bool:
        """
        Layer 1: Kiểm tra từ ngữ tục tĩu hạng nặng.
        
        Logic: Nếu hits chứa bất kỳ từ nào trong SEVERE_WORDS -> True
        
        Args:
            hits: Danh sách từ vi phạm từ rule_engine
            
        Returns:
            True nếu phát hiện severe word, False nếu không
        """
        for hit in hits:
            hit_lower = hit.lower()
            
            # Exact match
            if hit_lower in SEVERE_WORDS:
                return True
            
            # Substring match (cho compound words như "ditmemay")
            for severe in SEVERE_WORDS:
                if severe in hit_lower:
                    return True
        
        return False
    
    # ========================================================================
    # LAYER 2 (NEW): POSITIVE CONTEXT CHECK với MITIGATION
    # ========================================================================
    def _check_positive_context(self, text: str) -> bool:
        """
        Layer 2 (v2.1): Bảo vệ ngữ cảnh tích cực VỚI MITIGATION.
        
        Logic: Return True (Allow) KHI VÀ CHỈ KHI:
        1. Có từ trong ANIMAL_WORDS
        2. AND có từ trong POSITIVE_CONTEXTS  
        3. AND **KHÔNG** chứa từ trong INSULT_PREFIXES (Mitigation)
        
        Mitigation giúp tránh lỗ hổng như:
        - "Thằng chó ngoan" -> Có "ngoan" nhưng có "thằng" -> Không được tha
        - "Con chó ngoan"   -> Có "ngoan", không có insult prefix -> Được tha
        
        Args:
            text: Văn bản gốc
            
        Returns:
            True nếu là ngữ cảnh tích cực an toàn, False nếu không
        """
        normalized = _normalize_text(text)
        words = _normalize_text_keep_words(text)
        
        # Check 1: Có animal word không?
        has_animal = any(animal in normalized for animal in ANIMAL_WORDS)
        if not has_animal:
            return False
        
        # Check 2: Có positive context không?
        has_positive = any(positive in normalized for positive in POSITIVE_CONTEXTS)
        if not has_positive:
            return False
        
        # Check 3 (MITIGATION): Có insult prefix không?
        # Nếu có -> KHÔNG được tha bổng (return False)
        has_insult_prefix = any(word in INSULT_PREFIXES_NORMALIZED for word in words)
        
        # Đặc biệt: Kiểm tra "con" - chỉ là insult nếu đi với badword
        # "Con chó" vs "Con điên" -> cần logic tinh tế hơn
        # Giải pháp: Cho phép "con" nếu theo sau là animal word
        if has_insult_prefix:
            # Kiểm tra xem prefix có phải là "con" đi với động vật không
            for i, word in enumerate(words):
                if word == "con" and i + 1 < len(words):
                    next_word = words[i + 1]
                    if next_word in ANIMAL_WORDS:
                        # "con chó", "con mèo" -> OK, bỏ qua insult check cho "con"
                        continue
                    else:
                        # "con điên", "con đĩ" -> Không tha
                        return False
                elif word in INSULT_PREFIXES_NORMALIZED and word != "con":
                    # "thằng", "đồ", "lũ" -> Không tha
                    return False
        
        # Tất cả conditions passed -> Cho phép
        return True
    
    # ========================================================================
    # LAYER 3 (NEW POSITION): INSULT PATTERN CHECK  
    # ========================================================================
    def _check_insult_patterns(self, text: str, hits: List[str]) -> bool:
        """
        Layer 3 (v2.1): Phát hiện cấu trúc xúc phạm: [Prefix] + [Badword]
        
        Ví dụ:
        - "Thằng ngu" -> "thằng" (prefix) + "ngu" (badword) -> True
        - "Thằng Khánh" -> "thằng" (prefix) + "khánh" (not badword) -> False
        
        Args:
            text: Văn bản gốc
            hits: Danh sách từ vi phạm
            
        Returns:
            True nếu phát hiện insult pattern, False nếu không
        """
        words = _normalize_text_keep_words(text)
        
        for i, word in enumerate(words):
            # Kiểm tra word có phải là insult prefix không
            if word in INSULT_PREFIXES_NORMALIZED:
                # Lấy từ tiếp theo
                if i + 1 < len(words):
                    next_word = words[i + 1]
                    
                    # Kiểm tra từ tiếp theo có trong badwords không
                    if next_word in self._badwords_set:
                        return True
        
        return False
    
    # ========================================================================
    # LAYER 4: AI FALLBACK
    # ========================================================================
    def _layer4_ai_check(self, text: str, hits: List[str]) -> Dict[str, Any]:
        """
        Layer 4: Dùng AI để xử lý các trường hợp còn lại.
        
        Logic:
        - AI label = "NOT" -> ALLOW (Tin tưởng AI)
        - AI label = "OFFENSIVE":
            + score >= 0.85 VÀ có hits -> WARN
            + Ngược lại -> ALLOW (Safety Net)
        
        Args:
            text: Văn bản gốc
            hits: Danh sách từ vi phạm
            
        Returns:
            Result dict (luôn return, không pass)
        """
        # Gọi AI với cache
        ai_result = self._cached_ai_check(text)
        
        label = ai_result.get("label", "NOT")
        score = ai_result.get("score", 0.0)
        
        # Case 1: AI nói không vi phạm -> ALLOW
        if label == "NOT":
            return self._create_result(
                action="ALLOW",
                final_text=text,
                label=label,
                score=score,
                hits=[],
                layer="L4_AI_NOT"
            )
        
        # Case 2: AI nói OFFENSIVE
        # Chỉ WARN khi: score >= threshold VÀ có hits
        if score >= self.AI_CONFIDENCE_THRESHOLD and hits:
            censored = self.rule_engine.censor_text(text, hits)
            return self._create_result(
                action="WARN",
                final_text=censored,
                label=label,
                score=score,
                hits=hits,
                layer="L4_AI_OFFENSIVE"
            )
        
        # Case 3: Safety Net - Score thấp hoặc không có hits -> ALLOW
        return self._create_result(
            action="ALLOW",
            final_text=text,
            label=label,
            score=score,
            hits=hits,
            layer="L4_AI_SAFETY_NET"
        )
    
    @lru_cache(maxsize=1000)
    def _cached_ai_check(self, text: str) -> Dict[str, Any]:
        """
        Gọi AI classifier với LRU cache để tối ưu hiệu năng.
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            AI result dict với keys: label, score, action
        """
        return self.ai_engine.check(text)
    
    def _create_result(
        self,
        action: str,
        final_text: Optional[str],
        label: str,
        score: float,
        hits: List[str],
        layer: str
    ) -> Dict[str, Any]:
        """
        Tạo result dict chuẩn.
        
        Args:
            action: ALLOW | WARN | BLOCK
            final_text: Văn bản sau xử lý (None nếu BLOCK)
            label: NOT | OFFENSIVE
            score: AI confidence score
            hits: Danh sách từ vi phạm
            layer: Layer nào đã quyết định
            
        Returns:
            Result dict
        """
        return {
            "action": action,
            "final_text": final_text,
            "label": label,
            "score": round(score, 4),
            "hits": hits,
            "layer": layer
        }
    
    def clear_cache(self) -> None:
        """Xóa cache AI để reload."""
        self._cached_ai_check.cache_clear()
        print("[DECISION_ENGINE] AI cache cleared")


# ============================================================================
# TEST BLOCK
# ============================================================================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, r'd:\Python_VsCode\Chat_Client-Server')
    
    from common.moderation.ai_classifier import ToxicAIClassifier
    from common.moderation.text_filter import TextModerationEngine
    
    print("=" * 100)
    print("ModerationDecisionEngine v2.1 - Hybrid Waterfall Test")
    print("Layer Order: L1_SEVERE -> L2_CONTEXT -> L3_PATTERN -> L4_AI")
    print("=" * 100)
    
    # Khởi tạo engines
    print("\n[INIT] Loading AI model...")
    ai_engine = ToxicAIClassifier()
    rule_engine = TextModerationEngine(r'd:\Python_VsCode\Chat_Client-Server\common\moderation\badwords.txt')
    
    # Khởi tạo Decision Engine
    engine = ModerationDecisionEngine(ai_engine, rule_engine)
    
    # Test cases - ĐẶC BIỆT CHÚ Ý các case về động vật
    test_cases = [
        # === POSITIVE CONTEXT (Should ALLOW) ===
        ("Con chó này dễ thương quá", "ALLOW", "L2: Positive context - animal + cute"),
        ("Con mèo đáng yêu", "ALLOW", "L2: Positive context - cat"),
        ("Tao thích nuôi mèo", "ALLOW", "L2: Positive context - nuôi"),
        ("Con chó nhà tao béo tốt", "ALLOW", "L2: Positive context - béo tốt"),
        ("Con heo này ngoan", "ALLOW", "L2: Positive context - ngoan"),
        
        # === INSULT PATTERN (Should WARN) - với Mitigation ===
        ("Thằng chó ngoan", "WARN", "L3: Insult prefix 'thằng' + animal -> NOT protected"),
        ("Đồ con chó", "WARN", "L3: Insult prefix 'đồ' + animal -> NOT protected"),
        ("Thằng ngu", "WARN", "L3: Pattern prefix + badword"),
        ("Đồ điên", "WARN", "L3: Pattern prefix + badword"),
        
        # === SEVERE (Should BLOCK) ===
        ("Địt mẹ mày", "BLOCK", "L1: Severe word"),
        ("dm", "BLOCK", "L1: Severe word short"),
        ("vcl", "BLOCK", "L1: Severe word"),
        
        # === NORMAL (Should ALLOW) ===
        ("Xin chào bạn", "ALLOW", "L4: Normal text"),
        ("Thằng Khánh", "ALLOW", "L4: Name, not badword"),
        ("Hôm nay trời đẹp", "ALLOW", "L4: Normal text"),
    ]
    
    print("\n" + "-" * 100)
    print(f"{'Input':<35} {'Expected':<10} {'Actual':<10} {'Layer':<25} {'Status'}")
    print("-" * 100)
    
    passed = 0
    failed = 0
    
    for input_text, expected_action, description in test_cases:
        result = engine.moderate(input_text)
        actual_action = result["action"]
        layer = result.get("layer", "N/A")
        
        is_pass = actual_action == expected_action
        status = "[PASS]" if is_pass else "[FAIL]"
        if is_pass:
            passed += 1
        else:
            failed += 1
        
        # Encode-safe output for Windows console
        try:
            input_display = input_text[:33] if len(input_text) > 33 else input_text
            # Encode to ASCII-safe format
            safe_input = input_display.encode('ascii', 'replace').decode('ascii')
            print(f"{safe_input:<35} {expected_action:<10} {actual_action:<10} {layer:<25} {status}")
        except Exception:
            print(f"{'[Text]':<35} {expected_action:<10} {actual_action:<10} {layer:<25} {status}")
    
    print("-" * 100)
    print(f"\nResult: {passed}/{passed + failed} tests passed")
    
    if failed > 0:
        print("\nSome tests FAILED. Check:")
        print("  - AI classifier behavior")
        print("  - badwords.txt content")
        print("  - POSITIVE_CONTEXTS coverage")
    else:
        print("\nAll tests PASSED!")
    
    print("\n" + "=" * 100)
    print("v2.1 CHANGES SUMMARY:")
    print("=" * 100)
    print("""
    [+] Layer Order Changed:
        OLD: Severe -> Pattern -> Context -> AI
        NEW: Severe -> Context -> Pattern -> AI
    
    [+] Mitigation Logic Added:
        - "Con cho ngoan" -> ALLOW (no insult prefix)
        - "Thang cho ngoan" -> WARN (has insult prefix)
    
    [+] Expanded POSITIVE_CONTEXTS:
        + Added: "nay", "kia", "do", "beo", "tot", "khoe", colors...
    
    [+] Result:
        - No more over-censoring of innocent animal phrases!
    """)
    print("=" * 100)
