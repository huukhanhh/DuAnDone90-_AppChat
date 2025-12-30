# common/moderation/ai_classifier.py
# AI-based toxic/offensive content classifier
# Sử dụng pretrained model: cardiffnlp/twitter-roberta-base-offensive
# Module độc lập - KHÔNG phụ thuộc code rule-based

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import Optional


class ToxicAIClassifier:
    """
    AI classifier phát hiện nội dung toxic/offensive.
    
    Sử dụng pretrained model cardiffnlp/twitter-roberta-base-offensive
    chạy trên CPU.
    
    Threshold:
        - score >= 0.8 → BLOCK
        - 0.5 <= score < 0.8 → WARN  
        - score < 0.5 → ALLOW
    """
    
    MODEL_NAME = "cardiffnlp/twitter-roberta-base-offensive"
    
    # Label mapping: model outputs [not-offensive, offensive]
    LABEL_MAPPING = {
        0: "not-offensive",
        1: "offensive"
    }
    
    def __init__(self):
        """
        Khởi tạo classifier, load model và tokenizer.
        """
        self.device = torch.device("cpu")
        self.tokenizer: Optional[AutoTokenizer] = None
        self.model: Optional[AutoModelForSequenceClassification] = None
        self._loaded = False
        
        self._load_model()
    
    def _load_model(self):
        """Load pretrained model và tokenizer."""
        try:
            print(f"[AI_CLASSIFIER] Loading model: {self.MODEL_NAME}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME)
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode
            
            self._loaded = True
            print(f"[AI_CLASSIFIER] Model loaded successfully on {self.device}")
            
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
                "reason": "ai_offensive"
            }
        """
        # Fallback nếu model chưa load
        if not self._loaded or self.model is None or self.tokenizer is None:
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": "ai_model_not_loaded"
            }
        
        # Empty text
        if not text or not text.strip():
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": "empty_text"
            }
        
        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                # Softmax to get probabilities
                probs = torch.softmax(logits, dim=-1)
                
                # Get offensive probability (label 1)
                offensive_score = probs[0][1].item()
            
            # Determine action based on score
            action = self._score_to_action(offensive_score)
            
            return {
                "action": action,
                "score": round(offensive_score, 4),
                "reason": "ai_offensive"
            }
            
        except Exception as e:
            print(f"[AI_CLASSIFIER] Error during inference: {e}")
            return {
                "action": "ALLOW",
                "score": 0.0,
                "reason": f"ai_error: {str(e)}"
            }
    
    def _score_to_action(self, score: float) -> str:
        """
        Chuyển đổi score thành action.
        
        Args:
            score: Offensive probability (0.0 - 1.0)
            
        Returns:
            "ALLOW" | "WARN" | "BLOCK"
        """
        if score >= 0.8:
            return "BLOCK"
        elif score >= 0.5:
            return "WARN"
        else:
            return "ALLOW"
    
    def is_loaded(self) -> bool:
        """Kiểm tra model đã load chưa."""
        return self._loaded


# === TEST BLOCK ===
if __name__ == "__main__":
    print("=" * 60)
    print("ToxicAIClassifier - Test Suite")
    print("=" * 60)
    
    # Initialize classifier
    classifier = ToxicAIClassifier()
    
    if not classifier.is_loaded():
        print("\n[ERROR] Model failed to load. Please check:")
        print("  1. transformers installed: pip install transformers")
        print("  2. torch installed: pip install torch")
        print("  3. Internet connection for downloading model")
        exit(1)
    
    # Test cases
    test_cases = [
        # Normal text
        ("Hello, how are you?", "Normal greeting"),
        ("I love this product!", "Positive sentiment"),
        ("The weather is nice today", "Neutral statement"),
        
        # Potentially offensive
        ("You are so stupid", "Insult"),
        ("I hate you", "Hate speech"),
        ("Go to hell", "Aggressive"),
        ("You idiot", "Name calling"),
        
        # Vietnamese (model may not handle well)
        ("Xin chào bạn", "Vietnamese greeting"),
        ("Đồ ngu", "Vietnamese insult"),
    ]
    
    print("\n" + "-" * 60)
    print(f"{'Text':<40} {'Action':<8} {'Score':<8}")
    print("-" * 60)
    
    for text, description in test_cases:
        result = classifier.check(text)
        action = result["action"]
        score = result["score"]
        
        # Color coding for terminal (optional)
        if action == "BLOCK":
            marker = "🔴"
        elif action == "WARN":
            marker = "🟡"
        else:
            marker = "🟢"
        
        print(f"{marker} {text:<38} {action:<8} {score:<8.4f}")
    
    print("-" * 60)
    print("\nThreshold rules:")
    print("  🔴 BLOCK: score >= 0.8")
    print("  🟡 WARN:  0.5 <= score < 0.8")
    print("  🟢 ALLOW: score < 0.5")
    print("=" * 60)
