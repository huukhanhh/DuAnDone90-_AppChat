
import sys
import os

# Add project root to path
sys.path.insert(0, r'd:\Python_VsCode\AppChat')

from client.controllers.moderation_controller import ClientModerationController

def test_client_moderation():
    print("=== TESTING CLIENT MODERATION CONTROLLER ===")
    
    # Initialize controller
    # Point to the correct badwords file
    badwords_path = r'd:\Python_VsCode\AppChat\common\moderation\badwords.txt'
    controller = ClientModerationController(badwords_path)
    
    test_cases = [
        # Normal
        ("Xin chào bạn", "ALLOW"),
        
        # Severe - Should be BLOCKED now (previously WARN)
        ("địt mẹ mày", "BLOCK"), 
        ("dm mày", "BLOCK"),
        
        # Insult - Should now be ALLOWED (Server AI will handle it)
        ("ngu quá", "ALLOW"),
        ("đồ con chó", "ALLOW"), # "cho" is mild, let server decide context
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_action in test_cases:
        print(f"\nScanning: '{text}'")
        result = controller.check_outgoing_text(text)
        action = result["action"]
        final_text = result.get("final_text")
        hits = result.get("hits")
        
        print(f"  -> Action: {action} (Expected: {expected_action})")
        print(f"  -> Final Text: {final_text}")
        print(f"  -> Hits: {hits}")
        
        if action == expected_action:
            print("  -> PASS")
            passed += 1
        else:
            print("  -> FAIL")
            failed += 1
            
    print("-" * 50)
    print(f"Result: {passed}/{len(test_cases)} passed")
    
    if failed == 0:
        print("SUCCESS: Client check logic is working as intended.")
    else:
        print("FAILURE: Some test cases failed.")

if __name__ == "__main__":
    test_client_moderation()
