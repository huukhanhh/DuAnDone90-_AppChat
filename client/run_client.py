# client/run_client.py
import sys
sys.path.append("D:/Python_VsCode/AppChat")  # Thêm đường dẫn gốc của dự án

from main import ChatApp

if __name__ == "__main__":
    app = ChatApp()
    app.run()