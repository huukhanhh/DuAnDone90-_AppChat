# client/face/face_embedding_provider.py
"""
Provider trích xuất embedding khuôn mặt với lazy-loading dependencies.
Module này cung cấp chức năng phát hiện khuôn mặt và trích xuất vector đặc trưng (embedding)
sử dụng thư viện DeepFace.

Nếu thiếu dependencies, ứng dụng vẫn chạy được - chỉ FaceEnrollDialog sẽ hiển thị 
thông báo lỗi thân thiện.

Dependencies cần thiết:
    - opencv-python: Xử lý hình ảnh và camera
    - deepface: Thư viện nhận diện khuôn mặt
    - tensorflow (hoặc tf-keras): Backend cho deepface
    - numpy: Xử lý mảng số
"""

from typing import Optional, List, TYPE_CHECKING

# Tham chiếu đến các module được load lazy (chỉ import khi cần)
_cv2 = None
_np = None
_deepface = None
_import_errors: List[str] = []  # Danh sách các package bị thiếu
_import_attempted = False  # Đã thử import chưa

# Mapping tên module -> tên package trên pip
_REQUIRED_PACKAGES = {
    "cv2": "opencv-python",
    "numpy": "numpy",
    "deepface": "deepface",
}


def _lazy_import():
    """
    Thử import tất cả dependencies cần thiết.
    Các package bị thiếu sẽ được lưu vào _import_errors.
    Hàm này chỉ chạy một lần (singleton pattern).
    """
    global _cv2, _np, _deepface, _import_errors, _import_attempted
    
    if _import_attempted:  # Đã thử rồi, không cần thử lại
        return
    
    _import_attempted = True
    _import_errors = []
    
    # Thử import numpy
    try:
        import numpy as np
        _np = np
    except ImportError:
        _import_errors.append("numpy")
    
    # Thử import opencv
    try:
        import cv2
        _cv2 = cv2
    except ImportError:
        _import_errors.append("opencv-python")
    
    # Thử import deepface
    try:
        from deepface import DeepFace
        _deepface = DeepFace
    except ImportError:
        _import_errors.append("deepface")


class FaceEmbeddingProvider:
    """
    Cung cấp chức năng phát hiện khuôn mặt và trích xuất embedding 
    sử dụng thư viện DeepFace.
    
    DeepFace hỗ trợ nhiều model:
    - VGG-Face (mặc định)
    - Facenet / Facenet512
    - ArcFace
    - Dlib
    - SFace
    - v.v.
    
    Cách sử dụng:
        provider = FaceEmbeddingProvider()
        
        # Kiểm tra dependencies
        if not provider.is_available():
            print(f"Thiếu: {provider.get_missing_deps()}")
            return
        
        # Khởi tạo model
        provider.initialize()
        
        # Trích xuất embedding từ frame
        embedding = provider.get_embedding_from_frame(frame)
    """
    
    # Sử dụng Facenet512 cho cân bằng giữa độ chính xác và tốc độ
    # Tạo ra vector embedding 512 chiều
    MODEL_NAME = "Facenet512"
    EMBEDDING_DIM = 512
    DEFAULT_THRESHOLD = 0.70  # Ngưỡng similarity để xác định khớp khuôn mặt
    
    def __init__(self):
        """Khởi tạo provider. CHƯA load model vào lúc này."""
        self._initialized = False
        _lazy_import()
    
    @staticmethod
    def is_available() -> bool:
        """Kiểm tra xem tất cả dependencies đã được cài đặt chưa."""
        _lazy_import()
        return len(_import_errors) == 0
    
    @staticmethod
    def get_missing_deps() -> List[str]:
        """Lấy danh sách tên các package bị thiếu để pip install."""
        _lazy_import()
        return _import_errors.copy()
    
    @staticmethod
    def get_install_command() -> str:
        """Lấy lệnh pip install cho các dependencies bị thiếu."""
        _lazy_import()
        if not _import_errors:
            return ""
        return f"pip install {' '.join(_import_errors)}"
    
    def initialize(self) -> bool:
        """
        Khởi tạo model nhận diện khuôn mặt.
        DeepFace sẽ tự động tải model lần đầu sử dụng.
        
        Returns:
            True nếu khởi tạo thành công, False nếu thất bại.
        """
        if self._initialized:
            return True
        
        if not self.is_available():
            return False
        
        try:
            # DeepFace load model lazy, ở đây chỉ pre-load để kiểm tra
            print(f"[FaceEmbeddingProvider] Đang tải model {self.MODEL_NAME}...")
            _deepface.build_model(self.MODEL_NAME)
            self._initialized = True
            print(f"[FaceEmbeddingProvider] Đã tải model thành công!")
            return True
        except Exception as e:
            print(f"[FaceEmbeddingProvider] Lỗi khởi tạo: {e}")
            return False
    
    def get_embedding_from_frame(self, frame) -> Optional["_np.ndarray"]:
        """
        Trích xuất vector embedding từ một frame ảnh BGR.
        
        Args:
            frame: Ảnh BGR dạng numpy array (từ cv2.read())
            
        Returns:
            Vector embedding 512 chiều (np.ndarray) hoặc None nếu không phát hiện khuôn mặt
        """
        if not self._initialized:
            return None
        
        try:
            # DeepFace.represent cần ảnh RGB
            rgb_frame = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
            
            # Lấy embedding sử dụng DeepFace
            # enforce_detection=False để tránh exception khi không tìm thấy khuôn mặt
            result = _deepface.represent(
                img_path=rgb_frame,
                model_name=self.MODEL_NAME,
                enforce_detection=False,
                detector_backend="opencv"  # Dùng opencv detector nhanh hơn
            )
            
            if not result or len(result) == 0:
                return None
            
            # Lấy embedding của khuôn mặt đầu tiên
            embedding = result[0].get("embedding")
            if embedding is None:
                return None
            
            return _np.array(embedding, dtype=_np.float32)
            
        except Exception as e:
            print(f"[FaceEmbeddingProvider] Lỗi trích xuất embedding: {e}")
            return None
    
    def get_embedding_dim(self) -> int:
        """Lấy số chiều của embedding (512 cho Facenet512)."""
        return self.EMBEDDING_DIM
    
    def get_model_name(self) -> str:
        """Lấy tên model để đăng ký với server."""
        return self.MODEL_NAME
    
    def get_default_threshold(self) -> float:
        """Lấy ngưỡng similarity khuyến nghị."""
        return self.DEFAULT_THRESHOLD
    
    @staticmethod
    def average_embeddings(embeddings: List["_np.ndarray"]) -> Optional["_np.ndarray"]:
        """
        Tính trung bình nhiều embeddings và chuẩn hóa L2.
        
        Việc này giúp tạo ra một embedding ổn định hơn từ nhiều góc chụp khác nhau.
        
        Args:
            embeddings: Danh sách các vector embedding
            
        Returns:
            Vector embedding đã trung bình và chuẩn hóa, hoặc None nếu danh sách rỗng
        """
        if not embeddings or _np is None:
            return None
        
        # Xếp chồng và tính trung bình
        stacked = _np.stack(embeddings, axis=0)
        avg = _np.mean(stacked, axis=0).astype(_np.float32)
        
        # Chuẩn hóa L2 (chia cho độ dài vector)
        norm = _np.linalg.norm(avg)
        if norm < 1e-12:  # Tránh chia cho 0
            return avg
        return avg / norm
    
    def open_camera(self, camera_index: int = 0):
        """
        Mở camera để chụp frame.
        
        Args:
            camera_index: Index của camera (mặc định 0 là webcam chính)
            
        Returns:
            cv2.VideoCapture object hoặc None nếu không mở được
        """
        if _cv2 is None:
            return None
        
        try:
            cap = _cv2.VideoCapture(camera_index)
            if cap.isOpened():
                return cap
            return None
        except Exception:
            return None
    
    @staticmethod
    def release_camera(cap):
        """Giải phóng camera capture object."""
        if cap is not None:
            try:
                cap.release()
            except:
                pass
    
    @staticmethod
    def frame_to_qimage(frame):
        """
        Chuyển đổi frame BGR sang QImage để hiển thị trong Qt.
        
        Args:
            frame: Ảnh BGR numpy array từ cv2
            
        Returns:
            QImage hoặc None nếu lỗi
        """
        if _cv2 is None or _np is None:
            return None
        
        try:
            from PySide6 import QtGui
            
            # Chuyển BGR sang RGB
            rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            
            # Tạo QImage
            qimg = QtGui.QImage(
                rgb.data, w, h, bytes_per_line,
                QtGui.QImage.Format.Format_RGB888
            )
            return qimg.copy()  # Trả về bản copy để tránh lỗi bộ nhớ
        except Exception:
            return None


# Instance singleton để tiện sử dụng
_provider_instance: Optional[FaceEmbeddingProvider] = None


def get_provider() -> FaceEmbeddingProvider:
    """Lấy hoặc tạo instance FaceEmbeddingProvider singleton."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = FaceEmbeddingProvider()
    return _provider_instance
