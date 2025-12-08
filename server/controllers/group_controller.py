class GroupController:
    def __init__(self, model):
        self.model = model

    def create_group(self, name, owner_id, members):
        return self.model.create_group(name, owner_id, members)

    def get_groups(self, user_id):
        return {"status": "success", "groups": self.model.get_user_groups(user_id)}

    def handle_group_message(self, sender_id, request):
        gid = request.get("group_id")
        msg = request.get("message")
        is_img = request.get("is_image", False)
        img_data = request.get("image_data")
        
        self.model.save_group_message(gid, sender_id, msg, is_image=is_img, image_data=img_data)
        return {"status": "success", "group_id": gid}

    def get_history(self, group_id):
        return {"status": "success", "history": self.model.get_group_chat_history(group_id)}
