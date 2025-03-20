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
        key = key.lower()
        # Map macOS key names to ones keyboard module recognizes
        if key in ["command", "cmd", "meta"]:
            # Try different variants for command key
            return any(keyboard.is_pressed(k) for k in ["command", "cmd"])

        # Explicitly handle 'd' key which has compatibility issues on macOS
        if key == "d":
            try:
                # First try keyboard module with scan code
                return keyboard.is_pressed(2)  # 'd' key code on macOS
            except:
                # If that fails, use a less reliable but working method
                # Just check if any(keyboard) since we're already checking command separately
                return len(keyboard._pressed_events) > 0 and any(
                    k for k in keyboard._pressed_events if str(k) == "d"
                )

        # Simple key check for other keys
        return keyboard.is_pressed(key)
    except ValueError as e:
        # Don't log on each check - too noisy
        return False
    except Exception as e:
        print(f"⚠️ Unexpected key check error for '{key}': {e}")
        return False


def is_key_combo_pressed(keys):
    """
    Check if a key combination is currently pressed

    Args:
        keys (list): List of keys that should be pressed together

    Returns:
        bool: True if all keys in the combination are pressed, False otherwise
    """
    try:
        return all(is_key_pressed(key) for key in keys)
    except Exception as e:
        print(f"⚠️ Key combo check error: {e}")
        return False
