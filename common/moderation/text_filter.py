# common/moderation/text_filter.py
# Text moderation engine - lọc từ ngữ thô tục/phản cảm
# Hỗ trợ bắt các biến thể: "dit me", "d i t m e", "d.i.t-m_e", "Địt mẹ", etc.

import re
import os
import unicodedata
from common.moderation.types import ACTION_ALLOW, ACTION_WARN, ACTION_BLOCK, create_result


# Bảng chuyển đổi dấu tiếng Việt
VIETNAMESE_DIACRITICS = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'đ': 'd',
    # Uppercase
    'À': 'a', 'Á': 'a', 'Ả': 'a', 'Ã': 'a', 'Ạ': 'a',
    'Ă': 'a', 'Ằ': 'a', 'Ắ': 'a', 'Ẳ': 'a', 'Ẵ': 'a', 'Ặ': 'a',
    'Â': 'a', 'Ầ': 'a', 'Ấ': 'a', 'Ẩ': 'a', 'Ẫ': 'a', 'Ậ': 'a',
    'È': 'e', 'É': 'e', 'Ẻ': 'e', 'Ẽ': 'e', 'Ẹ': 'e',
    'Ê': 'e', 'Ề': 'e', 'Ế': 'e', 'Ể': 'e', 'Ễ': 'e', 'Ệ': 'e',
    'Ì': 'i', 'Í': 'i', 'Ỉ': 'i', 'Ĩ': 'i', 'Ị': 'i',
    'Ò': 'o', 'Ó': 'o', 'Ỏ': 'o', 'Õ': 'o', 'Ọ': 'o',
    'Ô': 'o', 'Ồ': 'o', 'Ố': 'o', 'Ổ': 'o', 'Ỗ': 'o', 'Ộ': 'o',
    'Ơ': 'o', 'Ờ': 'o', 'Ớ': 'o', 'Ở': 'o', 'Ỡ': 'o', 'Ợ': 'o',
    'Ù': 'u', 'Ú': 'u', 'Ủ': 'u', 'Ũ': 'u', 'Ụ': 'u',
    'Ư': 'u', 'Ừ': 'u', 'Ứ': 'u', 'Ử': 'u', 'Ữ': 'u', 'Ự': 'u',
    'Ỳ': 'y', 'Ý': 'y', 'Ỷ': 'y', 'Ỹ': 'y', 'Ỵ': 'y',
    'Đ': 'd',
}

# Bảng chống né (leet speak / symbol substitution)
LEET_MAP = {
    '@': 'a',
    '4': 'a',
    '$': 's',
    '5': 's',
    '!': 'i',
    '1': 'i',
    '0': 'o',
    '3': 'e',
    '7': 't',
    '8': 'b',
    '9': 'g',
    '+': 't',
    '|': 'i',
}

# Các ký tự phân tách cần chuyển thành khoảng trắng
SEPARATOR_CHARS = r'[.,\-_*/\\|:;!@#$%^&()+=\[\]{}\'\"<>?`~]'


def normalize_text(text: str) -> str:
    """
    Chuẩn hóa văn bản để so khớp từ cấm.
    
    Steps:
    1. Lowercase
    2. Bỏ dấu tiếng Việt (dùng bảng thủ công + NFD decomposition)
    3. Chuyển đ/Đ -> d
    4. Chống né (leet speak: @->a, $->s, etc.)
    5. Chuyển ký tự phân tách (.,_-*/|) thành khoảng trắng
    6. Loại bỏ ký tự lạ (chỉ giữ a-z, 0-9, space)
    7. Gom khoảng trắng
    
    Args:
        text: Văn bản gốc
        
    Returns:
        Văn bản đã chuẩn hóa
    """
    if not text:
        return ""
    
    result = text.lower()
    
    # Bỏ dấu tiếng Việt bằng bảng thủ công (ưu tiên)
    for vn_char, ascii_char in VIETNAMESE_DIACRITICS.items():
        result = result.replace(vn_char, ascii_char)
    
    # Fallback: Dùng NFD decomposition cho các ký tự còn sót
    # NFD tách dấu ra khỏi ký tự gốc, sau đó loại bỏ các combining marks
    try:
        nfd_text = unicodedata.normalize('NFD', result)
        result = ''.join(c for c in nfd_text if unicodedata.category(c) != 'Mn')
    except:
        pass
    
    # Chống né (leet speak)
    for leet_char, normal_char in LEET_MAP.items():
        result = result.replace(leet_char, normal_char)
    
    # Chuyển ký tự phân tách thành khoảng trắng
    result = re.sub(SEPARATOR_CHARS, ' ', result)
    
    # Loại bỏ ký tự lạ (chỉ giữ a-z, 0-9, space)
    result = re.sub(r'[^a-z0-9\s]', '', result)
    
    # Gom khoảng trắng
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def pack_text(normalized_text: str) -> str:
    """
    Tạo bản "packed" của văn bản đã chuẩn hóa.
    Bỏ hết khoảng trắng để bắt các kiểu chèn ký tự.
    
    Ví dụ: "d i t m e" -> "ditme"
    
    Args:
        normalized_text: Văn bản đã qua normalize_text()
        
    Returns:
        Văn bản không có khoảng trắng
    """
    return normalized_text.replace(' ', '')


def load_badwords(path: str) -> tuple:
    """
    Load danh sách từ cấm từ file.
    
    Args:
        path: Đường dẫn tới file badwords.txt
        
    Returns:
        Tuple (short_words, long_words):
        - short_words: Set các từ ngắn (<=3 ký tự) - chỉ match token
        - long_words: Set các từ dài (>=4 ký tự) - có thể match packed
    """
    short_words = set()  # <=3 chars: only token match
    long_words = set()   # >=4 chars: can use packed contains
    
    if not os.path.exists(path):
        print(f"[MODERATION] Warning: badwords file not found: {path}")
        return short_words, long_words
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                # Bỏ comment và whitespace
                line = line.strip()
                if line and not line.startswith('#'):
                    # Normalize từ cấm khi load
                    normalized = normalize_text(line)
                    # Tạo packed version (bỏ space)
                    packed = pack_text(normalized)
                    
                    if packed:
                        if len(packed) <= 3:
                            short_words.add(packed)
                        else:
                            long_words.add(packed)
    except Exception as e:
        print(f"[MODERATION] Error loading badwords: {e}")
    
    return short_words, long_words


class TextModerationEngine:
    """
    Engine kiểm duyệt văn bản.
    
    Hỗ trợ bắt các biến thể:
    - "dit me" (có khoảng trắng)
    - "d i t m e" (chèn khoảng trắng)
    - "d.i.t-m_e" (chèn ký tự đặc biệt)
    - "Địt mẹ" (có dấu tiếng Việt)
    - "DiT    mE" (mixed case, nhiều space)
    
    Chiến lược matching:
    - Từ ngắn (<=3 ký tự): Chỉ match theo token để tránh false positive
      (ví dụ: "vl" không nên match trong "valentine")
    - Từ dài (>=4 ký tự): Match bằng packed contains
    """
    
    def __init__(self, badwords_path: str):
        """
        Khởi tạo engine với đường dẫn file từ cấm.
        
        Args:
            badwords_path: Đường dẫn tới file badwords.txt
        """
        self.short_words, self.long_words = load_badwords(badwords_path)
        self.badwords_path = badwords_path
        total = len(self.short_words) + len(self.long_words)
        print(f"[MODERATION] Loaded {total} badwords ({len(self.short_words)} short, {len(self.long_words)} long)")
    
    def reload_badwords(self):
        """Reload danh sách từ cấm từ file."""
        self.short_words, self.long_words = load_badwords(self.badwords_path)
        total = len(self.short_words) + len(self.long_words)
        print(f"[MODERATION] Reloaded {total} badwords")
    
    def check(self, text: str) -> dict:
        """
        Kiểm duyệt văn bản.
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            dict với format chuẩn:
            {
                "action": "ALLOW" | "WARN",
                "reason": "string",
                "hits": ["từ vi phạm"],
                "score": None,
                "censored_text": "văn bản đã censor"
            }
        """
        if not text:
            return create_result(ACTION_ALLOW, censored_text=text)
        
        if not self.short_words and not self.long_words:
            return create_result(ACTION_ALLOW, censored_text=text)
        
        normalized = normalize_text(text)
        packed = pack_text(normalized)
        tokens = normalized.split()
        
        hits = []
        
        # Check 1: Từ ngắn (<=3 ký tự) - chỉ match theo token
        for token in tokens:
            if token in self.short_words:
                if token not in hits:
                    hits.append(token)
        
        # Check 2: Từ dài (>=4 ký tự) - match bằng packed contains
        for long_word in self.long_words:
            if long_word in packed:
                if long_word not in hits:
                    hits.append(long_word)
        
        if hits:
            # Censor văn bản và trả về WARN
            censored = self.censor_text(text, hits)
            return create_result(
                ACTION_WARN,
                reason="Tin nhắn của bạn có chứa từ ngữ không phù hợp",
                hits=hits,
                censored_text=censored
            )
        
        return create_result(ACTION_ALLOW, censored_text=text)
    
    def censor_text(self, original_text: str, hits: list) -> str:
        """
        Censor các từ cấm trong văn bản gốc bằng dấu *.
        
        Args:
            original_text: Văn bản gốc
            hits: Danh sách từ cấm (đã normalize và pack)
            
        Returns:
            Văn bản đã được censor (thay từ cấm bằng ***)
        """
        if not hits or not original_text:
            return original_text
        
        result = original_text
        
        # Sắp xếp hits theo độ dài giảm dần để thay thế từ dài trước
        sorted_hits = sorted(hits, key=len, reverse=True)
        
        for badword in sorted_hits:
            # Tìm tất cả các biến thể của từ cấm trong văn bản gốc
            pattern = self._build_pattern_for_badword(badword)
            
            def replace_with_asterisks(match):
                """Thay thế bằng số dấu * bằng với độ dài từ gốc"""
                return '*' * len(match.group(0))
            
            try:
                result = re.sub(pattern, replace_with_asterisks, result, flags=re.IGNORECASE)
            except:
                # Fallback: simple replacement
                pass
        
        return result
    
    def _build_pattern_for_badword(self, badword: str) -> str:
        """
        Xây dựng regex pattern để tìm các biến thể của từ cấm.
        
        Ví dụ: "ditme" sẽ match "ditme", "địt mẹ", "d!t m3", "d i t m e", etc.
        """
        pattern_parts = []
        
        for char in badword:
            if char == 'a':
                pattern_parts.append(r'[aàáảãạăằắẳẵặâầấẩẫậ@4AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ]')
            elif char == 'e':
                pattern_parts.append(r'[eèéẻẽẹêềếểễệ3EÈÉẺẼẸÊỀẾỂỄỆ]')
            elif char == 'i':
                pattern_parts.append(r'[iìíỉĩị!1|IÌÍỈĨỊyỳýỷỹỵYỲÝỶỸỴ]')
            elif char == 'o':
                pattern_parts.append(r'[oòóỏõọôồốổỗộơờớởỡợ0OÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ]')
            elif char == 'u':
                pattern_parts.append(r'[uùúủũụưừứửữựUÙÚỦŨỤƯỪỨỬỮỰ]')
            elif char == 'y':
                pattern_parts.append(r'[yỳýỷỹỵYỲÝỶỸỴiìíỉĩịIÌÍỈĨỊ]')
            elif char == 'd':
                pattern_parts.append(r'[dđDĐ]')
            elif char == 's':
                pattern_parts.append(r'[sS$5]')
            elif char == 't':
                pattern_parts.append(r'[tT7+]')
            elif char == 'b':
                pattern_parts.append(r'[bB8]')
            elif char == 'g':
                pattern_parts.append(r'[gG9]')
            elif char == 'c':
                pattern_parts.append(r'[cCkK]')
            elif char == 'k':
                pattern_parts.append(r'[kKcC]')
            elif char == 'm':
                pattern_parts.append(r'[mM]')
            elif char == 'n':
                pattern_parts.append(r'[nN]')
            elif char == 'l':
                pattern_parts.append(r'[lL1|]')
            else:
                # Ký tự thường - escape và match cả upper/lower
                escaped = re.escape(char)
                pattern_parts.append(f'[{escaped}{escaped.upper()}]')
        
        # Cho phép có khoảng trắng hoặc ký tự đặc biệt xen giữa
        # Ví dụ: "d i t m e" hoặc "d.i.t.m.e" vẫn match
        separator = r'[\s.,\-_*/\\|:;!@#$%^&()+=\[\]{}\'\"<>?`~]*'
        flexible_pattern = separator.join(pattern_parts)
        
        return flexible_pattern
