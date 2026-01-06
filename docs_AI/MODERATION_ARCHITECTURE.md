# 🛡️ Hệ Thống Kiểm Duyệt Nội Dung - Multi-Layer Smart Detection

> **Phiên bản:** 2.0 (01/2026)  
> **Kiến trúc:** Multi-Layer Smart Detection  
> **Mục tiêu:** Accuracy, Performance, Context-Awareness

---

## 📑 Mục Lục

1. [Tổng Quan](#1-tổng-quan)
2. [Kiến Trúc Multi-Layer](#2-kiến-trúc-multi-layer)
3. [Chi Tiết Từng Layer](#3-chi-tiết-từng-layer)
4. [Luồng Xử Lý](#4-luồng-xử-lý)
5. [Phân Loại Từ Ngữ](#5-phân-loại-từ-ngữ)
6. [Hiệu Suất](#6-hiệu-suất)
7. [Test Cases](#7-test-cases)
8. [Cấu Trúc File](#8-cấu-trúc-file)

---

## 1. Tổng Quan

### 1.1 Vấn Đề Với Các Phương Pháp Cũ

| Phương pháp | Ưu điểm | Nhược điểm |
|-------------|---------|------------|
| **Rule-based only** | Nhanh, đơn giản | False-positive cao ("con chó dễ thương" bị censor) |
| **AI only** | Hiểu ngữ cảnh | False-positive ngược, phụ thuộc model |
| **AI + Rule-based đơn giản** | Tốt hơn | Chưa xử lý được nhiều edge cases |

### 1.2 Giải Pháp: Multi-Layer Smart Detection

Kết hợp **4 tầng xử lý** tuần tự, mỗi tầng đảm nhận một nhiệm vụ cụ thể:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MULTI-LAYER SMART DETECTION                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Input ──► L1: SEVERE ──► L2: PATTERN ──► L3: CONTEXT ──► L4: AI       │
│            (Block)       (Warn)         (Allow)        (Fallback)      │
│                                                                         │
│  Mỗi layer có thể RETURN ngay hoặc PASS xuống layer tiếp theo          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Kiến Trúc Multi-Layer

### 2.1 Sơ Đồ Tổng Quan

```
                         Input: "Thằng Khánh đang làm gì?"
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SEVERE WORDS DETECTION                                         │
│  ────────────────────────────────                                        │
│  Mục đích: Block ngay các từ tục tĩu                                    │
│  Danh sách: dit, dm, fuck, lon, cac, buoi...                            │
│                                                                          │
│  Kết quả: KHÔNG tìm thấy từ severe → PASS                               │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: INSULT PATTERN DETECTION                                       │
│  ─────────────────────────────────                                       │
│  Mục đích: Phát hiện pattern xúc phạm (prefix + badword)                │
│  Pattern: "thằng/đồ/con/lũ/bọn" + [từ trong badwords.txt]               │
│                                                                          │
│  Phân tích: "thằng" + "Khánh"                                           │
│  → "Khánh" KHÔNG có trong badwords.txt                                  │
│  Kết quả: PASS                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: POSITIVE CONTEXT DETECTION                                     │
│  ───────────────────────────────────                                     │
│  Mục đích: Allow các câu có ngữ cảnh tích cực                           │
│  Keywords: "dễ thương", "đáng thương", "nuôi", "thú cưng"...            │
│                                                                          │
│  Phân tích: Không có context keyword                                    │
│  Kết quả: PASS                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: AI FALLBACK                                                    │
│  ────────────────────                                                    │
│  Mục đích: Xử lý các trường hợp còn lại bằng AI                         │
│  Model: XLM-RoBERTa (đa ngôn ngữ)                                       │
│                                                                          │
│  AI Result: label="NOT", score=0.82                                     │
│  Kết quả: ALLOW ✅                                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Nguyên Tắc Hoạt Động

| Layer | Điều kiện | Action | Tiếp tục? |
|-------|-----------|--------|-----------|
| L1 | Có SEVERE word | **BLOCK** | ❌ Dừng |
| L2 | Prefix + badword | **WARN** | ❌ Dừng |
| L3 | Animal + positive context | **ALLOW** | ❌ Dừng |
| L4 | AI label = NOT | **ALLOW** | ❌ Dừng |
| L4 | AI label = OFFENSIVE + score ≥ 0.85 + hits | **WARN** | ❌ Dừng |
| L4 | Còn lại | **ALLOW** | ❌ Dừng |

---

## 3. Chi Tiết Từng Layer

### 3.1 Layer 1: Severe Words Detection

**Mục đích:** Block ngay các từ tục tĩu, không cần AI

**Danh sách SEVERE_WORDS:**
```python
SEVERE_WORDS = {
    # Đit và biến thể
    "dit", "ditme", "ditmemay", "ditcon", "djt", "d1t",
    
    # DM và biến thể  
    "dm", "dmm", "dmmm", "dcm", "dcmm",
    
    # Lon và biến thể
    "lon", "loz", "cailon", "conlon",
    
    # Cac và biến thể
    "cac", "cak", "concac", "caiconcac",
    
    # Buoi
    "buoi", "daubuoi",
    
    # English
    "fuck", "fck", "fuk",
}
```

**Xử lý:**
- Normalize text (bỏ dấu, lowercase)
- Check từng token trong SEVERE_WORDS set
- Nếu tìm thấy → **BLOCK** ngay

**Hiệu suất:** O(n) với set lookup O(1)

---

### 3.2 Layer 2: Insult Pattern Detection

**Mục đích:** Phát hiện pattern xúc phạm người

**Insult Prefixes:**
```python
INSULT_PREFIXES = ["thằng", "đồ", "con", "lũ", "bọn", "tụi"]
```

**Logic:**
```
"thằng" + [từ trong badwords.txt] → WARN
"thằng" + [tên người/từ bình thường] → PASS
```

**Ví dụ:**
| Input | Prefix | Next Word | In Badwords? | Result |
|-------|--------|-----------|--------------|--------|
| "Thằng ngu" | thằng | ngu | ✅ Yes | **WARN** |
| "Thằng Khánh" | thằng | khánh | ❌ No | PASS |
| "Đồ ngốc" | đồ | ngoc | ✅ Yes | **WARN** |
| "Đồ đẹp trai" | đồ | dep | ❌ No | PASS |

**Hiệu suất:** O(n) - one pass through words

---

### 3.3 Layer 3: Positive Context Detection

**Mục đích:** Allow các câu nói về động vật với ngữ cảnh tích cực

**Context Keywords:**
```python
POSITIVE_CONTEXTS = [
    # Tính từ tích cực
    "dễ thương", "đáng thương", "đáng yêu", "cute", "xinh", 
    "tội nghiệp", "dễ ghét", "ngộ nghĩnh",
    
    # Hoạt động chăm sóc
    "nuôi", "chăm sóc", "thú cưng", "thú y", "bệnh viện",
    
    # Neutral descriptions
    "con", "của tôi", "của em", "nhà tôi"
]

ANIMAL_WORDS = ["chó", "mèo", "gà", "vịt", "chuột", "thỏ", "hamster"]
```

**Logic:**
```python
if has_animal_word(text) and has_positive_context(text):
    return ALLOW
```

**Ví dụ:**
| Input | Animal | Positive | Result |
|-------|--------|----------|--------|
| "Con chó dễ thương" | chó ✅ | dễ thương ✅ | **ALLOW** |
| "Con mèo đáng yêu" | mèo ✅ | đáng yêu ✅ | **ALLOW** |
| "Con chó này" | chó ✅ | ❌ | PASS → L4 |

---

### 3.4 Layer 4: AI Fallback

**Mục đích:** Xử lý các trường hợp không rõ ràng bằng AI

**Model:** XLM-RoBERTa Offensive Detection (đa ngôn ngữ)

**Logic:**
```python
ai_result = ai_classifier.check(text)

if ai_result["label"] == "NOT":
    return ALLOW  # AI nói không xúc phạm
    
if ai_result["label"] == "OFFENSIVE":
    if ai_result["score"] >= 0.85:
        hits = rule_engine.check(text)["hits"]
        if hits:
            return WARN  # AI + Rule-based đồng ý
    
    return ALLOW  # Tránh false-positive
```

**Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=500)
def cached_ai_check(text):
    return ai_classifier.check(text)
```

---

## 4. Luồng Xử Lý

### 4.1 Client-Side

```
User gõ tin nhắn
        │
        ▼
┌─────────────────────────────────────────┐
│  ClientModerationController             │
│                                         │
│  ⚠️ CHỈ GỬI TIN GỐC LÊN SERVER         │
│  (Không censor ở client)                │
│                                         │
│  Lý do: Để Server AI quyết định         │
└─────────────────────────────────────────┘
        │
        ▼ TCP/IP
```

### 4.2 Server-Side

```
Server nhận tin nhắn
        │
        ▼
┌─────────────────────────────────────────┐
│  ServerModerationController             │
│          │                              │
│          ▼                              │
│  ModerationDecisionEngine.moderate()    │
│          │                              │
│          ├── L1: check_severe()         │
│          ├── L2: check_pattern()        │
│          ├── L3: check_context()        │
│          └── L4: check_ai()             │
│                                         │
│  Return: {action, final_text, hits}     │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│  ALLOW  → Broadcast tin gốc             │
│  WARN   → Broadcast tin đã censor       │
│  BLOCK  → Không broadcast, trả error    │
└─────────────────────────────────────────┘
```

---

## 5. Phân Loại Từ Ngữ

### 5.1 Ba Nhóm Từ

| Nhóm | Mô tả | Ví dụ | Xử lý |
|------|-------|-------|-------|
| **SEVERE** | Tục tĩu, không thể chấp nhận | dit, dm, fuck, lon | BLOCK ngay |
| **OFFENSIVE** | Xúc phạm khi kết hợp prefix | ngu, điên, chó, khùng | WARN nếu có pattern |
| **SENSITIVE** | Có thể vô hại tùy ngữ cảnh | chó, mèo, điên | Check context |

### 5.2 File badwords.txt Structure

```
# === SEVERE (L1 - BLOCK ngay) ===
# SEVERE_START
dit
dm
fuck
lon
cac
# SEVERE_END

# === OFFENSIVE (L2 - Pattern check) ===
ngu
dien
khung
dan
ngoc

# === COMPOUND WORDS ===
concho
thangcho
dongu
dodien
```

---

## 6. Hiệu Suất

### 6.1 Thời Gian Xử Lý

| Layer | Độ phức tạp | Thời gian | Khi nào chạy |
|-------|-------------|-----------|--------------|
| L1: SEVERE | O(n) | ~0.1ms | Luôn luôn |
| L2: PATTERN | O(n) | ~0.2ms | Nếu L1 pass |
| L3: CONTEXT | O(n) | ~0.2ms | Nếu L2 pass |
| L4: AI | O(1)* | ~50-100ms | Nếu L3 pass |

*O(1) với LRU cache, O(model) nếu cache miss

### 6.2 Tối Ưu

1. **LRU Cache** - Cache kết quả AI cho tin nhắn lặp lại
2. **Early Return** - Dừng ngay khi có kết quả ở bất kỳ layer nào
3. **Set Lookup** - Sử dụng set() cho O(1) lookup thay vì list
4. **Pre-compiled Regex** - Compile regex patterns một lần khi khởi động

### 6.3 Benchmark Ước Tính

| Scenario | Thời gian |
|----------|-----------|
| SEVERE word detected | ~0.5ms |
| Pattern detected | ~0.8ms |
| Context ALLOW | ~1.0ms |
| AI check (cache hit) | ~2ms |
| AI check (cache miss) | ~100ms |
| **Average (80% cache hit)** | **~20ms** |

---

## 7. Test Cases

### 7.1 Bảng Test Cases Toàn Diện

| # | Input | L1 | L2 | L3 | L4 | Expected | Đúng? |
|---|-------|----|----|----|----|----------|-------|
| 1 | "Xin chào bạn" | ❌ | ❌ | ❌ | NOT | **ALLOW** | ✅ |
| 2 | "Địt mẹ mày" | ✅ | - | - | - | **BLOCK** | ✅ |
| 3 | "Thằng ngu" | ❌ | ✅ | - | - | **WARN** | ✅ |
| 4 | "Thằng điên" | ❌ | ✅ | - | - | **WARN** | ✅ |
| 5 | "Thằng Khánh" | ❌ | ❌ | ❌ | NOT | **ALLOW** | ✅ |
| 6 | "Con chó dễ thương" | ❌ | ❌ | ✅ | - | **ALLOW** | ✅ |
| 7 | "Con chó đáng thương" | ❌ | ❌ | ✅ | - | **ALLOW** | ✅ |
| 8 | "Đồ con chó" | ❌ | ✅ | - | - | **WARN** | ✅ |
| 9 | "Mày ngu quá" | ❌ | ❌ | ❌ | OFF | **WARN** | ✅ |
| 10 | "dm" | ✅ | - | - | - | **BLOCK** | ✅ |
| 11 | "Tôi nuôi con chó" | ❌ | ❌ | ✅ | - | **ALLOW** | ✅ |
| 12 | "Lũ ngu" | ❌ | ✅ | - | - | **WARN** | ✅ |

### 7.2 Chạy Test

```bash
cd d:\Python_VsCode\Chat_Client-Server
python -m common.moderation.decision_engine
```

---

## 8. Cấu Trúc File

```
common/moderation/
├── ai_classifier.py      # AI Model XLM-RoBERTa
├── text_filter.py        # Rule-based + Pattern detection
├── decision_engine.py    # Multi-Layer Decision Engine (CORE)
├── badwords.txt          # Danh sách từ cấm (phân loại)
├── types.py              # Constants (ALLOW, WARN, BLOCK)
└── __init__.py

client/controllers/
└── moderation_controller.py  # Client-side (gửi tin gốc)

server/controllers/
└── moderation_controller.py  # Server-side (Multi-Layer check)

docs_AI/
└── MODERATION_ARCHITECTURE.md  # Tài liệu này
```

---

## 📌 Tổng Kết

**Multi-Layer Smart Detection** giải quyết các vấn đề:

| Vấn đề | Giải pháp |
|--------|-----------|
| "Con chó dễ thương" bị censor | L3: Positive Context Detection |
| "Thằng Khánh" bị censor | L2: Pattern chỉ check badwords |
| "Địt mẹ" không bị block | L1: SEVERE words detection |
| AI false-positive | L4: Yêu cầu score ≥ 0.85 + hits |
| Performance chậm | LRU Cache + Early Return |

**Kết quả:**
- ✅ Accuracy cao (context-aware)
- ✅ Performance tốt (~20ms average)
- ✅ UX tốt (ít false-positive)
