# server/controllers/moderation_controller.py
# Server-side moderation controller - kiểm tra tin nhắn đến

from common.moderation import TextModerationEngine, ACTION_ALLOW, create_result


class ServerModerationController:
    """
    Controller kiểm duyệt nội dung phía server.
    Kiểm tra tin nhắn nhận được trước khi broadcast.
    """
    
    def __init__(self, badwords_path: str):
        """
        Khởi tạo controller với đường dẫn file từ cấm.
        
        Args:
            badwords_path: Đường dẫn tới file badwords.txt
        """
        self.text_engine = TextModerationEngine(badwords_path)
    
    def check_incoming_text(self, msg: dict) -> dict:
        """
        Kiểm tra tin nhắn văn bản nhận được.
        
        Args:
            msg: Request dict từ client, có field "message" chứa nội dung
            
        Returns:
            dict với format chuẩn:
            {
                "action": "ALLOW" | "BLOCK",
                "reason": "string",
                "hits": ["từ vi phạm"],
                "score": None
            }
        """
        text = msg.get("message", "")
        return self.text_engine.check(text)
    
    def check_incoming_image(self, msg: dict) -> dict:
        """
        Kiểm tra ảnh nhận được.
        
        STUB: Bước 1 chưa có model AI, luôn trả về ALLOW.
        TODO: Thêm model NSFW detection ở bước sau.
        
        Args:
            msg: Request dict từ client, có field "image_data"
            
        Returns:
            dict với format chuẩn (luôn ALLOW trong bước 1)
        """
        # TODO: Implement NSFW detection model
        return create_result(ACTION_ALLOW)
