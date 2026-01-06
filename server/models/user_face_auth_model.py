# server/models/user_face_auth_model.py
"""
DB model access for FaceID table: chat_app.user_face_auth
Provides CRUD operations for face authentication records.
"""
import mysql.connector
from config.config import DATABASE_CONFIG
import logging

logger = logging.getLogger(__name__)


class UserFaceAuthModel:
    def __init__(self):
        try:
            self.connection = mysql.connector.connect(**DATABASE_CONFIG)
            self.cursor = self.connection.cursor()
            logger.info("UserFaceAuthModel: Database connection established")
        except mysql.connector.Error as err:
            logger.error(f"UserFaceAuthModel: Database connection failed: {err}")
            raise

    def upsert_face_auth(
        self,
        user_id: int,
        embedding_bytes: bytes,
        embedding_dim: int,
        model_name: str,
        threshold: float
    ) -> None:
        """
        Insert or update face authentication record for a user.
        If record exists for user_id => UPDATE, else INSERT.
        Sets is_enabled=1 and updated_at=NOW().
        For INSERT, also sets created_at=NOW().
        Uses INSERT ... ON DUPLICATE KEY UPDATE (requires UNIQUE(user_id) constraint).
        """
        try:
            query = """
                INSERT INTO user_face_auth 
                    (user_id, embedding, embedding_dim, model_name, threshold, is_enabled, created_at, updated_at)
                VALUES 
                    (%s, %s, %s, %s, %s, 1, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    embedding = VALUES(embedding),
                    embedding_dim = VALUES(embedding_dim),
                    model_name = VALUES(model_name),
                    threshold = VALUES(threshold),
                    is_enabled = 1,
                    updated_at = NOW()
            """
            self.cursor.execute(query, (user_id, embedding_bytes, embedding_dim, model_name, threshold))
            self.connection.commit()
            logger.info(f"Face auth upserted for user_id={user_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error upserting face auth for user_id={user_id}: {err}")
            raise

    def get_face_auth_by_user_id(self, user_id: int) -> dict | None:
        """
        Get face authentication record by user_id.
        Returns dict with all columns, or None if not found.
        """
        try:
            query = """
                SELECT id, user_id, embedding, embedding_dim, model_name, threshold, 
                       is_enabled, created_at, updated_at, last_used_at
                FROM user_face_auth
                WHERE user_id = %s
            """
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "user_id": result[1],
                    "embedding": result[2],
                    "embedding_dim": result[3],
                    "model_name": result[4],
                    "threshold": result[5],
                    "is_enabled": bool(result[6]),
                    "created_at": str(result[7]) if result[7] else None,
                    "updated_at": str(result[8]) if result[8] else None,
                    "last_used_at": str(result[9]) if result[9] else None,
                }
            return None
        except mysql.connector.Error as err:
            logger.error(f"Error getting face auth for user_id={user_id}: {err}")
            return None

    def get_active_face_auth_by_user_id(self, user_id: int) -> dict | None:
        """
        Get active (is_enabled=1) face authentication record by user_id.
        Returns dict with all columns, or None if not found or disabled.
        """
        try:
            query = """
                SELECT id, user_id, embedding, embedding_dim, model_name, threshold, 
                       is_enabled, created_at, updated_at, last_used_at
                FROM user_face_auth
                WHERE user_id = %s AND is_enabled = 1
            """
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "user_id": result[1],
                    "embedding": result[2],
                    "embedding_dim": result[3],
                    "model_name": result[4],
                    "threshold": result[5],
                    "is_enabled": bool(result[6]),
                    "created_at": str(result[7]) if result[7] else None,
                    "updated_at": str(result[8]) if result[8] else None,
                    "last_used_at": str(result[9]) if result[9] else None,
                }
            return None
        except mysql.connector.Error as err:
            logger.error(f"Error getting active face auth for user_id={user_id}: {err}")
            return None

    def disable_face_auth(self, user_id: int) -> None:
        """
        Disable face authentication for a user (set is_enabled=0, updated_at=NOW()).
        Safe/idempotent if record does not exist.
        """
        try:
            query = """
                UPDATE user_face_auth
                SET is_enabled = 0, updated_at = NOW()
                WHERE user_id = %s
            """
            self.cursor.execute(query, (user_id,))
            self.connection.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"Face auth disabled for user_id={user_id}")
            else:
                logger.debug(f"No face auth record found to disable for user_id={user_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error disabling face auth for user_id={user_id}: {err}")
            raise

    def touch_last_used(self, user_id: int) -> None:
        """
        Update last_used_at=NOW() for a user's face auth record.
        Safe/idempotent if record does not exist.
        """
        try:
            query = """
                UPDATE user_face_auth
                SET last_used_at = NOW()
                WHERE user_id = %s
            """
            self.cursor.execute(query, (user_id,))
            self.connection.commit()
            if self.cursor.rowcount > 0:
                logger.debug(f"Face auth last_used_at touched for user_id={user_id}")
            else:
                logger.debug(f"No face auth record found to touch for user_id={user_id}")
        except mysql.connector.Error as err:
            logger.error(f"Error touching last_used_at for user_id={user_id}: {err}")
            raise

    def __del__(self):
        try:
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
            logger.info("UserFaceAuthModel: Database connection closed")
        except Exception as e:
            logger.error(f"UserFaceAuthModel: Error closing database connection: {e}")
