# client/controllers/auth_controller_client.py
import socket
import json
import threading
import time
import struct
from config.config import SERVER_CONFIG
from queue import Queue


class AuthController:
    def __init__(self, socket, host=SERVER_CONFIG["host"], port=SERVER_CONFIG["port"]):
        self.host = host
        self.port = port
        self.client_socket = socket
        self.current_user_id = None
        self.reconnect_attempts = 3
        self.message_queue = Queue()  # Queue chứa tin nhắn đến
        self.response_queue = Queue()  # Queue chứa phản hồi request
        self.running = True

        # Bắt đầu luồng nhận tin
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _send_all(self, sock, data):
        total_sent = 0
        while total_sent < len(data):
            sent = sock.send(data[total_sent:])
            if sent == 0: raise socket.error("Socket broken")
            total_sent += sent

    def _recv_all(self, sock, length):
        data = b''
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), 10485760))  # 10MB chunk
            if not chunk: raise socket.error("Socket broken")
            data += chunk
        return data

    def _receive_loop(self):
        while self.running:
            try:
                if self.client_socket:
                    length_data = self._recv_all(self.client_socket, 4)
                    if not length_data: break
                    data_length = struct.unpack('>I', length_data)[0]

                    data = self._recv_all(self.client_socket, data_length)
                    response = json.loads(data.decode('utf-8'))

                    action = response.get("action")

                    # DANH SÁCH CÁC ACTION TỰ ĐẨY VỀ (PUSH NOTIFICATION)
                    push_actions = [
                        "message",
                        "group_message",
                        "new_group",
                        "profile_update_notification"  # <-- Mới thêm
                    ]

                    if action in push_actions:
                        self.message_queue.put(response)
                    else:
                        self.response_queue.put(response)

            except (socket.error, json.JSONDecodeError):
                if not self.reconnect(): break
                time.sleep(1)
            except Exception as e:
                print(f"Receive loop error: {e}")
                break

    def reconnect(self):
        print("Mất kết nối, đang thử lại...")
        try:
            self.client_socket.close()
        except:
            pass

        for _ in range(self.reconnect_attempts):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.host, self.port))

                if self.current_user_id:
                    req = {"action": "resume_session", "user_id": self.current_user_id}
                    d = json.dumps(req).encode('utf-8')
                    l = struct.pack('>I', len(d))
                    self.client_socket.send(l + d)

                print("Kết nối lại thành công!")
                return True
            except:
                time.sleep(2)
        return False

    def send_request(self, request, timeout=5):
        try:
            with self.response_queue.mutex:
                self.response_queue.queue.clear()

            data = json.dumps(request).encode('utf-8')
            length = struct.pack('>I', len(data))
            self._send_all(self.client_socket, length + data)

            return self.response_queue.get(timeout=timeout)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # === APIs ===
    def get_users(self):
        return self.send_request({"action": "get_users"}).get("users", [])

    def send_message(self, receiver_id, message):
        return self.send_request({"action": "message", "receiver_id": receiver_id, "message": message})

    def send_image(self, receiver_id, image_data, filename):
        return self.send_request({
            "action": "send_image", "receiver_id": receiver_id,
            "image_data": image_data, "filename": filename
        }, timeout=20)

    def send_voice(self, receiver_id, voice_data, filename):
        return self.send_request({
            "action": "send_voice", "receiver_id": receiver_id,
            "voice_data": voice_data, "filename": filename
        }, timeout=20)

    def send_video(self, receiver_id, video_data, filename):
        return self.send_request({
            "action": "send_video", "receiver_id": receiver_id,
            "video_data": video_data, "filename": filename
        }, timeout=120)

    def get_chat_history(self, receiver_id):
        return self.send_request({"action": "get_chat_history", "receiver_id": receiver_id}).get("history", [])

    def get_profile(self):
        return self.send_request({"action": "get_profile"})

    def update_profile(self, display_name, avatar_data, old_password=None, new_password=None):
        req = {
            "action": "update_profile",
            "display_name": display_name,
            "avatar": avatar_data
        }
        if new_password:
            req["old_password"] = old_password
            req["new_password"] = new_password
        # Tăng timeout lên 30 giây vì avatar có thể rất lớn
        return self.send_request(req, timeout=30)

    def create_group(self, name, member_ids):
        return self.send_request({"action": "create_group", "name": name, "members": member_ids})

    def get_groups(self):
        return self.send_request({"action": "get_groups"}).get("groups", [])

    def send_group_message(self, group_id, message, is_image=False, image_data=None):
        req = {
            "action": "group_message",
            "group_id": group_id,
            "message": message,
            "is_image": is_image,
            "image_data": image_data
        }
        return self.send_request(req)

    def get_group_chat_history(self, group_id):
        return self.send_request({"action": "get_group_history", "group_id": group_id}).get("history", [])

    def get_incoming_message(self, timeout=0.1):
        try:
            return self.message_queue.get(timeout=timeout)
        except:
            return None

    def stop(self):
        self.running = False
        try:
            self.client_socket.close()
        except:
            pass