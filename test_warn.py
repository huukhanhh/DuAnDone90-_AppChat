# Test WARN cases
import sys
sys.path.insert(0, r'd:\Python_VsCode\Chat_Client-Server')

from common.moderation.text_sanitizer import SmartTextSanitizer

sanitizer = SmartTextSanitizer()

# Test cases cho WARN - che từ xấu, giữ nguyên từ bình thường
warn_tests = [
    'Sao mày ngu thế',
    'Tại sao mày ngu vậy',
    'Mày hơi ngu đấy',
    'Bạn ơi đừng ngu nữa',
    'Đồ rác rưởi mày',
    'Mày là đồ rác rưởi',
    'Thằng này ngu quá trời',
    'Cái thằng ngu kia',
    'Sao đần thế',
    'Xin chào bạn',
]

print('=' * 100)
print('TEST WARN CASES - Che CHI tu xau')
print('=' * 100)

for text in warn_tests:
    result = sanitizer.sanitize(text)
    action = result['action']
    score = result['ai_score']
    censored = result['censored_text']
    hits = result['hits']
    
    marker = '[X]' if action == 'BLOCK' else '[!]' if action == 'WARN' else '[O]'
    
    print(f"{marker} {text:<35} -> {censored}")
    print(f"    Action: {action}, Score: {score:.4f}, Hits: {hits}")
    print()

print('=' * 100)
