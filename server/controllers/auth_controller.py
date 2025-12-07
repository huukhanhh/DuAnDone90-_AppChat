# server/controllers/auth_controller.py
import json
import socket
import struct
from config.config import SERVER_CONFIG
import logging
import threading
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='server.log',
    filemode='a'
)
logger = logging.getLogger(__name__)


class ChatController:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((SERVER_CONFIG["host"], SERVER_CONFIG["port"]))
        self.server_socket.listen(5)
        self.clients = {}
        self.user_sockets = {}
        self.offline_messages = {}
        self.lock = threading.Lock()
        try:
            from server.models.user_model import UserModel
            self.model = UserModel()
            logger.info("UserModel initialized successfully")
        except Exception as e:
            logger.error(f"Không thể khởi tạo UserModel: {str(e)}")
            raise

    def _send_all(self, sock, data):
        total_sent = 0
        while total_sent < len(data):
            sent = sock.send(data[total_sent:])
            if sent == 0:
                raise socket.error("Socket connection broken")
            total_sent += sent
        return total_sent

    def _recv_all(self, sock, length):
        data = b''
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), 10485760))
            if not chunk:
                raise socket.error("Socket connection broken")
            data += chunk
        return data

    def send_to_client(self, client_socket, message):
        try:
            if client_socket.fileno() != -1:
                data = json.dumps(message).encode('utf-8')
                length = struct.pack('>I', len(data))
                self._send_all(client_socket, length + data)
                return True
        except Exception as e:
            logger.error(f"Lỗi gửi message: {str(e)}")
            return False
        return False

    def handle_client(self, client_socket):
        client_socket.settimeout(600)
        logger.info("New client session started")

        try:
            while True:
                try:
                    length_data = self._recv_all(client_socket, 4)
                    if not length_data: break

                    data_length = struct.unpack('>I', length_data)[0]
                    # Tăng limit lên 10MB cho avatar (đủ cho ảnh đã resize 200x200)
                    if data_length > 10 * 1024 * 1024:  # 10MB limit
                        logger.warning(f"Request quá lớn: {data_length} bytes")
                        self.send_to_client(client_socket, {"status": "error", "message": "Dữ liệu quá lớn (tối đa 10MB)"})
                        break

                    data = self._recv_all(client_socket, data_length)
                    message = data.decode('utf-8')
                    request = json.loads(message)
                    action = request.get("action")

                    response = {"status": "error", "message": "Hành động không hợp lệ"}

                    # === AUTH ===
                    if action == "login":
                        response = self.model.login_user(request.get("email"), request.get("password"))
                        if response.get("status") == "success":
                            user_id = response.get("user_id")
                            with self.lock:
                                self.clients[client_socket] = user_id
                                self.user_sockets[user_id] = client_socket

                            # Gửi tin offline nếu có
                            if user_id in self.offline_messages:
                                for msg in self.offline_messages[user_id]:
                                    self.send_to_client(client_socket, msg)
                                del self.offline_messages[user_id]

                    elif action == "register":
                        response = self.model.register_user(request.get("display_name"), request.get("email"),
                                                            request.get("password"))

                    # === PROFILE & USERS ===
                    elif action == "get_users":
                        response = {"status": "success", "users": self.model.get_all_users()}

                    elif action == "get_profile":
                        uid = self.clients.get(client_socket)
                        if uid: response = self.model.get_profile(uid)



                    elif action == "update_profile":

                        uid = self.clients.get(client_socket)
                        if uid:

                            # 1. Xử lý đổi password trước (nếu có)
                            new_pass = request.get("new_password")
                            if new_pass:
                                pass_res = self.model.change_password(uid, request.get("old_password"), new_pass)
                                if pass_res.get("status") != "success":
                                    # Nếu đổi password thất bại, trả về lỗi ngay
                                    response = pass_res
                                    self.send_to_client(client_socket, response)
                                    continue

                            # 2. Update profile (display_name và avatar)
                            res = self.model.update_profile(
                                uid,
                                display_name=request.get("display_name"),
                                avatar_data=request.get("avatar")

                            )
                            if res["status"] == "success":

                                # 3. Lấy thông tin mới nhất
                                new_profile = self.model.get_profile(uid)

                                # 4. BROADCAST: Báo cho mọi người (BAO GỒM CẢ BẢN THÂN)
                                # CHỈ GỬI user_id và display_name, KHÔNG GỬI avatar (quá lớn)
                                # Client sẽ tự fetch lại avatar từ get_users hoặc get_profile
                                noti_data = {
                                    "action": "profile_update_notification",
                                    "user_id": uid,
                                    "display_name": new_profile.get("display_name")
                                    # KHÔNG gửi avatar ở đây để tránh crash do dữ liệu quá lớn
                                }

                                with self.lock:
                                    # Gửi notification cho tất cả user (bao gồm cả chính user đó)
                                    for u_id, sock in list(self.user_sockets.items()):  # Dùng list() để tránh RuntimeError
                                        try:
                                            self.send_to_client(sock, noti_data)
                                        except Exception as e:
                                            logger.error(f"Lỗi gửi notification cho user {u_id}: {e}")
                                            # Nếu socket bị lỗi, sẽ được dọn dẹp ở finally block
                                response = {"status": "success", "message": "Cập nhật thành công"}
                            else:
                                response = res



                    # === CHAT 1-1 ===
                    elif action == "get_chat_history":
                        uid = self.clients.get(client_socket)
                        if uid:
                            response = {"status": "success",
                                        "history": self.model.get_chat_history(uid, request.get("receiver_id"))}

                    elif action in ["message", "send_image", "send_voice", "send_video"]:
                        if client_socket in self.clients:
                            sender_id = self.clients[client_socket]
                            receiver_id = request.get("receiver_id")

                            # Xác định loại tin nhắn và lưu DB
                            msg_type = "text"
                            content = request.get("message")

                            if action == "send_image":
                                msg_type = "image"
                                content = request.get("filename", "image.jpg")
                                self.model.save_image_message(sender_id, receiver_id, request.get("image_data"),
                                                              content)
                            elif action == "send_voice":
                                msg_type = "voice"
                                content = request.get("filename", "voice.wav")
                                self.model.save_voice_message(sender_id, receiver_id, request.get("voice_data"),
                                                              content)
                            elif action == "send_video":
                                msg_type = "video"
                                content = request.get("filename", "video.mp4")
                                self.model.save_video_message(sender_id, receiver_id, request.get("video_data"),
                                                              content)
                            else:
                                self.model.save_message(sender_id, receiver_id, content)

                            # Tạo gói tin gửi đi
                            msg_data = {
                                "action": "message",
                                "sender_id": sender_id,
                                "sender_name": self.model.get_display_name(sender_id),
                                "sender_avatar": self.model.get_avatar(sender_id),
                                "receiver_id": receiver_id,
                                "message": request.get("message"),
                                "is_image": action == "send_image",
                                "image_data": request.get("image_data"),
                                "is_voice": action == "send_voice",
                                "voice_data": request.get("voice_data"),
                                "is_video": action == "send_video",
                                "video_data": request.get("video_data")
                            }

                            # Gửi cho receiver
                            with self.lock:
                                if receiver_id in self.user_sockets:
                                    self.send_to_client(self.user_sockets[receiver_id], msg_data)
                                else:
                                    if receiver_id not in self.offline_messages: self.offline_messages[receiver_id] = []
                                    self.offline_messages[receiver_id].append(msg_data)

                            response = {"status": "success"}

                    # === GROUP CHAT ===
                    elif action == "create_group":
                        owner_id = self.clients.get(client_socket)
                        if owner_id:
                            res = self.model.create_group(request.get("name"), owner_id, request.get("members"))
                            if res["status"] == "success":
                                noti = {
                                    "action": "new_group",
                                    "group_id": res["group_id"],
                                    "name": request.get("name"),
                                    "owner_name": self.model.get_display_name(owner_id)
                                }
                                with self.lock:
                                    for mid in res["members"]:
                                        if mid != owner_id and mid in self.user_sockets:
                                            self.send_to_client(self.user_sockets[mid], noti)
                            response = res

                    elif action == "get_groups":
                        uid = self.clients.get(client_socket)
                        if uid:
                            response = {"status": "success", "groups": self.model.get_user_groups(uid)}

                    elif action == "group_message":
                        sender_id = self.clients.get(client_socket)
                        if sender_id:
                            gid = request.get("group_id")
                            msg = request.get("message")
                            is_img = request.get("is_image", False)
                            img_data = request.get("image_data")

                            self.model.save_group_message(gid, sender_id, msg, is_image=is_img, image_data=img_data)
                            members = self.model.get_group_members(gid)

                            msg_data = {
                                "action": "group_message",
                                "group_id": gid,
                                "sender_id": sender_id,
                                "sender_name": self.model.get_display_name(sender_id),
                                "sender_avatar": self.model.get_avatar(sender_id),
                                "message": msg,
                                "is_image": is_img,
                                "image_data": img_data
                            }

                            with self.lock:
                                for mid in members:
                                    if mid in self.user_sockets:
                                        self.send_to_client(self.user_sockets[mid], msg_data)
                            response = {"status": "success"}

                    elif action == "get_group_history":
                        response = {"status": "success",
                                    "history": self.model.get_group_chat_history(request.get("group_id"))}

                    # === SESSION ===
                    elif action == "resume_session":
                        uid = request.get("user_id")
                        if uid:
                            with self.lock:
                                self.clients[client_socket] = uid
                                self.user_sockets[uid] = client_socket
                            response = {"status": "success"}

                    # Gửi phản hồi (Chỉ gửi nếu response chưa được gửi qua broadcast logic ở trên)
                    # Một số action ở trên ta gán response = ... nên nó sẽ chạy xuống đây
                    self.send_to_client(client_socket, response)

                except json.JSONDecodeError:
                    self.send_to_client(client_socket, {"status": "error", "message": "JSON lỗi"})
                except socket.error:
                    break
                except Exception as e:
                    logger.error(f"Server Error: {e}")
                    break
        finally:
            with self.lock:
                if client_socket in self.clients:
                    uid = self.clients[client_socket]
                    del self.clients[client_socket]
                    if uid in self.user_sockets: del self.user_sockets[uid]
            client_socket.close()

    def start(self):
        print(f"Server started on port {SERVER_CONFIG['port']}")
        while True:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
            except:
                break