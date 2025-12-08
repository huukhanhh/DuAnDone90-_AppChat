from client.controllers.base import BaseController
from client.controllers.chat_mixin import ChatMixin
from client.controllers.user_mixin import UserMixin

# Main Client Controller Facade
class AuthController(BaseController, ChatMixin, UserMixin):
    pass