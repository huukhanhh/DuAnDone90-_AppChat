class ChatMixin:
    def send_message(self, receiver_id, message):
        return self.send_request({"action": "message", "receiver_id": receiver_id, "message": message})

    def send_image(self, receiver_id, image_data, filename):
        return self.send_request({
            "action": "send_image", "receiver_id": receiver_id,
            "image_data": image_data, "filename": filename
        }, timeout=20)

    def send_voice(self, receiver_id, voice_data, filename):
        return self.send_request({
            "action": "send_voice", "receiver_id": receiver_id,
            "voice_data": voice_data, "filename": filename
        }, timeout=20)

    def send_video(self, receiver_id, video_data, filename):
        return self.send_request({
            "action": "send_video", "receiver_id": receiver_id,
            "video_data": video_data, "filename": filename
        }, timeout=120)

    def send_call_log(self, receiver_id, content):
        return self.send_request({
            "action": "system_log", "receiver_id": receiver_id, "content": content
        })

    def send_typing_status(self, receiver_id, is_typing):
        # Fire and forget, no need to wait for response usually, but recv loop handles it.
        return self.send_request({
            "action": "typing", "receiver_id": receiver_id, "is_typing": is_typing
        })

    def send_signal(self, target_id, signal_type, data=None):
        payload = {"action": "signal", "target_id": target_id, "signal_type": signal_type}
        if data: payload.update(data)
        return self.send_request(payload)

    def get_chat_history(self, receiver_id):
        return self.send_request({"action": "get_chat_history", "receiver_id": receiver_id}).get("history", [])

    def get_incoming_message(self, timeout=0.1):
        try: return self.message_queue.get(timeout=timeout)
        except: return None
        
    def create_group(self, name, member_ids):
        return self.send_request({"action": "create_group", "name": name, "members": member_ids})

    def get_groups(self):
        return self.send_request({"action": "get_groups"}).get("groups", [])

    def send_group_message(self, group_id, message, is_image=False, image_data=None):
        req = {"action": "group_message", "group_id": group_id, "message": message, "is_image": is_image, "image_data": image_data}
        return self.send_request(req)

    def get_group_chat_history(self, group_id):
        return self.send_request({"action": "get_group_history", "group_id": group_id}).get("history", [])
