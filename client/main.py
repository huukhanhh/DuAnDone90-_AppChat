# client/main.py
import sys
from PySide6 import QtWidgets
from views.login_view import LoginView
from views.register_view import RegisterView
from views.main_view import MainView

class ChatApp:
    def __init__(self):
        self.app = QtWidgets.QApplication(sys.argv)
        self.current_window = None
        self.controller = None # Đổi socket thành controller
        self.user_id = None
        self.display_name = None

    def show_login(self):
        if self.current_window:
            self.current_window.close()
        self.current_window = LoginView(self)
        self.current_window.show()

    def show_register(self):
        if self.current_window:
            self.current_window.close()
        self.current_window = RegisterView(self)
        self.current_window.show()

    # --- SỬA HÀM NÀY ---
    def show_main(self, controller, user_id, display_name):
        try:
            self.controller = controller
            self.user_id = user_id
            self.display_name = display_name
            if self.current_window:
                self.current_window.close()
            # Truyền controller vào MainView
            self.current_window = MainView(self, controller, user_id, display_name)
            self.current_window.show()
        except Exception as e:
            print(f"CRITICAL ERROR starting MainView: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        self.show_login()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = ChatApp()
    app.run()