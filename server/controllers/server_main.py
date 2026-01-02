import json
import socket
import struct
import threading
import logging
from config.config import SERVER_CONFIG, BADWORDS_PATH

# Import Các Sub-Controller
from server.models.user_model import UserModel
from server.controllers.auth_controller import AuthController
from server.controllers.user_controller import UserController
from server.controllers.chat_controller import ChatController
from server.controllers.group_controller import GroupController
from server.controllers.moderation_controller import ServerModerationController

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
        self.server_socket.bind(("0.0.0.0", SERVER_CONFIG["port"]))
        self.server_socket.listen(5)
        
        self.clients = {}      # socket -> user_id
        self.user_sockets = {} # user_id -> socket
        self.user_visibility = {} # user_id -> bool (Is Visible?)
        self.offline_messages = {}
        self.lock = threading.Lock()
        
        try:
            self.model = UserModel()
            logger.info("UserModel initialized successfully")
            
            # Khởi tạo các Sub-Controller
            self.auth_ctrl = AuthController(self.model)
            self.user_ctrl = UserController(self.model)
            self.chat_ctrl = ChatController(self.model)
            self.group_ctrl = GroupController(self.model)
            
            # Khởi tạo Moderation Controller
            self.mod_ctrl = ServerModerationController(BADWORDS_PATH)
            logger.info("Moderation controller initialized")
            
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
        logger.info("Phiên client mới bắt đầu")

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

                    # === BỘ ĐIỀU PHỐI (DISPATCHER) ===
                    
                    # 1. AUTH
                    if action == "login":
                        response = self.auth_ctrl.handle_login(request.get("email"), request.get("password"))
                        if response.get("status") == "success":
                            user_id = int(response.get("user_id")) # Ensure int
                            is_invisible = response.get("is_invisible", False)
                            
                            old_socket_to_close = None  # Store old socket to close OUTSIDE lock
                            
                            # === ATOMIC OPERATION: Kick old + Register new in ONE lock ===
                            with self.lock:
                                # Step 1: Check and prepare to kick old session
                                if user_id in self.user_sockets:
                                    old_socket = self.user_sockets[user_id]
                                    
                                    # Send force_logout to old session
                                    try:
                                        force_logout_packet = {
                                            "action": "force_logout",
                                            "message": "Tài khoản đã đăng nhập từ thiết bị khác."
                                        }
                                        self.send_to_client(old_socket, force_logout_packet)
                                        print(f"[DEBUG] Sent force_logout packet to old socket for user {user_id}")
                                        logger.info(f"Sent force_logout to old session of user {user_id}")
                                    except Exception as e:
                                        logger.warning(f"Could not send force_logout: {e}")
                                    
                                    # Remove old session from all tracking IMMEDIATELY
                                    if old_socket in self.clients:
                                        del self.clients[old_socket]
                                    # Note: user_sockets[user_id] will be overwritten below
                                    # Note: user_visibility[user_id] will be overwritten below
                                    
                                    old_socket_to_close = old_socket
                                    logger.info(f"Kicked old session of user {user_id}")
                                
                                # Step 2: Register new session (STILL IN SAME LOCK)
                                self.clients[client_socket] = user_id
                                self.user_sockets[user_id] = client_socket
                                self.user_visibility[user_id] = False if is_invisible else True
                                self.model.update_last_active(user_id)
                            # === END ATOMIC OPERATION ===
                            
                            # Close old socket OUTSIDE lock (to avoid blocking)
                            if old_socket_to_close:
                                try:
                                    old_socket_to_close.shutdown(socket.SHUT_RDWR)
                                except:
                                    pass
                                try:
                                    old_socket_to_close.close()
                                except:
                                    pass
                            
                            print(f"[DEBUG login] Registered user_id={user_id} (type={type(user_id)}). user_sockets={list(self.user_sockets.keys())}")
                            
                            # Gửi tin nhắn offline
                            if user_id in self.offline_messages:
                                for msg in self.offline_messages[user_id]:
                                    self.send_to_client(client_socket, msg)
                                del self.offline_messages[user_id]

                            # Broadcast USER_ONLINE nếu user KHÔNG ẩn danh
                            if self.user_visibility[user_id]:
                                self.broadcast_user_status(user_id, "online")
                                
                    elif action == "register":
                        response = self.auth_ctrl.handle_register(request.get("display_name"), request.get("email"), request.get("password"))

                    elif action == "resume_session":
                        uid = request.get("user_id")
                        if uid:
                            try:
                                uid = int(uid) # Ensure int
                                with self.lock:
                                    # === SINGLE SESSION ENFORCEMENT ===
                                    # Reject resume if another session is active
                                    if uid in self.user_sockets and self.user_sockets[uid] != client_socket:
                                        logger.warning(f"Resume session rejected for User {uid} - another session is active")
                                        response = {"status": "error", "message": "Session đã bị thay thế bởi đăng nhập khác"}
                                    else:
                                        self.clients[client_socket] = uid
                                        self.user_sockets[uid] = client_socket
                                        logger.info(f"Resume session success for User {uid}. Sockets: {list(self.user_sockets.keys())}")
                                        response = {"status": "success"}
                                        
                                        # Broadcast online status on resume if visible
                                        is_visible = self.user_visibility.get(uid, True)
                                        if is_visible:
                                             self.broadcast_user_status(uid, "online")
                            except ValueError:
                                response = {"status": "error", "message": "Invalid User ID"}
                            
                        else:
                            response = {"status": "error", "message": "Missing User ID"}
                        
                        self.send_to_client(client_socket, response)

                    # 2. USER / PROFILE
                    elif action == "get_users":
                        uid = self.clients.get(client_socket)
                        self.handle_get_users(client_socket, uid)
                        continue  # handle_get_users sends the response itself
                        
                    elif action == "get_profile":
                        uid = self.clients.get(client_socket)
                        if uid: response = self.user_ctrl.get_profile(uid)

                    elif action == "update_profile":
                        uid = self.clients.get(client_socket)
                        if uid:
                            # 1. Get current state to compare
                            # old_profile_data = self.user_ctrl.get_profile(uid) # Optional optimization
                            
                            is_invisible_req = request.get("is_invisible")
                            
                            # 2. Call controller to update DB
                            response = self.user_ctrl.update_profile(
                                uid, 
                                request.get("display_name"), 
                                request.get("avatar"), 
                                request.get("old_password"), 
                                request.get("new_password"),
                                is_invisible_req
                            )
                            
                            if response["status"] == "success":
                                is_invisible_db = response.get("is_invisible") # Assuming controller/model *could* return this, but currently it returns generic success msg. 
                                # We rely on the request or re-fetching profile.
                                
                                # Update RAM Visibility if changed
                                if is_invisible_req is not None:
                                    # Convert to bool to be safe
                                    new_is_invisible = bool(is_invisible_req)
                                    with self.lock:
                                        # Currently, if invisible is True -> visibility is False
                                        old_visibility = self.user_visibility.get(uid, True)
                                        current_visibility = not new_is_invisible
                                        self.user_visibility[uid] = current_visibility
                                        
                                        # Compare and Broadcast Status Change
                                        if old_visibility != current_visibility:
                                            if current_visibility: # Invisible -> Visible
                                                self.broadcast_user_status(uid, "online")
                                            else: # Visible -> Invisible (Offline)
                                                # Update last active time for fake offline
                                                ts = self.model.update_last_active(uid)
                                                self.broadcast_user_status(uid, "offline", str(ts) if ts else None)

                                # Broadcast Profile Update (Display Name / Avatar)
                                # We re-fetch profile to get the latest DB state
                                new_profile = self.user_ctrl.get_profile(uid)
                                noti_data = {
                                    "action": "profile_update_notification",
                                    "user_id": uid,
                                    "display_name": new_profile.get("display_name")
                                    # We could include avatar hash here too if needed
                                }
                                self.broadcast_to_all(noti_data) # Use helper if available, else loop
                                
                            self.send_to_client(client_socket, response)

                    # 3. CHAT 1-1
                    elif action == "get_chat_history":
                        uid = self.clients.get(client_socket)
                        if uid:
                            response = self.chat_ctrl.get_history(uid, request.get("receiver_id"))

                    elif action in ["message", "send_image", "send_voice", "send_video", "system_log", "send_file"]:
                        if client_socket in self.clients:
                            sender_id = self.clients[client_socket]
                            
                            # === MODERATION CHECK (Text Message) ===
                            if action == "message":
                                mod_result = self.mod_ctrl.check_incoming_text(request)
                                
                                if mod_result["action"] == "BLOCK":
                                    # Vi phạm nặng (profanity) -> Không broadcast, return lỗi
                                    logger.warning(f"Message BLOCKED from user {sender_id}: {mod_result['hits']}")
                                    response = {"status": "error", "code": "MESSAGE_BLOCKED"}
                                    self.send_to_client(client_socket, response)
                                    continue  # Không xử lý tiếp
                                
                                elif mod_result["action"] == "WARN":
                                    # Vi phạm nhẹ -> Che từ xấu, vẫn broadcast
                                    censored_text = mod_result.get("final_text", request.get("message", ""))
                                    request["message"] = censored_text
                                    logger.info(f"Message CENSORED from user {sender_id}: {mod_result['hits']}")
                            # === END MODERATION CHECK ===
                            
                            res_data = self.chat_ctrl.handle_message(sender_id, request)
                            
                            if res_data:
                                # Chuẩn bị gói tin (Packet)
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
                                    "is_call_log": res_data.get("is_call_log", False),
                                    "is_file": res_data.get("is_file", False),
                                    "file_data": res_data.get("file_data"),
                                    "file_size": res_data.get("file_size", 0)
                                }
                                
                                receiver_socket = None
                                with self.lock:
                                    if receiver_id in self.user_sockets:
                                        receiver_socket = self.user_sockets[receiver_id]

                                if receiver_socket:
                                    if msg_data.get("is_file"):
                                         # Run in thread to prevent blocking the entire server or sender loop
                                         threading.Thread(
                                             target=self.send_to_client, 
                                             args=(receiver_socket, msg_data),
                                             daemon=True
                                         ).start()
                                    else:
                                         self.send_to_client(receiver_socket, msg_data)
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
                                # Thông báo cho các thành viên
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
                            # === MODERATION CHECK (Group Message) ===
                            if not request.get("is_image", False):  # Chỉ check text, không check ảnh
                                mod_result = self.mod_ctrl.check_incoming_text(request)
                                
                                if mod_result["action"] == "BLOCK":
                                    # Vi phạm nặng -> Không broadcast
                                    logger.warning(f"Group message BLOCKED from user {sender_id}: {mod_result['hits']}")
                                    response = {"status": "error", "code": "MESSAGE_BLOCKED"}
                                    self.send_to_client(client_socket, response)
                                    continue
                                
                                elif mod_result["action"] == "WARN":
                                    # Vi phạm nhẹ -> Che từ xấu
                                    censored_text = mod_result.get("final_text", request.get("message", ""))
                                    request["message"] = censored_text
                                    logger.info(f"Group message CENSORED from user {sender_id}: {mod_result['hits']}")
                            # === END MODERATION CHECK ===
                            
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

                    elif action == "add_group_member":
                        sender_id = self.clients.get(client_socket)
                        if sender_id:
                            adder_name = self.model.get_display_name(sender_id)
                            res = self.group_ctrl.add_member(request.get("group_id"), sender_id, request.get("user_ids"), adder_name)
                            if res["status"] == "success":
                                # Thông báo cho thành viên MỚI
                                for new_uid in res["added_members"]:
                                    if new_uid in self.user_sockets:
                                        self.send_to_client(self.user_sockets[new_uid], {"action": "new_group"}) # Trigger reload groups
                                
                                # Thông báo cho TẤT CẢ thành viên (tin nhắn hệ thống)
                                gid = request.get("group_id")
                                members = self.model.get_group_members(gid)
                                msg_data = {
                                    "action": "group_message",
                                    "group_id": gid,
                                    "sender_id": None, # System
                                    "sender_name": "System", 
                                    "message": f"{adder_name} đã thêm thành viên mới", # Simplified, real msg in history
                                    "is_system": True
                                }
                                # Retrieve real last system msg? No, just signal to reload or show ephemeral?
                                # Ideally, we should broadcast the actual system message content that was saved.
                                # But let's just trigger "group_message" which client will handle.
                                # Wait, client handles "group_message" by appending.
                                # We need to send the exact text used in DB.
                                # In `add_member`, model saved specific text.
                                # For simplicity, client can just reload history OR we send a generic notification.
                                # Hãy gửi một gói tin nhắn hệ thống cụ thể.
                                
                                # Better approach: Trigger reload or send synthesized msg.
                                # Let's fetch the latest msg from history? overhead.
                                # We can just construct it here: 
                                # "A added B". Code below constructs it for real-time display.
                                
                                # User Model already saved: "{added_by_name} đã thêm {user_name} vào nhóm"
                                # We can iterate added_members and send one msg per user.
                                for new_uid in res["added_members"]:
                                    u_name = self.model.get_display_name(new_uid)
                                    sys_msg = f"{adder_name} đã thêm {u_name} vào nhóm"
                                    
                                    pkt = {
                                        "action": "group_message",
                                        "group_id": gid,
                                        "sender_id": None,
                                        "sender_name": "System",
                                        "message": sys_msg,
                                        "is_system": True
                                    }
                                    with self.lock:
                                        for m in members:
                                            if m in self.user_sockets:
                                                self.send_to_client(self.user_sockets[m], pkt)

                                response = {"status": "success"}

                    elif action == "leave_group":
                        sender_id = self.clients.get(client_socket)
                        if sender_id:
                            u_name = self.model.get_display_name(sender_id)
                            gid = request.get("group_id")
                            
                            # Lấy danh sách thành viên TRƯỚC KHI xóa (để thông báo cho họ)
                            # Actually we need members AFTER removing (to notify remaining)
                            # But if we remove first, we can't query group members easily if table deleted? 
                            # Wait, `remove_group_member` returns remaining count.
                            # If count > 0, we can still query members.
                            
                            old_members = self.model.get_group_members(gid)
                            
                            res = self.group_ctrl.leave_group(gid, sender_id, u_name)
                            
                            if res["status"] == "success":
                                # Thông báo cho các thành viên còn lại
                                if res.get("remaining_members", 0) > 0:
                                    # Lấy danh sách thành viên hiện tại
                                    current_members = self.model.get_group_members(gid)
                                    sys_msg = f"{u_name} đã rời nhóm"
                                    
                                    pkt = {
                                        "action": "group_message",
                                        "group_id": gid,
                                        "sender_id": None,
                                        "sender_name": "System",
                                        "message": sys_msg,
                                        "is_system": True
                                    }
                                    
                                    with self.lock:
                                        for m in current_members:
                                            if m in self.user_sockets:
                                                self.send_to_client(self.user_sockets[m], pkt)
                                
                                response = {"status": "success"}

                    elif action == "get_group_members":
                         response = self.group_ctrl.get_members(request.get("group_id"))

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
                    print(f"[DEBUG response] Sending response to client: action={action}, status={response.get('status') if response else 'None'}")
                    self.send_to_client(client_socket, response)

                except json.JSONDecodeError:
                    self.send_to_client(client_socket, {"status": "error", "message": "JSON Error"})
                except socket.error:
                    break
                except Exception as e:
                    logger.error(f"Server Loop Error: {e}")
                    break
        finally:
            uid = None
            is_visible = False
            is_active_socket = False  # Flag: Is this socket still the active one for this user?
            
            # Step 1: Get user info and check if this socket is still active
            with self.lock:
                if client_socket in self.clients:
                    uid = self.clients[client_socket]
                    is_visible = self.user_visibility.get(uid, True)
                    # Check if this socket is still the active socket for this user
                    # If not, it means user logged in elsewhere and this is the kicked session
                    is_active_socket = (uid in self.user_sockets and self.user_sockets[uid] == client_socket)
            
            # Step 2: Only broadcast offline if THIS socket is still the active one
            # (Don't broadcast if this is a kicked session - user is still online on new device)
            if uid and is_active_socket:
                last_active = self.model.update_last_active(uid)
                last_active_str = str(last_active) if last_active else None
                
                if is_visible:
                    self.broadcast_user_status(uid, "offline", last_active_str)
                
                logger.info(f"User {uid} disconnected - broadcast sent")
            elif uid and not is_active_socket:
                logger.info(f"User {uid} kicked (logged in elsewhere) - no offline broadcast")
            
            # Step 3: Cleanup - only remove from tracking if this is still the active socket
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
                # Only delete user_sockets and visibility if this is still the active socket
                if uid and is_active_socket:
                    if uid in self.user_sockets:
                        del self.user_sockets[uid]
                    if uid in self.user_visibility:
                        del self.user_visibility[uid]
            
            try:
                client_socket.close()
            except:
                pass

    def handle_get_users(self, client_socket, uid):
        users = self.model.get_all_users()
        
        # DEBUG: Print socket keys
        print(f"[DEBUG handle_get_users] user_sockets keys: {list(self.user_sockets.keys())}")
        
        for user in users:
            raw_user_id = user["user_id"]
            user_id = int(raw_user_id) # Ensure int for validation
            
            is_connected = user_id in self.user_sockets
            is_visible_ram = self.user_visibility.get(user_id, True)
            
            # DEBUG PRINT
            print(f"[DEBUG] User {user_id}: connected={is_connected}, visible={is_visible_ram}")

            if is_connected and is_visible_ram:
                user["status"] = "online"
            else:
                user["status"] = "offline"
                
        self.send_to_client(client_socket, {"status": "success", "users": users})

    def broadcast_user_status(self, user_id, status, last_active_at=None):
        """Broadcast user status update to all clients except the user themselves."""
        notification = {
            "action": "user_status_update",
            "user_id": user_id,
            "status": status,
            "last_active_at": last_active_at
        }
        with self.lock:
            for uid, sock in self.user_sockets.items():
                # Do not send to the user whose status is being updated if they are the one disconnecting
                # or if the client should handle its own status update.
                # The original code had `if uid != user_id:`, let's keep that logic.
                if uid != user_id:
                    self.send_to_client(sock, notification)

    def start(self):
        print(f"Server started on port {SERVER_CONFIG['port']}")
        while True:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
            except Exception as e:
                logger.error(f"Server accept error: {e}")
                break
