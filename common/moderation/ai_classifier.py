# common/moderation/ai_classifier.py
# AI-based toxic/offensive content classifier
# Sử dụng pretrained model đa ngôn ngữ: christinacdl/XLM_RoBERTa-Offensive-Language-Detection-8-langs-new
# Labels: NOT, OFFENSIVE
# Module độc lập - KHÔNG phụ thuộc code rule-based

from transformers import pipeline
from typing import Optional


class ToxicAIClassifier:
    """
    AI classifier phát hiện nội dung toxic/offensive đa ngôn ngữ.
    
    Sử dụng pretrained model XLM-RoBERTa multilingual chạy trên CPU.
    
    3 mức độ dựa trên confidence score:
        - score < 0.45 -> ALLOW (tin nhắn bình thường)
        - 0.45 ≤ score < 0.60 -> WARN (cảnh báo, không censor)
        - score ≥ 0.60 -> BLOCK (cảnh báo + censor thành ***)
    """
    
    MODEL_NAME = "christinacdl/XLM_RoBERTa-Offensive-Language-Detection-8-langs-new"
    
    # Ngưỡng phân loại 3 mức
    THRESHOLD_WARN = 0.45   # Score >= này sẽ WARN
    THRESHOLD_BLOCK = 0.85  # Score >= này sẽ BLOCK (tăng từ 0.60 để có WARN)
    
    def __init__(self):
        """
        Khởi tạo classifier, load model bằng pipeline.
        """
        self._pipeline: Optional[pipeline] = None
        self._loaded = False
        
        self._load_model()
    
    def _load_model(self):
        """Load pretrained model bằng transformers pipeline."""
        try:
            print(f"[AI_CLASSIFIER] Loading model: {self.MODEL_NAME}")
            
            self._pipeline = pipeline(
                "text-classification",
                model=self.MODEL_NAME,
                device=-1  # CPU
            )
            
            self._loaded = True
            print(f"[AI_CLASSIFIER] Model loaded successfully (CPU)")
            
            # Warmup inference để tránh lag tin nhắn đầu tiên
            print(f"[AI_CLASSIFIER] Warming up model...")
            _ = self._pipeline("test warmup message")
            print(f"[AI_CLASSIFIER] Warmup complete - ready for inference")
            
        except Exception as e:
            print(f"[AI_CLASSIFIER] Error loading model: {e}")
            self._loaded = False
    
    def check(self, text: str) -> dict:
        """
        Kiểm tra văn bản có toxic/offensive hay không.
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            dict với format:
            {
                "action": "ALLOW" | "WARN" | "BLOCK",
                "score": float (0.0 - 1.0),
                "reason": str,
                "label": str,
                "censored_text": str (văn bản đã censor nếu BLOCK)
            }
        """
        # Fallback nếu model chưa load
        if not self._loaded or self._pipeline is None:
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": "ai_model_not_loaded",
                "label": "UNKNOWN",
                "censored_text": text
            }
        
        # Empty text
        if not text or not text.strip():
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": "empty_text",
                "label": "NOT",
                "censored_text": text
            }
        
        try:
            # Inference với pipeline
            result = self._pipeline(text)[0]
            
            label = result["label"]  # NOT hoặc OFFENSIVE
            score = result["score"]  # confidence score
            
            # Xác định action dựa trên score và label
            if label == "NOT":
                # Tin nhắn không offensive
                action = "ALLOW"
                reason = ""
                censored_text = text
            else:
                # Tin nhắn offensive - phân loại theo score
                if score >= self.THRESHOLD_BLOCK:
                    action = "BLOCK"
                    reason = "Tin nhắn vi phạm nặng - đã được censor"
                    censored_text = self._censor_text(text)
                elif score >= self.THRESHOLD_WARN:
                    action = "WARN"
                    reason = "Vui lòng điều chỉnh hành vi, tránh sử dụng từ ngữ không phù hợp"
                    censored_text = text  # Không censor, chỉ cảnh báo
                else:
                    action = "ALLOW"
                    reason = ""
                    censored_text = text
            
            return {
                "action": action,
                "score": round(score, 4),
                "reason": reason,
                "label": label,
                "censored_text": censored_text
            }
            
        except Exception as e:
            print(f"[AI_CLASSIFIER] Error during inference: {e}")
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": f"ai_error: {str(e)}",
                "label": "ERROR",
                "censored_text": text
            }
    
    def _censor_text(self, text: str) -> str:
        """
        Censor toàn bộ tin nhắn thành ****** (cùng độ dài).
        
        Args:
            text: Văn bản gốc
            
        Returns:
            Văn bản đã censor (thay bằng *)
        """
        if not text:
            return text
        
        # Censor toàn bộ tin nhắn, giữ nguyên khoảng trắng
        result = []
        for char in text:
            if char.isspace():
                result.append(char)
            else:
                result.append('*')
        return ''.join(result)
    
    def is_loaded(self) -> bool:
        """Kiểm tra model đã load chưa."""
        return self._loaded


# === TEST BLOCK ===
if __name__ == "__main__":
    print("=" * 70)
    print("ToxicAIClassifier - Multilingual Test Suite")
    print("Model: christinacdl/XLM_RoBERTa-Offensive-Language-Detection-8-langs-new")
    print("=" * 70)
    
    # Initialize classifier
    classifier = ToxicAIClassifier()
    
    if not classifier.is_loaded():
        print("\n[ERROR] Model failed to load. Please check:")
        print("  1. pip install transformers torch")
        print("  2. Internet connection for downloading model")
        exit(1)
    
    # Test cases tiếng Việt
    test_cases = [
        # Bình thường
        "Xin chào bạn",
        "Hôm nay bạn thế nào?",
        "Cảm ơn bạn rất nhiều",
        
        # Xúc phạm nhẹ
        "Đồ ngu",
        "Nói chuyện ngu quá",
        "Mày ngu thế",
        
        # Nặng
        "Địt mẹ mày",
        "Thằng chó",
        "Đồ con chó",
        
        # Biến thể
        "d i t m e",
        "dit me",
        "d!t m3",
    ]
    
    print("\n" + "-" * 90)
    print(f"{'Text':<25} {'Label':<10} {'Action':<8} {'Score':<8} {'Censored':<20}")
    print("-" * 90)
    
    for text in test_cases:
        result = classifier.check(text)
        action = result["action"]
        score = result["score"]
        label = result["label"]
        censored = result.get("censored_text", text)
        
        # Marker
        if action == "BLOCK":
            marker = "[X]"
        elif action == "WARN":
            marker = "[!]"
        else:
            marker = "[O]"
        
        # Rút gọn censored nếu quá dài
        censored_display = censored[:18] + ".." if len(censored) > 20 else censored
        
        print(f"{marker} {text:<23} {label:<10} {action:<8} {score:.4f}   {censored_display}")
    
    print("-" * 90)
    print("\nThreshold settings:")
    print(f"  ALLOW: score < {classifier.THRESHOLD_WARN}")
    print(f"  WARN:  {classifier.THRESHOLD_WARN} <= score < {classifier.THRESHOLD_BLOCK}")
    print(f"  BLOCK: score >= {classifier.THRESHOLD_BLOCK}")
    print("\nAction mapping:")
    print("  [O] ALLOW  - Tin nhan binh thuong")
    print("  [!] WARN   - Canh bao, khong censor")
    print("  [X] BLOCK  - Canh bao + censor thanh ***")
    print("=" * 90)
