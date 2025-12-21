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

    def add_member(self, group_id, owner_id, user_ids, added_by_name):
        # Allow adding multiple or single? Request says "add user" -> assume list for future proof or single?
        # Model takes single. Let's iterate if list or just handle single.
        # Flow: Owner/Member adds New User? Typically anyone in group can add.
        # Let's assume passed user_ids is a list.
        
        results = []
        for uid in user_ids:
            res = self.model.add_group_member(group_id, uid, added_by_name)
            if res["status"] == "success":
                results.append(uid)
        
        return {"status": "success", "added_members": results}

    def leave_group(self, group_id, user_id, user_name):
        return self.model.remove_group_member(group_id, user_id, user_name)

    def get_members(self, group_id):
        return {"status": "success", "members": self.model.get_group_members(group_id)}
