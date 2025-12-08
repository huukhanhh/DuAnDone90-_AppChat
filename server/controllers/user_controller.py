class UserController:
    def __init__(self, model):
        self.model = model

    def get_users(self):
        return {"status": "success", "users": self.model.get_all_users()}

    def get_profile(self, user_id):
        return self.model.get_profile(user_id)

    def update_profile(self, user_id, display_name, avatar_data, old_password=None, new_password=None):
        error_resp = None
        
        # 1. Change Password if requested
        if new_password:
            pass_res = self.model.change_password(user_id, old_password, new_password)
            if pass_res.get("status") != "success":
                return pass_res

        # 2. Update Profile
        res = self.model.update_profile(user_id, display_name=display_name, avatar_data=avatar_data)
        
        # Return result (if password change was success but profile failed? unlikely but handle basic return)
        return res
