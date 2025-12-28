# common/moderation/types.py
# Định nghĩa constants và kiểu dữ liệu cho moderation

# Action constants
ACTION_ALLOW = "ALLOW"
ACTION_WARN = "WARN"  # Cho phép gửi nhưng cảnh báo (đã censor)
ACTION_BLOCK = "BLOCK"


def create_result(action: str, reason: str = "", hits: list = None, score: float = None, censored_text: str = None) -> dict:
    """
    Tạo result dict chuẩn cho moderation.
    
    Args:
        action: ACTION_ALLOW, ACTION_WARN, hoặc ACTION_BLOCK
        reason: Lý do (string ngắn gọn)
        hits: Danh sách từ vi phạm nếu có
        score: Điểm số (None cho bước 1)
        censored_text: Văn bản đã được censor (thay từ cấm bằng ***)
    
    Returns:
        dict với format chuẩn:
        {
            "action": "ALLOW" | "WARN" | "BLOCK",
            "reason": "string ngắn gọn",
            "hits": ["..."],
            "score": float|None,
            "censored_text": str|None
        }
    """
    return {
        "action": action,
        "reason": reason,
        "hits": hits if hits is not None else [],
        "score": score,
        "censored_text": censored_text
    }
