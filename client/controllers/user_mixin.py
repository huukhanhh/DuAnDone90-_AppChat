class UserMixin:
    def get_users(self):
        return self.send_request({"action": "get_users"}).get("users", [])

    def get_profile(self):
        return self.send_request({"action": "get_profile"})

    def update_profile(self, display_name, avatar_data, old_password=None, new_password=None):
        req = {"action": "update_profile", "display_name": display_name, "avatar": avatar_data}
        if new_password:
            req["old_password"] = old_password
            req["new_password"] = new_password
        return self.send_request(req, timeout=30)
