import pyautogui
import time
import keyboard

# Configure pyautogui settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01  # Reduce pause to 10ms for faster response

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
        return True
    except Exception as e:
        print(f"❌ Failed to press '{key}': {str(e)}")
        return False 

def is_key_pressed(key):
    """
    Check if a key is currently pressed using the keyboard module
    
    Args:
        key (str): The key to check
        
    Returns:
        bool: True if the key is pressed, False otherwise
    """
    try:
        # Map macOS key names to ones keyboard module recognizes
        if key == 'command' or key == 'cmd' or key == 'meta':
            # Try different variants for command key
            return any(keyboard.is_pressed(k) for k in ['command', 'cmd'])
        
        # Simple key check for other keys
        return keyboard.is_pressed(key)
    except Exception as e:
        print(f"⚠️ Key check error: {e}")
        return False 