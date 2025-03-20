from pynput import keyboard as pynput_keyboard


def toggle():
    print("Toggled!")


def on_press(key):
    try:
        if key == pynput_keyboard.Key.space:
            toggle()
    except AttributeError:
        pass  # Ignore non-special keys if needed


# Start the listener
listener = pynput_keyboard.Listener(on_press=on_press)
listener.start()
print("Hotkey set (press Spacebar)")
listener.join()  # Wait for listener to keep script alive
