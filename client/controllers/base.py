import socket
import json
import threading
import time
import struct
from queue import Queue
from config.config import SERVER_CONFIG

class BaseController:
    def __init__(self, socket, host=SERVER_CONFIG["host"], port=SERVER_CONFIG["port"]):
        self.host = host
        self.port = port
        self.client_socket = socket
        self.current_user_id = None
        self.reconnect_attempts = 3
        self.message_queue = Queue()
        self.response_queue = Queue()
        self.running = True

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
            chunk = sock.recv(min(length - len(data), 10485760))
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
                    push_actions = ["message", "group_message", "new_group", "profile_update_notification", "signal"]

                    if action in push_actions:
                        self.message_queue.put(response)
                    else:
                        self.response_queue.put(response)
            except (socket.error, json.JSONDecodeError):
                if not self.reconnect(): break
                time.sleep(1)
            except Exception as e:
                print(f"Receive error: {e}")
                break

    def reconnect(self):
        print("Reconnecting...")
        try: self.client_socket.close()
        except: pass

        for _ in range(self.reconnect_attempts):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.host, self.port))
                if self.current_user_id:
                    req = {"action": "resume_session", "user_id": self.current_user_id}
                    d = json.dumps(req).encode('utf-8')
                    l = struct.pack('>I', len(d))
                    self.client_socket.send(l + d)
                print("Reconnected!")
                return True
            except: time.sleep(2)
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
            
    def stop(self):
        self.running = False
        try: self.client_socket.close()
        except: pass
