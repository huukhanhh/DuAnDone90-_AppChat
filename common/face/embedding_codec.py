# common/face/embedding_codec.py
"""
Tiện ích codec cho embedding FaceID.
Cung cấp chuyển đổi giữa vector float32, bytes (little-endian), và chuỗi base64.

Các hàm:
    - embedding_to_bytes: np.ndarray -> bytes
    - bytes_to_embedding: bytes -> np.ndarray
    - embedding_to_b64: np.ndarray -> base64 str
    - b64_to_embedding: base64 str -> np.ndarray
    - normalize_embedding: Chuẩn hóa L2 một vector
"""

import base64
from typing import TYPE_CHECKING

# Import numpy lazy - không fail khi import module
_numpy = None
_numpy_import_error = None

try:
    import numpy as np
    _numpy = np
except ImportError as e:
    _numpy_import_error = e

if TYPE_CHECKING:
    import numpy as np


def _require_numpy():
    """Đảm bảo numpy đã được cài đặt, raise lỗi thân thiện nếu chưa."""
    if _numpy is None:
        raise ImportError(
            "numpy là bắt buộc cho các thao tác face embedding nhưng chưa được cài. "
            "Vui lòng cài đặt bằng: pip install numpy"
        ) from _numpy_import_error
    return _numpy


def embedding_to_bytes(vec: "np.ndarray") -> bytes:
    """
    Chuyển đổi numpy array float32 sang bytes thô (little-endian).
    
    Args:
        vec: numpy array có shape (dim,) với dtype float32
        
    Returns:
        Bytes thô theo định dạng little-endian float32
    """
    np = _require_numpy()
    # Đảm bảo float32 và contiguous
    arr = np.asarray(vec, dtype=np.float32)
    if arr.ndim != 1:
        raise ValueError(f"Cần array 1 chiều, nhận được shape {arr.shape}")
    # little-endian float32
    return arr.astype('<f4').tobytes()


def bytes_to_embedding(b: bytes, dim: int) -> "np.ndarray":
    """
    Parse bytes thành vector float32 (little-endian).
    
    Args:
        b: Bytes thô (little-endian float32)
        dim: Số chiều mong đợi của embedding
        
    Returns:
        numpy array có shape (dim,) với dtype float32
        
    Raises:
        ValueError: Nếu độ dài byte không khớp dim * 4 (DIM_MISMATCH)
    """
    np = _require_numpy()
    expected_len = dim * 4  # float32 = 4 bytes
    if len(b) != expected_len:
        raise ValueError(
            f"DIM_MISMATCH: mong đợi {expected_len} bytes cho dim={dim}, nhận được {len(b)} bytes"
        )
    # little-endian float32
    return np.frombuffer(b, dtype='<f4').copy()


def embedding_to_b64(vec: "np.ndarray") -> str:
    """
    Chuyển đổi numpy array float32 sang chuỗi base64.
    
    Args:
        vec: numpy array có shape (dim,) với dtype float32
        
    Returns:
        Chuỗi base64 của embedding bytes
    """
    raw_bytes = embedding_to_bytes(vec)
    return base64.b64encode(raw_bytes).decode('ascii')


def b64_to_embedding(s: str, dim: int) -> "np.ndarray":
    """
    Giải mã chuỗi base64 thành numpy array float32.
    
    Args:
        s: Chuỗi đã mã hóa base64
        dim: Số chiều mong đợi của embedding
        
    Returns:
        numpy array có shape (dim,) với dtype float32
        
    Raises:
        ValueError: Nếu độ dài byte sau giải mã không khớp dim * 4 (DIM_MISMATCH)
    """
    raw_bytes = base64.b64decode(s)
    return bytes_to_embedding(raw_bytes, dim)


def normalize_embedding(vec: "np.ndarray") -> "np.ndarray":
    """
    Chuẩn hóa L2 một vector an toàn (tránh chia cho 0).
    
    Args:
        vec: numpy array có shape (dim,)
        
    Returns:
        numpy array đã chuẩn hóa L2. Nếu norm < 1e-12, trả về vec không đổi.
    """
    np = _require_numpy()
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm < 1e-12:
        # Tránh chia cho 0, trả về không đổi
        return arr
    return arr / norm


# =============================================================================
# Tự kiểm tra (Self-test)
# =============================================================================
if __name__ == "__main__":
    print("Đang chạy self-test cho embedding_codec...")
    
    np = _require_numpy()
    
    # Tham số test
    DIM = 128
    TOLERANCE = 1e-6
    
    # 1. Tạo vector ngẫu nhiên
    original = np.random.randn(DIM).astype(np.float32)
    print(f"  Vector gốc shape: {original.shape}, dtype: {original.dtype}")
    
    # 2. Chuẩn hóa
    normalized = normalize_embedding(original)
    norm_value = np.linalg.norm(normalized)
    print(f"  Norm của vector đã chuẩn hóa: {norm_value:.6f}")
    assert abs(norm_value - 1.0) < TOLERANCE, f"Norm phải ~1.0, nhận được {norm_value}"
    
    # 3. Vòng lặp kiểm tra: bytes
    raw_bytes = embedding_to_bytes(normalized)
    print(f"  Độ dài bytes: {len(raw_bytes)} (mong đợi {DIM * 4})")
    assert len(raw_bytes) == DIM * 4, "Độ dài bytes không khớp"
    
    restored_from_bytes = bytes_to_embedding(raw_bytes, DIM)
    diff_bytes = np.max(np.abs(normalized - restored_from_bytes))
    print(f"  Max sai lệch sau vòng bytes: {diff_bytes:.2e}")
    assert diff_bytes < TOLERANCE, f"Vòng bytes thất bại, diff={diff_bytes}"
    
    # 4. Vòng lặp kiểm tra: base64
    b64_str = embedding_to_b64(normalized)
    print(f"  Độ dài chuỗi Base64: {len(b64_str)}")
    
    restored_from_b64 = b64_to_embedding(b64_str, DIM)
    diff_b64 = np.max(np.abs(normalized - restored_from_b64))
    print(f"  Max sai lệch sau vòng b64: {diff_b64:.2e}")
    assert diff_b64 < TOLERANCE, f"Vòng b64 thất bại, diff={diff_b64}"
    
    # 5. Test lỗi DIM_MISMATCH
    try:
        bytes_to_embedding(raw_bytes, DIM + 1)  # Sai dim
        assert False, "Phải raise ValueError"
    except ValueError as e:
        assert "DIM_MISMATCH" in str(e)
        print(f"  Lỗi DIM_MISMATCH được raise đúng: {e}")
    
    # 6. Test chuẩn hóa với vector zero
    zero_vec = np.zeros(DIM, dtype=np.float32)
    normalized_zero = normalize_embedding(zero_vec)
    assert np.allclose(normalized_zero, zero_vec), "Vector zero phải giữ nguyên"
    print("  Chuẩn hóa vector zero: OK")
    
    print("\n[OK] Tất cả self-tests đã pass!")
