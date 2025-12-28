# client/controllers/moderation_controller.py
# Client-side moderation controller - kiểm tra trước khi gửi tin nhắn

from common.moderation import TextModerationEngine, ACTION_ALLOW, create_result


class ClientModerationController:
    """
    Controller kiểm duyệt nội dung phía client.
    Chạy local để kiểm tra trước khi gửi tin nhắn đến server.
    """
    
    def __init__(self, badwords_path: str):
        """
        Khởi tạo controller với đường dẫn file từ cấm.
        
        Args:
            badwords_path: Đường dẫn tới file badwords.txt
        """
        self.text_engine = TextModerationEngine(badwords_path)
    
    def check_outgoing_text(self, text: str) -> dict:
        """
        Kiểm tra tin nhắn văn bản trước khi gửi.
        
        Args:
            text: Nội dung tin nhắn
            
        Returns:
            dict với format chuẩn:
            {
                "action": "ALLOW" | "BLOCK",
                "reason": "string",
                "hits": ["từ vi phạm"],
                "score": None
            }
        """
        return self.text_engine.check(text)
    
    def check_outgoing_image(self, image_payload) -> dict:
        """
        Kiểm tra ảnh trước khi gửi.
        
        STUB: Bước 1 chưa có model AI, luôn trả về ALLOW.
        TODO: Thêm model NSFW detection ở bước sau.
        
        Args:
            image_payload: Dữ liệu ảnh (bytes hoặc base64 string)
            
        Returns:
            dict với format chuẩn (luôn ALLOW trong bước 1)
        """
        # TODO: Implement NSFW detection model
        return create_result(ACTION_ALLOW)
