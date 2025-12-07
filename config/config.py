# config/config.py

GEMINI_API_KEY = "AIzaSyCbC_gKgN383w4MLX2SzqOsxGsGc_qyDQo"  # Thay thế bằng API Key của bạn
DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "chat_app"
}

SERVER_CONFIG = {
    "host": "192.168.243.1",  # IP chung
    "port": 5001         # Port cho socket TCP
}

MULTICAST_CONFIG = {
    "group": "239.0.0.1",  # Multicast IP (phạm vi local)
    "port": 5008
}