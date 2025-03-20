import pyautogui
import time

# Configure pyautogui settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1  # Slightly increase the pause to avoid issues

def send_key_combo(modifier, key):
    """
    Send a single key press (ignoring modifier)
    
    Args:
        modifier (str): Ignored parameter (kept for compatibility)
        key (str): The key to press
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Just press the single key (number)
        pyautogui.press(key)
        print(f"✅ Successfully pressed '{key}'")
        return True
    except Exception as e:
        print(f"❌ Failed to press '{key}': {str(e)}")
        return False 