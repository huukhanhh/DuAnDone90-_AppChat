class UserController:
    def __init__(self, model):
        self.model = model

    def get_users(self):
        return {"status": "success", "users": self.model.get_all_users()}

    def get_profile(self, user_id):
        return self.model.get_profile(user_id)

    def update_profile(self, user_id, display_name=None, avatar_data=None, old_password=None, new_password=None):
        if old_password and new_password:
             # Change password logic
             pass_response = self.model.change_password(user_id, old_password, new_password)
             if pass_response["status"] == "error":
                 return pass_response

        return self.model.update_profile(user_id, display_name, avatar_data)
