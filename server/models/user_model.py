# server/models/user_model.py
import mysql.connector
import bcrypt
from config.config import DATABASE_CONFIG
import logging

logger = logging.getLogger(__name__)


class UserModel:
    def __init__(self):
        try:
            self.connection = mysql.connector.connect(**DATABASE_CONFIG)
            self.cursor = self.connection.cursor()
            logger.info("Database connection established")
        except mysql.connector.Error as err:
            logger.error(f"Database connection failed: {err}")
            raise

    def get_user_id(self, email):
        try:
            query = "SELECT id FROM users WHERE email = %s"
            self.cursor.execute(query, (email,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except mysql.connector.Error as err:
            logger.error(f"Error getting user_id: {err}")
            return None

    def get_display_name(self, user_id):
        try:
            query = "SELECT display_name FROM users WHERE id = %s"
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else "Unknown"
        except mysql.connector.Error as err:
            logger.error(f"Error getting display_name: {err}")
            return "Unknown"

    def get_avatar(self, user_id):
        try:
            query = "SELECT avatar_data FROM users WHERE id = %s"
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result and result[0] else None
        except mysql.connector.Error as err:
            logger.error(f"Error getting avatar: {err}")
            return None

    def get_all_users(self):
        try:
            query = "SELECT id, display_name, avatar_data, last_active_at FROM users"
            self.cursor.execute(query)
            return [
                {
                    "user_id": row[0], 
                    "display_name": row[1], 
                    "avatar": row[2],
                    "last_active_at": str(row[3]) if row[3] else None
                }
                for row in self.cursor.fetchall()
            ]
        except mysql.connector.Error as err:
            logger.error(f"Error getting all users: {err}")
            return []

    def register_user(self, display_name, email, password):
        try:
            query = "SELECT email FROM users WHERE email = %s"
            self.cursor.execute(query, (email,))
            if self.cursor.fetchone():
                return {"status": "error", "message": "Email đã tồn tại"}

            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)

            query = "INSERT INTO users (display_name, email, password_hash) VALUES (%s, %s, %s)"
            self.cursor.execute(query, (display_name, email, password_hash.decode('utf-8')))
            self.connection.commit()

            logger.info(f"User registered: {email}")
            return {"status": "success", "message": "Đăng ký thành công"}
        except mysql.connector.Error as err:
            logger.error(f"Database error during registration: {err}")
            return {"status": "error", "message": f"Lỗi database: {err}"}
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
            return {"status": "error", "message": f"Lỗi: {str(e)}"}

    def login_user(self, email, password):
        try:
            query = "SELECT id, display_name, password_hash, avatar_data, is_invisible FROM users WHERE email = %s"
            self.cursor.execute(query, (email,))
            result = self.cursor.fetchone()

            if result:
                user_id, display_name, password_hash, avatar_data, is_invisible = result
                try:
                    if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                        logger.info(f"User logged in: {email}")
                        return {
                            "status": "success", 
                            "user_id": user_id, 
                            "display_name": display_name, 
                            "avatar": avatar_data,
                            "is_invisible": bool(is_invisible),
                            "last_active_at": None # Login implies active now
                        }
                    else:
                        return {"status": "error", "message": "Mật khẩu sai"}
                except ValueError as e:
                    logger.error(f"Password hash error: {e}")
                    return {"status": "error", "message": f"Lỗi mã hóa (Invalid salt): {str(e)}. Vui lòng đăng ký lại."}
            else:
                return {"status": "error", "message": "Tài khoản không tồn tại"}
        except mysql.connector.Error as err:
            logger.error(f"Database error during login: {err}")
            return {"status": "error", "message": f"Lỗi database: {err}"}

    def save_message(self, sender_id, receiver_id, message, is_call_log=False):
        try:
            query = "INSERT INTO chat_messages (sender_id, receiver_id, message, is_image, is_call_log) VALUES (%s, %s, %s, %s, %s)"
            self.cursor.execute(query, (sender_id, receiver_id, message, False, is_call_log))
            self.connection.commit()
            logger.debug(f"Message saved: {sender_id} -> {receiver_id} (CallLog: {is_call_log})")
        except mysql.connector.Error as err:
            logger.error(f"Error saving message: {err}")

    def save_image_message(self, sender_id, receiver_id, image_data, filename):
        """Lưu tin nhắn ảnh vào database"""
        try:
            query = """
                    INSERT INTO chat_messages (sender_id, receiver_id, message, is_image, image_data)
                    VALUES (%s, %s, %s, %s, %s) \
                    """
            self.cursor.execute(query, (sender_id, receiver_id, filename, True, image_data))
            self.connection.commit()
            logger.debug(f"Image message saved: {sender_id} -> {receiver_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error saving image message: {err}")

    def save_voice_message(self, sender_id, receiver_id, voice_data, filename):
        """Lưu tin nhắn voice vào database"""
        try:
            query = """
                    INSERT INTO chat_messages (sender_id, receiver_id, message, is_voice, voice_data)
                    VALUES (%s, %s, %s, %s, %s)
                    """
            self.cursor.execute(query, (sender_id, receiver_id, filename, True, voice_data))
            self.connection.commit()
            logger.debug(f"Voice message saved: {sender_id} -> {receiver_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error saving voice message: {err}")

    def save_video_message(self, sender_id, receiver_id, video_data, filename):
        """Lưu tin nhắn video vào database"""
        try:
            query = """
                    INSERT INTO chat_messages (sender_id, receiver_id, message, is_video, video_data)
                    VALUES (%s, %s, %s, %s, %s)
                    """
            self.cursor.execute(query, (sender_id, receiver_id, filename, True, video_data))
            self.connection.commit()
            logger.debug(f"Video message saved: {sender_id} -> {receiver_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error saving video message: {err}")

    def save_file_message(self, sender_id, receiver_id, file_data, filename, file_size):
        """Lưu tin nhắn file vào database"""
        try:
            query = """
                    INSERT INTO chat_messages (sender_id, receiver_id, message, is_file, file_data, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
            self.cursor.execute(query, (sender_id, receiver_id, filename, True, file_data, file_size))
            self.connection.commit()
            logger.debug(f"File message saved: {sender_id} -> {receiver_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error saving file message: {err}")


    def get_chat_history(self, sender_id, receiver_id):
        try:
            query = """
                    SELECT sender_id, message, timestamp, is_image, image_data, is_voice, voice_data, 
                           is_video, video_data, is_call_log, is_file, file_data, file_size
                    FROM chat_messages
                    WHERE (sender_id = %s AND receiver_id = %s)
                       OR (sender_id = %s AND receiver_id = %s)
                    ORDER BY timestamp ASC
                    """
            self.cursor.execute(query, (sender_id, receiver_id, receiver_id, sender_id))

            history = []
            for row in self.cursor.fetchall():
                msg = {
                    "sender_id": row[0],
                    "sender_name": self.get_display_name(row[0]),
                    "sender_avatar": self.get_avatar(row[0]),
                    "timestamp": str(row[2]),
                    "is_image": bool(row[3]) if row[3] is not None else False,
                    "is_voice": bool(row[5]) if row[5] is not None else False,
                    "is_video": bool(row[7]) if len(row) > 7 and row[7] is not None else False,
                    "is_call_log": bool(row[9]) if len(row) > 9 and row[9] is not None else False,
                    "is_file": bool(row[10]) if len(row) > 10 and row[10] is not None else False
                }

                if msg["is_image"]:
                    msg["image_data"] = row[4]
                    msg["message"] = row[1]  # filename
                elif msg["is_voice"]:
                    msg["voice_data"] = row[6]
                    msg["message"] = row[1]  # filename
                elif msg["is_video"]:
                    msg["video_data"] = row[8] if len(row) > 8 else None
                    msg["message"] = row[1]  # filename
                elif msg["is_file"]:
                    msg["file_data"] = row[11] if len(row) > 11 else None
                    msg["file_size"] = row[12] if len(row) > 12 else 0
                    msg["message"] = row[1]  # filename
                else:
                    msg["message"] = row[1]

                history.append(msg)

            return history
        except mysql.connector.Error as err:
            logger.error(f"Error getting chat history: {err}")
            return []

    def get_recent_chats(self, user_id):
        try:
            query = """
                    SELECT DISTINCT u2.id as user_id, u2.display_name, u2.avatar_data, m.message as last_message
                    FROM users u2
                             LEFT JOIN chat_messages m ON (m.sender_id = u2.id AND m.receiver_id = %s)
                        OR (m.sender_id = %s AND m.receiver_id = u2.id)
                    WHERE u2.id != %s
                    ORDER BY m.timestamp DESC
                        LIMIT 10 \
                    """
            self.cursor.execute(query, (user_id, user_id, user_id))
            return [
                {
                    "user_id": row[0],
                    "display_name": row[1],
                    "avatar": row[2],
                    "last_message": row[3] if row[3] else "Chưa có tin nhắn"
                }
                for row in self.cursor.fetchall()
            ]
        except mysql.connector.Error as err:
            logger.error(f"Error getting recent chats: {err}")
            return []

    def get_profile(self, user_id):
        try:
            query = "SELECT display_name, email, avatar_data, is_invisible, last_active_at FROM users WHERE id = %s"
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            if not result:
                return {"status": "error", "message": "Không tìm thấy người dùng"}
            return {
                "status": "success",
                "display_name": result[0],
                "email": result[1],
                "avatar": result[2],
                "is_invisible": bool(result[3]),
                "last_active_at": str(result[4]) if len(result) > 4 and result[4] else None
            }
        except mysql.connector.Error as err:
            logger.error(f"Error getting profile: {err}")
            return {"status": "error", "message": f"Lỗi database: {err}"}


    def update_profile(self, user_id, display_name=None, avatar_data=None, is_invisible=None):
        try:
            updates = []
            params = []
            if display_name:
                updates.append("display_name = %s")
                params.append(display_name)
            if avatar_data:
                updates.append("avatar_data = %s")
                params.append(avatar_data)
            if is_invisible is not None:
                updates.append("is_invisible = %s")
                params.append(1 if is_invisible else 0)

            if not updates:
                return {"status": "success", "message": "Không có gì thay đổi"}

            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            params.append(user_id)
            self.cursor.execute(query, tuple(params))
            self.connection.commit()
            
            # Return updated info including is_invisible
            return {"status": "success", "is_invisible": is_invisible}
        except mysql.connector.Error as err:
            logger.error(f"Error updating profile: {err}")
            return {"status": "error", "message": "Lỗi cập nhật thông tin"}

    def change_password(self, user_id, old_password, new_password):
        try:
            # Lấy hash hiện tại
            self.cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
            row = self.cursor.fetchone()
            if not row:
                return {"status": "error", "message": "Không tìm thấy người dùng"}
            current_hash = row[0]
            if not bcrypt.checkpw(old_password.encode('utf-8'), current_hash.encode('utf-8')):
                return {"status": "error", "message": "Mật khẩu hiện tại không đúng"}

            new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            self.cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
            self.connection.commit()
            return {"status": "success", "message": "Đổi mật khẩu thành công"}
        except mysql.connector.Error as err:
            logger.error(f"Error changing password: {err}")
            return {"status": "error", "message": f"Lỗi database: {err}"}

    def __del__(self):
        try:
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

    def create_group(self, name, owner_id, member_ids):
        try:
            # Tạo nhóm
            self.cursor.execute("INSERT INTO `groups` (name, owner_id) VALUES (%s, %s)", (name, owner_id))
            group_id = self.cursor.lastrowid

            # Thêm thành viên (bao gồm cả owner)
            all_members = set(member_ids)
            all_members.add(owner_id)
            values = [(group_id, uid) for uid in all_members]
            self.cursor.executemany("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", values)

            # Tin nhắn hệ thống báo tạo nhóm
            creator_name = self.get_display_name(owner_id)
            self.save_group_message(group_id, None, f"Nhóm '{name}' đã được tạo bởi {creator_name}", is_system=True)

            self.connection.commit()
            return {"status": "success", "group_id": group_id, "members": list(all_members)}
        except Exception as e:
            self.connection.rollback()
            return {"status": "error", "message": str(e)}

    def add_group_member(self, group_id, user_id, added_by_name):
        try:
            # Kiểm tra tồn tại
            self.cursor.execute("SELECT 1 FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, user_id))
            if self.cursor.fetchone():
                return {"status": "error", "message": "Thành viên đã tồn tại"}
            
            self.cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", (group_id, user_id))
            
            # Tin nhắn hệ thống
            user_name = self.get_display_name(user_id)
            self.save_group_message(group_id, None, f"{added_by_name} đã thêm {user_name} vào nhóm", is_system=True)
            self.connection.commit()
            return {"status": "success"}
        except Exception as e:
             return {"status": "error", "message": str(e)}

    def remove_group_member(self, group_id, user_id, user_name):
        try:
            self.cursor.execute("DELETE FROM group_members WHERE group_id=%s AND user_id=%s", (group_id, user_id))
            
            # Tin nhắn hệ thống
            self.save_group_message(group_id, None, f"{user_name} đã rời nhóm", is_system=True)
            
            # Kiểm tra số lượng còn lại
            self.cursor.execute("SELECT COUNT(*) FROM group_members WHERE group_id=%s", (group_id,))
            count = self.cursor.fetchone()[0]
            
            if count == 0:
                self.delete_group(group_id)
                return {"status": "success", "remaining_members": 0}
            
            self.connection.commit()
            return {"status": "success", "remaining_members": count}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_group(self, group_id):
        try:
            self.cursor.execute("DELETE FROM group_messages WHERE group_id=%s", (group_id,))
            self.cursor.execute("DELETE FROM group_members WHERE group_id=%s", (group_id,))
            self.cursor.execute("DELETE FROM `groups` WHERE id=%s", (group_id,))
            self.connection.commit()
        except Exception as e:
            print(f"Error delete group: {e}")

    def get_user_groups(self, user_id):
        try:
            query = """
                SELECT g.id, g.name, g.avatar_data 
                FROM `groups` g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = %s
            """
            self.cursor.execute(query, (user_id,))
            groups = []
            for row in self.cursor.fetchall():
                groups.append({"id": row[0], "name": row[1], "avatar": row[2]})
            return groups
        except Exception:
            return []

    def get_group_members(self, group_id):
        self.cursor.execute("SELECT user_id FROM group_members WHERE group_id = %s", (group_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def save_group_message(self, group_id, sender_id, message, is_image=False, image_data=None, is_system=False, is_voice=False, voice_data=None):
        try:
            query = """INSERT INTO group_messages (group_id, sender_id, message, is_image, image_data, is_system, is_voice, voice_data) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            self.cursor.execute(query, (group_id, sender_id, message, is_image, image_data, is_system, is_voice, voice_data))
            self.connection.commit()
        except Exception as e:
            print(f"Error saving group msg: {e}")

    def get_group_chat_history(self, group_id):
        try:
            query = """
                SELECT gm.sender_id, u.display_name, u.avatar_data, gm.message, 
                       gm.is_image, gm.image_data, gm.is_system, gm.is_voice, gm.voice_data
                FROM group_messages gm
                LEFT JOIN users u ON gm.sender_id = u.id
                WHERE gm.group_id = %s ORDER BY gm.timestamp ASC
            """
            self.cursor.execute(query, (group_id,))
            history = []
            for row in self.cursor.fetchall():
                history.append({
                    "sender_id": row[0], "sender_name": row[1], "sender_avatar": row[2],
                    "message": row[3], "is_image": bool(row[4]), "image_data": row[5], 
                    "is_system": bool(row[6]), "is_voice": bool(row[7]) if len(row) > 7 else False,
                    "voice_data": row[8] if len(row) > 8 else None
                })
            return history
        except Exception:
            return []

    def update_last_active(self, user_id):
        try:
            from datetime import datetime
            now = datetime.now()
            query = "UPDATE users SET last_active_at = %s WHERE id = %s"
            self.cursor.execute(query, (now, user_id))
            self.connection.commit()
            return str(now)
        except Exception as e:
            logger.error(f"Error updating last active: {e}")
            return None