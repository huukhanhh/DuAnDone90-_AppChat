class AuthController:
    def __init__(self, model):
        self.model = model

    def handle_login(self, email, password):
        return self.model.login_user(email, password)

    def handle_register(self, display_name, email, password):
        return self.model.register_user(display_name, email, password)