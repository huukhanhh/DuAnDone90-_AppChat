import json
import socket
import struct
import threading
import logging
from config.config import SERVER_CONFIG

# Import Sub-Controllers
from server.models.user_model import UserModel
from server.controllers.auth_controller import AuthController
from server.controllers.user_controller import UserController
from server.controllers.chat_controller import ChatController
from server.controllers.group_controller import GroupController

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='server.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

class ServerController:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((SERVER_CONFIG["host"], SERVER_CONFIG["port"]))
        self.server_socket.listen(5)
        
        self.clients = {}      # socket -> user_id
        self.user_sockets = {} # user_id -> socket
        self.offline_messages = {}
        self.lock = threading.Lock()
        
        try:
            self.model = UserModel()
            logger.info("UserModel initialized successfully")
            
            # Initialize Sub-Controllers
            self.auth_ctrl = AuthController(self.model)
            self.user_ctrl = UserController(self.model)
            self.chat_ctrl = ChatController(self.model)
            self.group_ctrl = GroupController(self.model)
            
        except Exception as e:
            logger.error(f"Cannot initialize model/controllers: {str(e)}")
            raise

    def _send_all(self, sock, data):
        total_sent = 0
        while total_sent < len(data):
            sent = sock.send(data[total_sent:])
            if sent == 0: raise socket.error("Socket broken")
            total_sent += sent

    def _recv_all(self, sock, length):
        data = b''
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), 10485760))
            if not chunk: raise socket.error("Socket broken")
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
            logger.error(f"Error sending message: {str(e)}")
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

                    if data_length > 10 * 1024 * 1024:
                        logger.warning(f"Request too large: {data_length} bytes")
                        self.send_to_client(client_socket, {"status": "error", "message": "Data too large (max 10MB)"})
                        break

                    data = self._recv_all(client_socket, data_length)
                    message = data.decode('utf-8')
                    request = json.loads(message)
                    action = request.get("action")
                    
                    response = {"status": "error", "message": "Invalid Action"}

                    # === DISPATCHER ===
                    
                    # 1. AUTH
                    if action == "login":
                        response = self.auth_ctrl.handle_login(request.get("email"), request.get("password"))
                        if response.get("status") == "success":
                            user_id = response.get("user_id")
                            with self.lock:
                                self.clients[client_socket] = user_id
                                self.user_sockets[user_id] = client_socket
                            
                            # Send offline messages
                            if user_id in self.offline_messages:
                                for msg in self.offline_messages[user_id]:
                                    self.send_to_client(client_socket, msg)
                                del self.offline_messages[user_id]
                                
                    elif action == "register":
                        response = self.auth_ctrl.handle_register(request.get("display_name"), request.get("email"), request.get("password"))

                    elif action == "resume_session":
                        uid = request.get("user_id")
                        if uid:
                            with self.lock:
                                self.clients[client_socket] = uid
                                self.user_sockets[uid] = client_socket
                            response = {"status": "success"}

                    # 2. USER / PROFILE
                    elif action == "get_users":
                        response = self.user_ctrl.get_users()
                        
                    elif action == "get_profile":
                        uid = self.clients.get(client_socket)
                        if uid: response = self.user_ctrl.get_profile(uid)

                    elif action == "update_profile":
                        uid = self.clients.get(client_socket)
                        if uid:
                            response = self.user_ctrl.update_profile(uid, request.get("display_name"), request.get("avatar"), request.get("old_password"), request.get("new_password"))
                            if response["status"] == "success":
                                # Broadcast Update
                                new_profile = self.user_ctrl.get_profile(uid)
                                noti_data = {
                                    "action": "profile_update_notification",
                                    "user_id": uid,
                                    "display_name": new_profile.get("display_name")
                                }
                                with self.lock:
                                    for u_id, sock in list(self.user_sockets.items()):
                                        self.send_to_client(sock, noti_data)

                    # 3. CHAT 1-1
                    elif action == "get_chat_history":
                        uid = self.clients.get(client_socket)
                        if uid:
                            response = self.chat_ctrl.get_history(uid, request.get("receiver_id"))

                    elif action in ["message", "send_image", "send_voice", "send_video", "system_log"]:
                        if client_socket in self.clients:
                            sender_id = self.clients[client_socket]
                            res_data = self.chat_ctrl.handle_message(sender_id, request)
                            
                            if res_data:
                                # Prepare Packet
                                receiver_id = request.get("receiver_id")
                                msg_data = {
                                    "action": "message",
                                    "sender_id": sender_id,
                                    "sender_name": self.model.get_display_name(sender_id),
                                    "sender_avatar": self.model.get_avatar(sender_id),
                                    "receiver_id": receiver_id,
                                    "message": res_data.get("content"),
                                    "is_image": res_data.get("msg_type") == "image",
                                    "image_data": request.get("image_data") if res_data.get("msg_type") == "image" else None,
                                    "is_voice": res_data.get("msg_type") == "voice",
                                    "voice_data": request.get("voice_data") if res_data.get("msg_type") == "voice" else None,
                                    "is_video": res_data.get("msg_type") == "video",
                                    "video_data": request.get("video_data") if res_data.get("msg_type") == "video" else None,
                                    "is_call_log": res_data.get("is_call_log", False)
                                }
                                
                                with self.lock:
                                    if receiver_id in self.user_sockets:
                                        self.send_to_client(self.user_sockets[receiver_id], msg_data)
                                    else:
                                        if receiver_id not in self.offline_messages: self.offline_messages[receiver_id] = []
                                        self.offline_messages[receiver_id].append(msg_data)
                                
                                response = {"status": "success"}

                    # 4. GROUP CHAT
                    elif action == "create_group":
                        owner_id = self.clients.get(client_socket)
                        if owner_id:
                            response = self.group_ctrl.create_group(request.get("name"), owner_id, request.get("members"))
                            if response["status"] == "success":
                                # Notify Members
                                noti = {
                                    "action": "new_group",
                                    "group_id": response["group_id"],
                                    "name": request.get("name"),
                                    "owner_name": self.model.get_display_name(owner_id)
                                }
                                with self.lock:
                                    for mid in response["members"]:
                                        if mid != owner_id and mid in self.user_sockets:
                                            self.send_to_client(self.user_sockets[mid], noti)

                    elif action == "get_groups":
                        uid = self.clients.get(client_socket)
                        if uid: response = self.group_ctrl.get_groups(uid)

                    elif action == "group_message":
                        sender_id = self.clients.get(client_socket)
                        if sender_id:
                            res_data = self.group_ctrl.handle_group_message(sender_id, request)
                            gid = res_data["group_id"]
                            members = self.model.get_group_members(gid)
                            
                            msg_data = {
                                "action": "group_message",
                                "group_id": gid,
                                "sender_id": sender_id,
                                "sender_name": self.model.get_display_name(sender_id),
                                "sender_avatar": self.model.get_avatar(sender_id),
                                "message": request.get("message"),
                                "is_image": request.get("is_image", False),
                                "image_data": request.get("image_data")
                            }
                            
                            with self.lock:
                                for mid in members:
                                    if mid in self.user_sockets:
                                        self.send_to_client(self.user_sockets[mid], msg_data)
                            response = {"status": "success"}

                    elif action == "get_group_history":
                        response = self.group_ctrl.get_history(request.get("group_id"))

                    # 5. SIGNAL RELAY
                    elif action == "signal":
                        target_id = request.get("target_id")
                        if target_id:
                            signal_data = request.copy()
                            sender_id = self.clients.get(client_socket)
                            if sender_id: signal_data["sender_id"] = sender_id
                            
                            with self.lock:
                                if target_id in self.user_sockets:
                                    self.send_to_client(self.user_sockets[target_id], signal_data)
                                    response = {"status": "success"}
                                else:
                                    response = {"status": "error", "code": "USER_OFFLINE"}

                    # Respond
                    self.send_to_client(client_socket, response)

                except json.JSONDecodeError:
                    self.send_to_client(client_socket, {"status": "error", "message": "JSON Error"})
                except socket.error:
                    break
                except Exception as e:
                    logger.error(f"Server Loop Error: {e}")
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
