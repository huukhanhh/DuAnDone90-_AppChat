# 🤖 Hệ Thống AI Moderation - Giải Thích Chi Tiết

## Mục Lục
1. [Tổng Quan](#1-tổng-quan)
2. [AI Classifier (XLM-RoBERTa)](#2-ai-classifier-xlm-roberta)
3. [Rule-based Engine (badwords.txt)](#3-rule-based-engine)
4. [Decision Engine](#4-decision-engine)
5. [Luồng Hoạt Động](#5-luồng-hoạt-động)
6. [Cấu Trúc File](#6-cấu-trúc-file)
7. [Ví Dụ Thực Tế](#7-ví-dụ-thực-tế)

---

## 1. Tổng Quan

Hệ thống kiểm duyệt nội dung chat kết hợp **2 tầng**:

| Tầng | Công nghệ | Vai trò |
|------|-----------|---------|
| **Tầng 1** | AI Classifier (Deep Learning) | Phát hiện vi phạm tổng quát |
| **Tầng 2** | Rule-based (Regex + Từ điển) | Xác nhận + Phân loại độ nặng |

### Tại sao cần 2 tầng?

```
AI đơn lẻ:
  ✅ Phát hiện từ mới, ngữ cảnh
  ❌ Có thể nhầm ("hi" → vi phạm?)
  ❌ Không phân biệt nhẹ/nặng

Rule-based đơn lẻ:
  ✅ Chính xác với từ điển
  ❌ Bỏ sót từ mới, biến thể lạ
  
Kết hợp cả 2:
  ✅ AI phát hiện tổng quát
  ✅ Rule-based xác nhận + phân loại
  ✅ Giảm false positive (nhầm)
```

---

## 2. AI Classifier (XLM-RoBERTa)

### 2.1 Thông tin Model

| Thuộc tính | Giá trị |
|------------|---------|
| **Tên** | `christinacdl/XLM_RoBERTa-Offensive-Language-Detection-8-langs-new` |
| **Kiến trúc** | XLM-RoBERTa (Meta/Facebook) |
| **Framework** | Hugging Face Transformers |
| **Ngôn ngữ** | 8 ngôn ngữ (English, Vietnamese, Spanish, German, French, Italian, Portuguese, Turkish) |
| **Kích thước** | ~1.1 GB |
| **Thiết bị** | CPU (có thể dùng GPU) |

### 2.2 Input/Output

```
Input:  "Sao mày ngu thế"
         │
         ▼
    ┌─────────────┐
    │  XLM-RoBERTa │
    │   Model      │
    └─────┬───────┘
          │
          ▼
Output: {
    "label": "OFFENSIVE",  // hoặc "NOT"
    "score": 0.9272        // 0.0 - 1.0
}
```

### 2.3 Cách hoạt động

1. **Tokenization**: Văn bản được tách thành tokens (subwords)
2. **Embedding**: Tokens được chuyển thành vector số
3. **Transformer**: 12 lớp attention xử lý ngữ cảnh
4. **Classification**: Lớp cuối phân loại NOT/OFFENSIVE

### 2.4 File liên quan

- `common/moderation/ai_classifier.py` - Class `ToxicAIClassifier`

```python
from common.moderation.ai_classifier import ToxicAIClassifier

classifier = ToxicAIClassifier()
result = classifier.check("Xin chào bạn")
# {'label': 'NOT', 'score': 0.7994, 'action': 'ALLOW', ...}
```

---

## 3. Rule-based Engine

### 3.1 Thông tin

| Thuộc tính | Giá trị |
|------------|---------|
| **File từ điển** | `common/moderation/badwords.txt` |
| **Số từ** | 269 từ (47 ngắn, 222 dài) |
| **Khả năng** | Bắt biến thể (leet, space, dấu chấm) |

### 3.2 Danh sách từ vi phạm

```
# badwords.txt
ngu
cho
concho
dit
ditme
dm
dmm
...
```

### 3.3 Khả năng bắt biến thể

| Biến thể | Ví dụ | Phát hiện? |
|----------|-------|------------|
| Gốc | ngu | ✅ |
| Không dấu | ngu → ngu | ✅ |
| Leet speak | d!t m3 | ✅ |
| Có khoảng trắng | d i t m e | ✅ |
| Chèn dấu chấm | đ.ị.t m.ẹ | ✅ |

### 3.4 File liên quan

- `common/moderation/text_filter.py` - Class `TextModerationEngine`

```python
from common.moderation.text_filter import TextModerationEngine

engine = TextModerationEngine("path/to/badwords.txt")
result = engine.check("mày ngu thế")
# {'action': 'BLOCK', 'hits': ['ngu'], ...}
```

---

## 4. Decision Engine

### 4.1 Vai trò

Kết hợp AI + Rule-based để đưa ra quyết định cuối cùng.

### 4.2 Logic quyết định

```
                    ┌─────────────────────┐
                    │   AI: OFFENSIVE?    │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
           label=NOT      label=OFFENSIVE
               │               │
               ▼               ▼
         ┌─────────┐    ┌─────────────────────┐
         │ ✅ ALLOW │    │ Rule-based tìm từ    │
         └─────────┘    └──────────┬──────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   │               │               │
               hits=[]        hits có từ       hits có từ
               (không có)       NHẸ              NẶNG
                   │               │               │
                   ▼               ▼               ▼
             ┌─────────┐    ┌─────────┐    ┌─────────┐
             │ ✅ ALLOW │    │ ⚠️ WARN  │    │ ❌ BLOCK │
             │(tránh FP)│    │(che từ) │    │(chặn)  │
             └─────────┘    └─────────┘    └─────────┘
```

### 4.3 Phân loại từ vi phạm

| Loại | Ví dụ | Hành động |
|------|-------|-----------|
| **Từ NHẸ (insult)** | ngu, chó, đần, ngốc | ⚠️ WARN - Che từ, cho gửi |
| **Từ NẶNG (profanity)** | đ*t, dm, lồn, c*c | ❌ BLOCK - Chặn hoàn toàn |

### 4.4 File liên quan

- `common/moderation/decision_engine.py` - Class `ModerationDecisionEngine`

```python
from common.moderation.decision_engine import ModerationDecisionEngine

engine = ModerationDecisionEngine(ai_engine, rule_engine)
result = engine.moderate("sao mày ngu thế")
# {'action': 'WARN', 'final_text': 'sao mày *** thế', 'hits': ['ngu'], ...}
```

---

## 5. Luồng Hoạt Động

### 5.1 Client-side

```
User gõ tin nhắn
       │
       ▼
┌──────────────────────────────────────┐
│  ClientModerationController          │
│  (client/controllers/moderation_...) │
│       │                              │
│       ├── ALLOW → Gửi bình thường    │
│       ├── WARN  → Popup cảnh báo     │
│       │          + Gửi tin đã che    │
│       └── BLOCK → Popup chặn         │
│                  + KHÔNG gửi         │
└──────────────────────────────────────┘
```

### 5.2 Server-side

```
Server nhận tin nhắn
       │
       ▼
┌──────────────────────────────────────┐
│  ServerModerationController          │
│  (server/controllers/moderation_...) │
│       │                              │
│       ├── ALLOW → Broadcast          │
│       ├── WARN  → Broadcast đã che   │
│       └── BLOCK → Không broadcast    │
│                  + Return error      │
└──────────────────────────────────────┘
```

---

## 6. Cấu Trúc File

```
common/moderation/
├── ai_classifier.py      # AI Model (XLM-RoBERTa)
├── text_filter.py        # Rule-based Engine
├── decision_engine.py    # Decision Engine (AI + Rule)
├── badwords.txt          # Danh sách từ cấm (269 từ)
├── types.py              # Constants (ALLOW, WARN, BLOCK)
└── text_sanitizer.py     # (phiên bản cũ, không dùng)

client/controllers/
└── moderation_controller.py  # Client-side moderation

server/controllers/
└── moderation_controller.py  # Server-side moderation
```

---

## 7. Ví Dụ Thực Tế

### Test Case 1: Tin nhắn bình thường

```
Input:  "Xin chào bạn"
AI:     label=NOT, score=0.80
Action: ✅ ALLOW
Output: "Xin chào bạn"
```

### Test Case 2: Vi phạm nhẹ

```
Input:  "Sao mày ngu thế"
AI:     label=OFFENSIVE, score=0.93
Rule:   hits=['ngu'] (từ NHẸ)
Action: ⚠️ WARN
Output: "Sao mày *** thế" + Popup cảnh báo
```

### Test Case 3: Vi phạm nặng

```
Input:  "Đ*t mẹ mày"
AI:     label=OFFENSIVE, score=0.99
Rule:   hits=['dit', 'ditme'] (từ NẶNG)
Action: ❌ BLOCK
Output: (không gửi) + Popup chặn
```

### Test Case 4: AI nhầm, Rule-based sửa

```
Input:  "hi"
AI:     label=OFFENSIVE, score=0.85 (FALSE POSITIVE!)
Rule:   hits=[] (không tìm thấy từ xấu)
Action: ✅ ALLOW (tin tưởng Rule-based)
Output: "hi"
```

---

## Tổng Kết

| Thành phần | File | Vai trò |
|------------|------|---------|
| AI Classifier | `ai_classifier.py` | Phát hiện vi phạm tổng quát |
| Rule Engine | `text_filter.py` | Xác nhận + Tìm từ cụ thể |
| Decision Engine | `decision_engine.py` | Quyết định ALLOW/WARN/BLOCK |
| Từ điển | `badwords.txt` | 269 từ cấm tiếng Việt |

**Ưu điểm của hệ thống:**
- ✅ AI bắt được từ mới, ngữ cảnh
- ✅ Rule-based xác nhận, tránh false positive
- ✅ Phân loại độ nặng (WARN vs BLOCK)
- ✅ Che từ xấu chính xác, giữ từ bình thường
