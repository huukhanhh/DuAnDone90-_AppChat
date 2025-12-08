class ChatController:
    def __init__(self, model):
        self.model = model

    def get_history(self, user_id, receiver_id):
        return {"status": "success", "history": self.model.get_chat_history(user_id, receiver_id)}

    def handle_message(self, sender_id, request):
        receiver_id = request.get("receiver_id")
        action = request.get("action")
        
        content = request.get("message")
        is_call_log = request.get("is_call_log", False)

        # Basic Text / System Log
        if action == "message" or action == "system_log":
             # "system_log" logic from previous turn uses save_message with is_call_log
             # The request from client for system_log: action="system_log", content="..."
             if action == "system_log":
                 content = request.get("content")
                 is_call_log = True
             
             self.model.save_message(sender_id, receiver_id, content, is_call_log=is_call_log)
             return {
                 "msg_type": "text" if not is_call_log else "call_log",
                 "content": content,
                 "is_call_log": is_call_log
             }

        # Media Logic
        elif action == "send_image":
            filename = request.get("filename", "image.jpg")
            self.model.save_image_message(sender_id, receiver_id, request.get("image_data"), filename)
            return {"msg_type": "image", "content": filename}
            
        elif action == "send_voice":
            filename = request.get("filename", "voice.wav")
            self.model.save_voice_message(sender_id, receiver_id, request.get("voice_data"), filename)
            return {"msg_type": "voice", "content": filename}
            
        elif action == "send_video":
            filename = request.get("filename", "video.mp4")
            self.model.save_video_message(sender_id, receiver_id, request.get("video_data"), filename)
            return {"msg_type": "video", "content": filename}

        return None
