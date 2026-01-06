
import sys
import os

# Add project root to path
sys.path.insert(0, r'd:\Python_VsCode\AppChat')

from common.moderation.text_filter import normalize_text, TextModerationEngine
from common.moderation.decision_engine import SEVERE_WORDS

def debug_moderation():
    print("=== DEBUGGING MODERATION LOGIC ===")
    
    # 1. Test Normalization
    input_text = "địt mẹ mày"
    normalized = normalize_text(input_text)
    print(f"Input: '{input_text}'")
    print(f"Normalized: '{normalized}' (Hex: {[hex(ord(c)) for c in normalized]})")
    
    # 2. Test Badwords Loading
    badwords_path = r'd:\Python_VsCode\AppChat\common\moderation\badwords.txt'
    engine = TextModerationEngine(badwords_path)
    
    if "dit" in engine.short_words:
        print("'dit' found in short_words")
    else:
        print("'dit' NOT found in short_words")
        
    if "dm" in engine.short_words:
        print("'dm' found in short_words")
        
    # 3. Test Check
    result = engine.check(input_text)
    hits = result.get("hits", [])
    print(f"Hits: {hits}")
    
    # 4. Test Severe Check
    print("Checking against SEVERE_WORDS...")
    has_severe = False
    for hit in hits:
        print(f"Checking hit '{hit}' against SEVERE_WORDS...")
        if hit.lower() in SEVERE_WORDS:
            print(f"  -> MATCH FOUND (Direct): '{hit}'")
            has_severe = True
        
        for severe in SEVERE_WORDS:
            if severe in hit.lower():
                print(f"  -> MATCH FOUND (Contains): '{severe}' in '{hit}'")
                has_severe = True
                
    if has_severe:
        print("RESULT: BLOCK")
    else:
        print("RESULT: WARN (Severe check failed)")

if __name__ == "__main__":
    debug_moderation()
