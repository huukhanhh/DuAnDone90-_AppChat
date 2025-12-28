# config/config.py
import os

GEMINI_API_KEY = "AIzaSyCbC_gKgN383w4MLX2SzqOsxGsGc_qyDQo"  # Thay thế bằng API Key của bạn

# === MODERATION CONFIG ===
# Đường dẫn tới file danh sách từ cấm
_config_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_config_dir)
BADWORDS_PATH = os.path.join(_project_root, "common", "moderation", "badwords.txt")
DATABASE_CONFIG = {
    "host": "192.168.110.111",
    "user": "root",
    "password": "root",
    "database": "chat_app"
}

SERVER_CONFIG = {
    "host": "192.168.110.111",  # IP chung
    "port": 5001         # Port cho socket TCP
}

MULTICAST_CONFIG = {
    "group": "239.0.0.1",  # Multicast IP (phạm vi local)
    "port": 5008
}